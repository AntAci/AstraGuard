#!/usr/bin/env python3
"""Spatial hashing for conjunction candidate generation."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Iterable, List, Tuple

import numpy as np


_NEIGHBOR_OFFSETS = [
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
]


def candidate_pairs_by_timestep(positions_km: np.ndarray, voxel_km: float) -> Iterable[Tuple[int, List[Tuple[int, int]]]]:
    if voxel_km <= 0:
        raise ValueError("voxel_km must be > 0")

    timesteps = int(positions_km.shape[0])
    objects = int(positions_km.shape[1]) if positions_km.ndim >= 2 else 0

    output: List[Tuple[int, List[Tuple[int, int]]]] = []
    total_pairs = 0
    max_pairs = 0

    for t_idx in range(timesteps):
        voxel_map: DefaultDict[Tuple[int, int, int], List[int]] = defaultdict(list)
        coords = positions_km[t_idx]
        voxels = np.floor(coords / float(voxel_km)).astype(np.int64)

        for obj_idx in range(objects):
            key = (int(voxels[obj_idx, 0]), int(voxels[obj_idx, 1]), int(voxels[obj_idx, 2]))
            voxel_map[key].append(obj_idx)

        pair_set = set()
        for key, idxs in voxel_map.items():
            for dx, dy, dz in _NEIGHBOR_OFFSETS:
                nkey = (key[0] + dx, key[1] + dy, key[2] + dz)
                nidxs = voxel_map.get(nkey)
                if not nidxs:
                    continue
                for i in idxs:
                    for j in nidxs:
                        if i >= j:
                            continue
                        pair_set.add((i, j))

        pairs = sorted(pair_set)
        output.append((t_idx, pairs))
        pair_count = len(pairs)
        total_pairs += pair_count
        if pair_count > max_pairs:
            max_pairs = pair_count

    avg_pairs = float(total_pairs) / float(timesteps) if timesteps else 0.0
    print(
        "[INFO] Candidate generation summary: "
        f"timesteps={timesteps}, total_pairs={total_pairs}, "
        f"avg_pairs_per_timestep={avg_pairs:.2f}, max_pairs_per_timestep={max_pairs}"
    )

    return output
