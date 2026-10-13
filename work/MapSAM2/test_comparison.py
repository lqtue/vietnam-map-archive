"""Regression checks for the GPU comparison path; all fixtures are synthetic.

Run with the isolated segmentation environment. Set SAM2_SOURCE_DIR to the
qualified upstream clone to exercise a real, randomly initialized SAM2.1 model.
This verifies APIs/tensor flow, never map accuracy.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'image-processing/scripts'))
from memory_predictor import DiverseMemoryBank, MemoryEntry, MemoryImagePredictor
from seg_context import load_context, mask_area_bounds, legend_suggestion
from masks_to_polygons import masks_to_polygons
from to_sam2_seeds import blocks_to_seeds, load_seeds_from_prior, load_seeds_for_map
from regularize_blocks import regularize
from seg_eval import window_score, load_run_records
from shapely.geometry import Polygon, MultiPolygon


class ComparisonTests(unittest.TestCase):
    def test_duplicates_and_wrong_classes_are_not_successes(self):
        square = Polygon([(0,0),(10,0),(10,10),(0,10)])
        result = window_score([('parcel', square)], [(square,'parcel'),(square,'parcel'),(square,'building')],
                              (0,0,20,20), .5)
        self.assertEqual(result['precision'], 1/3)
        self.assertEqual(result['recall'], 1)
        self.assertEqual(result['duplicate_candidates'], 1)

    def test_context_identity_and_area_units(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'context.json'
            path.write_text(json.dumps({'map_id':'map','source_size':[100,100],
                'target_feature_type':'parcel','mpp':.5,'min_area_m2':100,'max_area_m2':200}))
            context, digest = load_context(path, 'map', (100,100))
            self.assertEqual(mask_area_bounds(context,2,2),(100,200))
            self.assertEqual(len(digest),64)
            with self.assertRaises(ValueError): load_context(path, 'different-map', (100,100))
            with self.assertRaises(ValueError): load_context(path, 'map', (200,200))

    def test_metadata_legend_remains_a_review_suggestion(self):
        rgb=np.full((10,10,3),[200,100,100],np.uint8)
        suggestion=legend_suggestion(rgb,np.ones((10,10),bool),{'legend':[{'category':'private','rgb':[200,100,100]}]})
        self.assertTrue(suggestion['review_required'])
        self.assertEqual(suggestion['category'],'private')

    def test_memory_gate_and_diversity(self):
        bank=DiverseMemoryBank(2,1,.8)
        entry=lambda key, confidence: MemoryEntry(np.array(key),None,None,confidence)
        self.assertFalse(bank.add(entry([1,0],.5)))
        bank.add(entry([1,0],.9)); bank.add(entry([0,1],.9))
        self.assertFalse(bank.add(entry([1,0],.8)))
        self.assertTrue(bank.add(entry([1,0],.99)))
        self.assertEqual(bank.retrieve([1,0])[0].confidence,.99)

    def test_regularization_keeps_holes_and_components(self):
        first=Polygon([(0,0),(100,0),(100,100),(0,100)], [[(20,20),(40,20),(40,40),(20,40)]])
        second=Polygon([(200,0),(250,0),(250,50),(200,50)])
        result,_=regularize(MultiPolygon([first,second]))
        self.assertEqual(len(result.geoms),2)
        self.assertEqual(sum(len(p.interiors) for p in result.geoms),1)
        self.assertTrue(result.is_valid)

    def test_geojson_reader_keeps_holes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'candidate.geojson'
            path.write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature',
                'properties':{'feature_type':'parcel'},'geometry':{'type':'Polygon','coordinates':[
                [[0,0],[100,0],[100,100],[0,100],[0,0]],[[20,20],[40,20],[40,40],[20,40],[20,20]] ]}}]}))
            records=load_run_records(path)
            self.assertEqual(len(records[0][0].interiors),1)
            self.assertEqual(records[0][1],'parcel')

    def test_mask_components_are_closed_and_not_silently_dropped(self):
        mask=np.zeros((150,150),np.uint8)
        mask[10:50,10:50]=1; mask[90:130,90:130]=1
        parts=masks_to_polygons([mask],[.95])
        self.assertEqual(len(parts),2)
        self.assertTrue(all(p.coords[0]==p.coords[-1] for p in parts))

    def test_mask_converter_retains_large_closed_holes(self):
        mask=np.zeros((150,150),np.uint8); mask[10:140,10:140]=1; mask[50:100,50:100]=0
        parts=masks_to_polygons([mask],[.95])
        self.assertEqual(len(parts),1)
        self.assertEqual(len(parts[0].holes),1)
        self.assertEqual(parts[0].holes[0][0],parts[0].holes[0][-1])

    def test_no_live_crop_prior_and_interior_point(self):
        # The bbox centre is outside this L-shaped block. A positive point
        # belongs inside the object, and an offline prior must never query DB.
        polygon=Polygon([(0,0),(100,0),(100,20),(20,20),(20,100),(0,100)])
        feature={'type':'Feature','properties':{'feature_type':'parcel'},
                 'geometry':{'type':'Polygon','coordinates':[list(polygon.exterior.coords)]}}
        from shapely.geometry import Point
        seed=blocks_to_seeds([feature])[0]
        self.assertTrue(polygon.contains(Point(seed['centroid'])))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'prior.geojson'
            path.write_text(json.dumps({'crs':'source-pixels-y-down','features':[feature]}))
            with patch('to_sam2_seeds.fetch_tiling_crop',side_effect=AssertionError('Unexpected live query')):
                self.assertEqual(len(load_seeds_from_prior(path,'map',resolve_crop=False)),1)

    def test_ocr_prompt_loader_still_resolves_saved_crop(self):
        with patch.dict(os.environ,{'PUBLIC_SUPABASE_URL':'https://example.invalid','PUBLIC_SUPABASE_ANON_KEY':'test'}):
            with patch('requests.get') as request, patch('to_sam2_seeds.fetch_tiling_crop',return_value=None) as crop:
                request.return_value.json.return_value=[]
                self.assertEqual(load_seeds_for_map('map'),[])
                crop.assert_called_once_with('map')

    def test_coarse_tile_scale_and_input_provenance(self):
        from PIL import Image
        import inference_tiles_as_video as inference
        from masks_to_polygons import PolygonResult
        class Model: pass
        model=Model()
        polygon=PolygonResult([[1,1],[20,1],[20,20],[1,20],[1,1]],361,.9)
        image=Image.new('RGB',(512,256),'white')
        with patch.object(inference,'fetch_crop',return_value=image) as fetch, \
             patch.object(inference,'_run_prompted',return_value=[polygon]):
            result=inference.infer_tile(model,'https://example.invalid',(100,200,2048,1024),[{}],'prompted',render_size=512)
        fetch.assert_called_once_with('https://example.invalid',100,200,2048,1024,size=512)
        self.assertEqual(result[0].coords[0],[104,204])
        self.assertEqual(result[0].area,361*16)
        self.assertEqual(model.tile_manifest[0]['render_size'],[512,256])
        self.assertEqual(len(model.tile_manifest[0]['rgb_sha256']),64)

    @unittest.skipUnless(os.environ.get('SAM2_SOURCE_DIR'),'Set SAM2_SOURCE_DIR for the real model smoke')
    def test_real_model_uses_memory_between_tiles(self):
        sys.path.insert(0, os.environ['SAM2_SOURCE_DIR'])
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        torch.set_num_threads(2)
        model=build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml',None,device='cpu')
        predictor=MemoryImagePredictor(SAM2ImagePredictor(model),2,1)
        image=np.full((128,128,3),200,np.uint8); image[30:90,30:90]=90
        predictor.set_image(image)
        mask=np.zeros((128,128),bool); mask[30:90,30:90]=True
        predictor.remember_mask(mask,.99); predictor.finish_tile()
        predictor.set_image(np.flip(image,axis=1).copy())
        masks,scores,_=predictor.predict(box=np.array([20,20,100,100]),multimask_output=True)
        self.assertEqual(masks.shape,(3,128,128)); self.assertTrue(np.isfinite(scores).all())
        self.assertEqual(predictor.stats['conditioned_tiles'],1)


if __name__ == '__main__': unittest.main()
