"""
Fast geocoding using pgeocode's offline Geonames data (no rate limits, runs in seconds).
Falls back to geopy Nominatim for cities not found in the offline database.

Usage: python geocode_stations_fast.py
"""

import csv
import json
import os
import sys
import time
import pgeocode
import numpy as np

INPUT_CSV  = "routes/data/fuel_prices.csv"
OUTPUT_CSV = "routes/data/fuel_prices_geocoded.csv"

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

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


def build_city_state_lookup(nomi):
    """
    Build a dict of (city_lower, state) -> (lat, lng) from pgeocode's US data.
    pgeocode provides zip-level data; we aggregate by city+state taking median coords.
    """
    print("Building city/state lookup from pgeocode Geonames data...")
    df = nomi._data  # Full DataFrame with postal_code, place_name, state_code, lat, lng
    df = df[['place_name', 'state_code', 'latitude', 'longitude']].dropna()
    
    # Group by (city, state) -> mean lat/lng
    grouped = df.groupby(['place_name', 'state_code'])[['latitude', 'longitude']].mean()
    
    lookup = {}
    for (place, state), row in grouped.iterrows():
        key = (place.strip().lower(), state.strip().upper())
        lookup[key] = (float(row['latitude']), float(row['longitude']))
    
    print(f"  Built lookup with {len(lookup)} entries")
    return lookup


def main():
    print("Loading raw CSV...")
    rows = []
    with open(INPUT_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"  {len(rows)} rows loaded")

    # Deduplicate: group by (name, city, state) -> keep min price
    # Then further deduplicate by (city, state) -> keep cheapest station
    stations_by_location = {}  # (city, state) -> min_price station
    for row in rows:
        name  = row["Truckstop Name"].strip()
        city  = row["City"].strip()
        state = row["State"].strip()
        if state not in US_STATES:
            continue  # skip non-US entries
        try:
            price = float(row["Retail Price"])
        except ValueError:
            continue
        key = (city, state)
        if key not in stations_by_location or price < stations_by_location[key]["price"]:
            stations_by_location[key] = {
                "name": name,
                "city": city,
                "state": state,
                "price": price,
            }

    print(f"  {len(stations_by_location)} unique (city, state) stations after dedup")

    # Load pgeocode offline data
    print("Loading pgeocode offline US Geonames data...")
    nomi = pgeocode.Nominatim('US')
    city_lookup = build_city_state_lookup(nomi)

    # Also attempt geopy for misses
    found = 0
    missed = 0
    missed_list = []
    results = []

    for (city, state), data in stations_by_location.items():
        city_lower = city.lower()
        coords = city_lookup.get((city_lower, state))
        
        if coords is None:
            # Try common variations
            # e.g. "Mount Vernon" might be stored as "Mt Vernon"
            for variant in [city_lower.replace("mount ", "mt "),
                            city_lower.replace("mt ", "mount "),
                            city_lower.replace(" city", ""),
                            city_lower.split(",")[0].strip()]:
                coords = city_lookup.get((variant, state))
                if coords:
                    break

        if coords:
            found += 1
            results.append({
                "name": data["name"],
                "city": city,
                "state": state,
                "lat": round(coords[0], 6),
                "lng": round(coords[1], 6),
                "price": data["price"],
            })
        else:
            missed += 1
            missed_list.append(f"{city}, {state}")

    print(f"\n  Found: {found}, Missed: {missed}")
    if missed_list[:10]:
        print(f"  First 10 misses: {', '.join(missed_list[:10])}")

    # For major misses, use geopy as fallback (rate limited, only for misses)
    if missed > 0:
        print(f"\n  Attempting geopy fallback for {missed} missed cities...")
        from geopy.geocoders import Nominatim as GeoNominatim
        from geopy.exc import GeocoderTimedOut

        geo = GeoNominatim(user_agent="fuel_route_geo_fallback")
        fallback_cache_file = "routes/data/geo_fallback_cache.json"
        fallback_cache = {}
        if os.path.exists(fallback_cache_file):
            with open(fallback_cache_file) as fc:
                fallback_cache = json.load(fc)

        fallback_found = 0
        for city_state_str in missed_list:
            city, state = city_state_str.rsplit(", ", 1)
            key = city_state_str
            if key in fallback_cache:
                coords_data = fallback_cache[key]
            else:
                try:
                    state_name = STATE_NAMES.get(state, state)
                    location = geo.geocode(f"{city}, {state_name}, USA", timeout=10)
                    time.sleep(1.1)
                    if location:
                        coords_data = {"lat": location.latitude, "lng": location.longitude}
                    else:
                        coords_data = None
                except GeocoderTimedOut:
                    coords_data = None
                fallback_cache[key] = coords_data
                with open(fallback_cache_file, "w") as fc:
                    json.dump(fallback_cache, fc)

            if coords_data:
                fallback_found += 1
                data = stations_by_location[(city.strip(), state.strip())]
                results.append({
                    "name": data["name"],
                    "city": city.strip(),
                    "state": state.strip(),
                    "lat": round(coords_data["lat"], 6),
                    "lng": round(coords_data["lng"], 6),
                    "price": data["price"],
                })

        print(f"  Fallback resolved: {fallback_found}/{missed}")

    # Write final geocoded CSV
    print(f"\nWriting {OUTPUT_CSV} with {len(results)} stations...")
    with open(OUTPUT_CSV, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["name", "city", "state", "lat", "lng", "price"])
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"Done! {len(results)} geocoded stations written.")


if __name__ == "__main__":
    main()
