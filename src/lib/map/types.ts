import type { FeatureCollection, GeoJsonObject } from 'geojson';

// UI-only map types. Canonical map data types live in $lib/data/maps/types.

export type ViewMode = 'overlay' | 'spy' | 'dual';
export type DrawingMode = 'point' | 'line' | 'polygon';

export interface AnnotationSummary {
  id: string;
  label: string;
  type: string;
  color: string;
  details?: string;
  hidden: boolean;
}

export interface SearchResult {
  display_name: string;
  lon: string;
  lat: string;
  type?: string;
  geojson?: GeoJsonObject;
}

export interface AnnotationSet {
  id: string;
  title: string;
  mapId: string;
  /** Every map in this project's layer stack (mapId is the first/primary one). */
  mapIds: string[];
  authorId: string;
  features: FeatureCollection;
  isPublic: boolean;
  createdAt: number;
  updatedAt: number;
}
