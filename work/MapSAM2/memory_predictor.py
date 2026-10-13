"""Prompted SAM2 with a confidence-gated, diverse cross-tile memory bank.

Uses the SAM2 memory encoder/attention, following MapSAM2's image path. Unlike
the paper's semantic decoder, VMA keeps explicit instance prompts. Retrieval is
deterministic top-k cosine similarity for reproducible ablations, not stochastic
sampling. Memory is scoped to a single map/target/context and reset per run.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
import numpy as np


@dataclass
class MemoryEntry:
    key: np.ndarray
    features: object
    position: object
    confidence: float


class DiverseMemoryBank:
    def __init__(self, capacity=8, retrieval_k=3, min_confidence=0.85):
        if capacity < 1 or not 1 <= retrieval_k <= capacity or not 0 <= min_confidence <= 1:
            raise ValueError("Invalid memory capacity/retrieval/confidence")
        self.capacity, self.retrieval_k, self.min_confidence = capacity, retrieval_k, min_confidence
        self.entries: list[MemoryEntry] = []

    @staticmethod
    def normalized(key):
        key = np.asarray(key, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(key))
        if not np.isfinite(key).all() or norm <= 0:
            raise ValueError("Memory keys must be finite and nonzero")
        return key / norm

    def retrieve(self, key):
        key = self.normalized(key)
        ranked = sorted(enumerate(self.entries), key=lambda pair: (-float(pair[1].key @ key), pair[0]))
        return [entry for _, entry in ranked[:self.retrieval_k]]

    def add(self, entry):
        if not np.isfinite(entry.confidence) or entry.confidence < self.min_confidence:
            return False
        entry.key = self.normalized(entry.key)
        if self.entries and entry.key.shape != self.entries[0].key.shape:
            raise ValueError("Memory feature shape changed between tiles")
        candidates = [*self.entries, entry]
        if len(candidates) <= self.capacity:
            self.entries = candidates
            return True
        # Keep the subset with maximum total pairwise dissimilarity. Confidence
        # breaks diversity ties, so redundant high-confidence examples may replace
        # weaker ones while low-confidence novel noise cannot enter the bank.
        keys = np.stack([item.key for item in candidates])
        distances = 1 - keys @ keys.T
        scores = [(float(distances[np.ix_([j for j in range(len(candidates)) if j != i],
                                        [j for j in range(len(candidates)) if j != i])].sum()),
                   sum(c.confidence for j, c in enumerate(candidates) if j != i), -i)
                  for i in range(len(candidates))]
        drop = max(range(len(candidates)), key=lambda i: scores[i])
        self.entries = [c for i, c in enumerate(candidates) if i != drop]
        return drop != len(candidates) - 1


class MemoryImagePredictor:
    """A small adapter around SAM2ImagePredictor's prompt/coordinate machinery."""
    def __init__(self, predictor, capacity=8, retrieval_k=3, min_confidence=0.85):
        self.predictor = predictor
        self.bank = DiverseMemoryBank(capacity, retrieval_k, min_confidence)
        self.stats = {"tiles": 0, "conditioned_tiles": 0, "accepted_memories": 0}
        self._raw = self._positions = self._sizes = self._key = None
        self._masks, self._scores = [], []

    def set_image(self, image):
        import torch
        p, model = self.predictor, self.predictor.model
        self._masks, self._scores = [], []
        with torch.inference_mode():
            p.reset_predictor()
            p._orig_hw = [image.shape[:2]]
            transformed = p._transforms(image)[None].to(p.device)
            _, raw, positions, sizes = model._prepare_backbone_features(model.forward_image(transformed))
            self._raw = raw
            self._positions, self._sizes = positions, sizes
            self._key = raw[-1].permute(1, 0, 2).flatten().float().cpu().numpy()
            memories = self.bank.retrieve(self._key)
            conditioned = list(raw)
            if memories:
                device, dtype = raw[-1].device, raw[-1].dtype
                features = torch.cat([m.features.to(device=device, dtype=dtype).flatten(2).permute(2, 0, 1)
                                      for m in memories], dim=0)
                positional = torch.cat([m.position.to(device=device, dtype=dtype).flatten(2).permute(2, 0, 1)
                                        for m in memories], dim=0)
                conditioned[-1] = model.memory_attention(curr=[raw[-1]], curr_pos=[positions[-1]],
                    memory=features, memory_pos=positional, num_obj_ptr_tokens=0)
                self.stats["conditioned_tiles"] += 1
            elif model.directly_add_no_mem_embed:
                conditioned[-1] = raw[-1] + model.no_mem_embed
            feats = [feat.permute(1, 2, 0).reshape(1, -1, *size)
                     for feat, size in zip(conditioned, sizes)]
            p._features = {"image_embed": feats[-1], "high_res_feats": feats[:-1]}
            p._is_image_set = True
            self.stats["tiles"] += 1

    def predict(self, **kwargs):
        return self.predictor.predict(**kwargs)

    def remember_mask(self, mask, confidence):
        # A union of confident instances represents the target class on a tile;
        # never let a bad prompt poison the memory for subsequent tiles.
        if np.isfinite(confidence) and confidence >= self.bank.min_confidence and np.asarray(mask).any():
            self._masks.append(np.asarray(mask, dtype=bool))
            self._scores.append(float(confidence))

    def finish_tile(self):
        import torch
        import torch.nn.functional as F
        if not self._masks:
            return
        model = self.predictor.model
        with torch.inference_mode():
            union = np.logical_or.reduce(self._masks)
            mask = torch.as_tensor(union, device=model.device, dtype=torch.float32)[None, None]
            mask = F.interpolate(mask, size=(model.image_size, model.image_size), mode="nearest")
            # _encode_new_memory expects raw logits, not a uint8/binary mask.
            logits = torch.where(mask > 0, 10.0, -10.0)
            kwargs = dict(current_vision_feats=self._raw, feat_sizes=self._sizes,
                          pred_masks_high_res=logits, is_mask_from_pts=False)
            # SAM2.1 adds object-presence conditioning; the vendored older API
            # has no such argument. Check the signature instead of catching a
            # TypeError that could hide an unrelated model failure.
            if "object_score_logits" in inspect.signature(model._encode_new_memory).parameters:
                kwargs["object_score_logits"] = logits.new_full((1, 1), 10)
            features, positions = model._encode_new_memory(**kwargs)
            accepted = self.bank.add(MemoryEntry(self._key, features.detach().float().cpu(),
                positions[-1].detach().float().cpu(), min(self._scores)))
            self.stats["accepted_memories"] += int(accepted)
        self._masks, self._scores = [], []


def self_check():
    bank = DiverseMemoryBank(2, 1, 0.8)
    entry = lambda key, score: MemoryEntry(np.asarray(key), None, None, score)
    assert not bank.add(entry([1, 0], 0.1))
    assert bank.add(entry([1, 0], 0.9))
    assert bank.add(entry([0, 1], 0.9))
    assert not bank.add(entry([1, 0], 0.8))
    assert bank.add(entry([1, 0], 0.95))
    assert bank.retrieve([1, 0])[0].confidence == 0.95
    assert len(bank.entries) == 2
    print("memory bank self-check passed")


if __name__ == "__main__":
    self_check()
