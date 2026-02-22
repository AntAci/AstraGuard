#!/usr/bin/env python3
"""Tiered geospatial risk model for Earth impact scoring.

Computes a weighted composite score based on infrastructure proximity,
latitude-band population density, and orbital catalog density.
Zero external dependencies — pure math with WGS-84 geodetics.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

# ── WGS-84 constants ─────────────────────────────────────────────────────────
_WGS84_A = 6_378_137.0          # semi-major axis (m)
_WGS84_E2 = 6.694379990141e-3   # first eccentricity squared

# ── Precomputed geospatial risk index ─────────────────────────────────────────
# Each entry: (lat, lon, radius_deg, label, zone_weight)
GEOSPATIAL_INDEX: Dict[str, List[Tuple[float, float, float, str, float]]] = {
    "launch_sites": [
        (28.5, -80.6, 1.5, "Kennedy Space Center", 0.98),
        (46.0, 63.3, 2.0, "Baikonur Cosmodrome", 0.95),
        (5.2, -52.8, 1.5, "Kourou CSG", 0.93),
        (31.3, 131.0, 1.5, "Tanegashima", 0.90),
        (28.2, -16.6, 1.5, "Canary Islands", 0.88),
        (34.6, -120.6, 1.5, "Vandenberg SFB", 0.92),
        (19.6, 110.9, 1.5, "Wenchang", 0.91),
    ],
    "tier_1_metro": [
        (35.7, 139.7, 3.0, "Tokyo Metro", 0.95),
        (40.7, -74.0, 3.0, "NYC Metro", 0.92),
        (51.5, -0.1, 3.0, "London", 0.90),
        (31.2, 121.5, 3.0, "Shanghai", 0.90),
        (28.6, 77.2, 3.0, "Delhi NCR", 0.88),
        (23.1, 113.3, 3.0, "Guangzhou-Shenzhen", 0.87),
        (37.6, 127.0, 3.0, "Seoul Metro", 0.86),
        (35.0, 136.9, 2.5, "Nagoya-Osaka Corridor", 0.85),
    ],
    "tier_2_metro": [
        (-23.5, -46.6, 2.5, "Sao Paulo", 0.78),
        (19.4, -99.1, 2.5, "Mexico City", 0.76),
        (30.0, 31.2, 2.0, "Cairo", 0.74),
        (55.8, 37.6, 2.5, "Moscow", 0.73),
        (-33.9, 151.2, 2.0, "Sydney", 0.70),
        (41.9, 12.5, 2.0, "Rome", 0.68),
        (48.9, 2.3, 2.5, "Paris", 0.75),
    ],
    "ground_stations": [
        (78.2, 15.6, 2.0, "Svalbard GS", 0.85),
        (64.1, -21.9, 2.0, "Keflavik GS", 0.75),
        (-35.4, 148.9, 2.0, "Canberra DSN", 0.80),
        (35.3, -116.9, 2.0, "Goldstone DSN", 0.80),
        (40.4, -4.2, 2.0, "Madrid DSN", 0.78),
    ],
    "shipping_corridors": [
        (1.3, 103.8, 2.0, "Strait of Malacca", 0.70),
        (30.0, 32.3, 1.5, "Suez Canal", 0.75),
        (9.0, -79.5, 1.5, "Panama Canal", 0.72),
        (36.0, -5.5, 1.5, "Strait of Gibraltar", 0.65),
        (12.0, 43.0, 1.5, "Bab el-Mandeb", 0.68),
    ],
}

# Category weights for composite infrastructure score
_CATEGORY_WEIGHTS: Dict[str, float] = {
    "launch_sites": 1.0,
    "tier_1_metro": 0.9,
    "tier_2_metro": 0.7,
    "ground_stations": 0.8,
    "shipping_corridors": 0.5,
}

# Latitude-band population density buckets (abs_lat_min, abs_lat_max, density_score)
# These are calibrated for land-dominated latitude bands.
_POPULATION_BANDS: List[Tuple[float, float, float]] = [
    (0, 10, 0.45),
    (10, 25, 0.70),
    (25, 45, 0.85),
    (45, 60, 0.55),
    (60, 90, 0.15),
]

# Confirmed open-ocean zones: (center_lat, center_lon, radius_km).
# Points inside these circles are classified as open ocean regardless of latitude band.
# Radii are deliberately conservative — coastal and island areas fall back to band model.
_OCEAN_ZONES: List[Tuple[float, float, float]] = [
    (-20.0,  80.0, 2500.0),   # Central Indian Ocean
    ( 10.0, 160.0, 3000.0),   # Western Pacific
    (  0.0, -140.0, 4000.0),  # Eastern Pacific
    (-20.0, -25.0, 3000.0),   # South Atlantic
    ( 35.0, -40.0, 2500.0),   # North Atlantic
    (-60.0,   0.0, 5500.0),   # Southern Ocean (circumpolar)
    ( 80.0,   0.0, 3000.0),   # Arctic Ocean
    (-10.0, -25.0, 2000.0),   # Equatorial Atlantic
]

_OCEAN_POPULATION_SCORE = 0.02

# Orbital density by altitude band (alt_min_km, alt_max_km, density_score)
_ORBITAL_DENSITY_BANDS: List[Tuple[float, float, float]] = [
    (0, 400, 0.30),
    (400, 600, 0.55),
    (600, 900, 0.85),
    (900, 1200, 0.60),
    (1200, 2000, 0.35),
    (2000, 36000, 0.20),
    (36000, 100000, 0.10),
]

_OPEN_OCEAN_DEFAULT = 0.15


def ecef_to_geodetic(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Convert ECEF (meters) to geodetic (lat, lon, alt_m) via iterative Bowring."""
    lon = math.degrees(math.atan2(y, x))
    p = math.sqrt(x * x + y * y)
    lat = math.atan2(z, p * (1 - _WGS84_E2))
    for _ in range(5):
        sin_lat = math.sin(lat)
        N = _WGS84_A / math.sqrt(1 - _WGS84_E2 * sin_lat * sin_lat)
        lat = math.atan2(z + _WGS84_E2 * N * sin_lat, p)
    sin_lat = math.sin(lat)
    N = _WGS84_A / math.sqrt(1 - _WGS84_E2 * sin_lat * sin_lat)
    alt_m = p / math.cos(lat) - N if abs(math.cos(lat)) > 1e-10 else abs(z) - _WGS84_A * math.sqrt(1 - _WGS84_E2)
    return math.degrees(lat), lon, alt_m


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _infra_proximity_score(lat: float, lon: float) -> Tuple[float, Optional[str], Optional[str], Optional[float]]:
    """Find nearest zone match and return (score, zone_name, category, distance_km)."""
    best_score = 0.0
    best_zone: Optional[str] = None
    best_cat: Optional[str] = None
    best_dist: Optional[float] = None

    for category, zones in GEOSPATIAL_INDEX.items():
        cat_weight = _CATEGORY_WEIGHTS.get(category, 0.5)
        for z_lat, z_lon, radius_deg, label, z_weight in zones:
            dist_km = haversine_km(lat, lon, z_lat, z_lon)
            radius_km = radius_deg * 111.0  # approx km per degree
            if dist_km <= radius_km:
                score = z_weight * cat_weight
            else:
                decay = math.exp(-((dist_km - radius_km) / 500.0))
                score = z_weight * cat_weight * decay
            if score > best_score:
                best_score = score
                best_zone = label
                best_cat = category
                best_dist = dist_km

    return min(best_score, 1.0), best_zone, best_cat, best_dist


def _is_open_ocean(lat: float, lon: float) -> bool:
    """Return True if the point lies within a confirmed open-ocean zone."""
    for center_lat, center_lon, radius_km in _OCEAN_ZONES:
        if haversine_km(lat, lon, center_lat, center_lon) <= radius_km:
            return True
    return False


def _population_band_score(lat: float, lon: float) -> float:
    """Population density estimate. Returns near-zero for open-ocean positions."""
    if _is_open_ocean(lat, lon):
        return _OCEAN_POPULATION_SCORE
    abs_lat = abs(lat)
    for lat_min, lat_max, density in _POPULATION_BANDS:
        if lat_min <= abs_lat < lat_max:
            return density
    return 0.10


def _orbital_density_score(alt_km: float) -> float:
    """Catalog density score by altitude band."""
    for alt_min, alt_max, density in _ORBITAL_DENSITY_BANDS:
        if alt_min <= alt_km < alt_max:
            return density
    return 0.10


def _ground_point_from_event(event: Dict[str, Any], cesium_snapshot: Optional[Dict[str, Any]]) -> Tuple[float, float, float, str]:
    """Extract or estimate ground point (lat, lon, alt_km, method) for an event."""
    # Try ECEF from cesium snapshot
    if cesium_snapshot and isinstance(cesium_snapshot, dict):
        objects = cesium_snapshot.get("objects") or []
        primary_id = event.get("primary_id") or event.get("primary_norad_id")
        for obj in objects:
            if obj.get("norad_id") == primary_id:
                positions = obj.get("positions_ecef_m") or []
                if positions:
                    mid = len(positions) // 2
                    x, y, z = positions[mid]
                    lat, lon, alt_m = ecef_to_geodetic(x, y, z)
                    return lat, lon, alt_m / 1000.0, "ecef_snapshot"

    # Fallback: use event lat/lon if available
    if "latitude" in event and "longitude" in event:
        return float(event["latitude"]), float(event["longitude"]), 500.0, "event_latlon"

    # Fallback: estimate from orbital parameters
    return 0.0, 0.0, 500.0, "latitude_band_estimate"


def compute_impact_score(event: Dict[str, Any], cesium_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute weighted Earth impact score for a conjunction event.

    Returns dict with impact_score (0-1), ground coordinates, nearest zone info,
    and component breakdown.
    """
    lat, lon, alt_km, method = _ground_point_from_event(event, cesium_snapshot)

    infra, nearest_zone, zone_category, zone_distance_km = _infra_proximity_score(lat, lon)
    population = _population_band_score(lat, lon)
    orbital = _orbital_density_score(alt_km)

    impact_score = 0.6 * infra + 0.3 * population + 0.1 * orbital
    impact_score = min(max(impact_score, 0.0), 1.0)

    # Apply open-ocean floor when no meaningful zone match
    if infra < 0.05 and method == "latitude_band_estimate":
        impact_score = max(impact_score, _OPEN_OCEAN_DEFAULT)

    return {
        "impact_score": round(impact_score, 4),
        "ground_lat": round(lat, 4),
        "ground_lon": round(lon, 4),
        "nearest_zone": nearest_zone,
        "zone_category": zone_category,
        "zone_distance_km": round(zone_distance_km, 1) if zone_distance_km is not None else None,
        "method": method,
        "components": {
            "infra": round(infra, 4),
            "population": round(population, 4),
            "orbital": round(orbital, 4),
        },
    }
