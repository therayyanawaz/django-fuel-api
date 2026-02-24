import os
import math
import csv
from pathlib import Path
from django.core.cache import cache

MAX_RANGE_MILES = 500
MPG = 10

# Absolute path to geocoded CSV - works regardless of cwd
BASE_DATA_DIR = Path(__file__).resolve().parent / "data"
GEOCODED_CSV = BASE_DATA_DIR / "fuel_prices_geocoded.csv"


def load_fuel_stations():
    """
    Load geocoded fuel stations from CSV, with Django cache to avoid repeated disk reads.
    Returns a list of dicts: [{"name", "city", "state", "lat", "lng", "price"}, ...]
    """
    cached = cache.get("fuel_stations_list")
    if cached is not None:
        return cached

    stations = []
    with open(GEOCODED_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                stations.append({
                    "name":  row["name"].strip(),
                    "city":  row["city"].strip(),
                    "state": row["state"].strip(),
                    "lat":   float(row["lat"]),
                    "lng":   float(row["lng"]),
                    "price": float(row["price"]),
                })
            except (ValueError, KeyError):
                continue

    # Cache indefinitely (data never changes at runtime)
    cache.set("fuel_stations_list", stations, timeout=None)
    return stations


def build_kdtree(stations):
    """
    Build a scipy KDTree over station coordinates (in radians for haversine-like queries).
    Returns (tree, stations_array) — cached in Django cache.
    """
    from scipy.spatial import KDTree
    import numpy as np

    cached = cache.get("fuel_stations_kdtree")
    if cached is not None:
        return cached

    coords_rad = np.radians([[s["lat"], s["lng"]] for s in stations])
    tree = KDTree(coords_rad)
    result = (tree, coords_rad)
    cache.set("fuel_stations_kdtree", result, timeout=None)
    return result


def haversine(lat1, lon1, lat2, lon2):
    """Return distance in miles between two (lat, lon) points."""
    R = 3959.0  # Earth radius miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))