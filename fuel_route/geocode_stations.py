"""
One-time geocoding script to produce fuel_prices_geocoded.csv
Uses geopy Nominatim with 1s rate limit. Run once, commit the output.
Usage: python geocode_stations.py
"""

import csv
import time
import os
import json

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

INPUT_CSV  = "routes/data/fuel_prices.csv"
OUTPUT_CSV = "routes/data/fuel_prices_geocoded.csv"
CACHE_FILE = "routes/data/geocode_cache.json"

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def geocode_city(geolocator, city, state, cache):
    key = f"{city.strip()},{state.strip()}"
    if key in cache:
        return cache[key]

    state_name = STATE_NAMES.get(state.strip(), state.strip())
    # Skip non-US entries (e.g., AB = Alberta, Canada)
    if state.strip() not in STATE_NAMES:
        cache[key] = None
        return None

    query = f"{city.strip()}, {state_name}, USA"
    try:
        location = geolocator.geocode(query, timeout=10)
        time.sleep(1.1)  # Nominatim 1 req/sec policy
        if location:
            result = {"lat": location.latitude, "lng": location.longitude}
        else:
            result = None
        cache[key] = result
        save_cache(cache)
        return result
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"  Error geocoding {query}: {e}")
        time.sleep(2)
        return None

def main():
    print("Loading raw CSV...")
    rows = []
    with open(INPUT_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"  {len(rows)} rows loaded")

    # Deduplicate: group by (Truckstop Name, City, State) → keep min price
    stations = {}
    for row in rows:
        name  = row["Truckstop Name"].strip()
        city  = row["City"].strip()
        state = row["State"].strip()
        try:
            price = float(row["Retail Price"])
        except ValueError:
            continue
        key = (name, city, state)
        if key not in stations or price < stations[key]["price"]:
            stations[key] = {
                "name": name,
                "city": city,
                "state": state,
                "price": price,
            }

    print(f"  {len(stations)} unique stations after dedup")

    # Get unique (city, state) pairs to geocode
    city_state_pairs = set((v["city"], v["state"]) for v in stations.values())
    print(f"  {len(city_state_pairs)} unique city/state pairs to geocode")

    cache = load_cache()
    already_cached = sum(1 for (c,s) in city_state_pairs if f"{c},{s}" in cache)
    print(f"  {already_cached} already in cache, {len(city_state_pairs)-already_cached} need geocoding")

    geolocator = Nominatim(user_agent="fuel_route_geocoder_v1")

    total = len(city_state_pairs)
    for i, (city, state) in enumerate(sorted(city_state_pairs)):
        key = f"{city},{state}"
        if key not in cache:
            print(f"  [{i+1}/{total}] Geocoding {city}, {state}...")
            geocode_city(geolocator, city, state, cache)

    # Write output CSV
    print(f"\nWriting {OUTPUT_CSV}...")
    count = 0
    with open(OUTPUT_CSV, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["name", "city", "state", "lat", "lng", "price"])
        writer.writeheader()
        for (name, city, state), data in stations.items():
            key = f"{city},{state}"
            coords = cache.get(key)
            if coords is None:
                continue  # skip stations we couldn't geocode
            writer.writerow({
                "name": data["name"],
                "city": city,
                "state": state,
                "lat": coords["lat"],
                "lng": coords["lng"],
                "price": data["price"],
            })
            count += 1

    print(f"Done! Wrote {count} geocoded stations to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
