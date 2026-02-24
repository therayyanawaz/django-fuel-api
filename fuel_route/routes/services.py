import numpy as np

from .utils import (
    load_fuel_stations,
    build_kdtree,
    haversine,
    MAX_RANGE_MILES,
    MPG,
)

TANK_GALLONS        = MAX_RANGE_MILES / MPG
EARTH_RADIUS_MILES  = 3959.0
CORRIDOR_MILES      = 15.0
CORRIDOR_RAD        = CORRIDOR_MILES / EARTH_RADIUS_MILES
SAMPLE_EVERY_MILES  = 3.0
SAFETY_BUFFER_MILES = 20.0
MIN_GALLONS_TO_STOP = 5.0


def find_stations_along_route(geometry):
    stations = load_fuel_stations()
    tree, _  = build_kdtree(stations)

    found = {}
    cumulative_miles  = 0.0
    last_sampled_mile = -SAMPLE_EVERY_MILES

    for i in range(1, len(geometry)):
        lon1, lat1 = geometry[i - 1]
        lon2, lat2 = geometry[i]
        cumulative_miles += haversine(lat1, lon1, lat2, lon2)

        if cumulative_miles - last_sampled_mile < SAMPLE_EVERY_MILES:
            continue
        last_sampled_mile = cumulative_miles

        pt = np.radians([lat2, lon2])
        for idx in tree.query_ball_point(pt, r=CORRIDOR_RAD):
            if idx not in found:
                found[idx] = cumulative_miles

    result = [{**stations[idx], "route_mile": rm} for idx, rm in found.items()]
    result.sort(key=lambda s: s["route_mile"])
    return result


def optimize_fuel_stops(stations_along_route, total_distance):
    current_fuel_miles = MAX_RANGE_MILES
    last_position      = 0.0
    stops              = []

    for i, station in enumerate(stations_along_route):
        rm = station["route_mile"]

        leg = rm - last_position
        if leg > current_fuel_miles + 0.1:
            break
        current_fuel_miles -= leg
        last_position = rm

        if current_fuel_miles >= total_distance - rm:
            continue

        next_stations = stations_along_route[i + 1:]

        if not any(s["route_mile"] - rm <= current_fuel_miles for s in next_stations):
            fill_miles = MAX_RANGE_MILES - current_fuel_miles
            gallons    = fill_miles / MPG
            current_fuel_miles = MAX_RANGE_MILES
            _append_stop(stops, station, rm, gallons,
                         "must_stop_last_reachable_station", current_fuel_miles)
            continue

        reachable = [s for s in next_stations
                     if s["route_mile"] - rm <= current_fuel_miles - SAFETY_BUFFER_MILES]

        cheapest_ahead = min(reachable, key=lambda s: s["price"]) if reachable else None

        if cheapest_ahead is None or station["price"] <= cheapest_ahead["price"]:
            fill_miles = MAX_RANGE_MILES - current_fuel_miles
            gallons    = fill_miles / MPG
            if gallons < MIN_GALLONS_TO_STOP:
                continue
            current_fuel_miles = MAX_RANGE_MILES
            _append_stop(stops, station, rm, gallons,
                         "cheapest_in_range_fill_up", current_fuel_miles)
            continue

        dist_to_cheapest = cheapest_ahead["route_mile"] - rm
        needed           = dist_to_cheapest + SAFETY_BUFFER_MILES
        if current_fuel_miles >= needed:
            continue

        fill_miles = needed - current_fuel_miles
        gallons    = fill_miles / MPG
        if gallons < MIN_GALLONS_TO_STOP:
            continue
        current_fuel_miles += fill_miles
        reason = (
            f"partial_fill_to_reach_cheaper_station"
            f" ({cheapest_ahead['city']}, {cheapest_ahead['state']}"
            f" @ ${cheapest_ahead['price']:.3f}/gal)"
        )
        _append_stop(stops, station, rm, gallons, reason, current_fuel_miles)

    return stops


def _append_stop(stops, station, route_mile, gallons, reason, tank_after_miles):
    fuel_cost = gallons * station["price"]
    stops.append({
        "name":              station["name"],
        "city":              station["city"],
        "state":             station["state"],
        "lat":               station["lat"],
        "lng":               station["lng"],
        "price_per_gallon":  round(station["price"], 3),
        "stop_at_mile":      round(route_mile, 1),
        "gallons_purchased": round(gallons, 2),
        "fuel_cost_at_stop": round(fuel_cost, 2),
        "tank_range_after":  round(tank_after_miles, 1),
        "stop_reason":       reason,
    })


def calculate_total_cost(fuel_stops, total_distance_miles):
    total_gallons_bought = sum(s["gallons_purchased"] for s in fuel_stops)
    total_cost           = sum(s["fuel_cost_at_stop"]  for s in fuel_stops)
    expected_gallons     = total_distance_miles / MPG

    return {
        "total_cost_usd":       round(total_cost, 2),
        "total_gallons_used":   round(expected_gallons, 2),
        "total_gallons_bought": round(total_gallons_bought, 2),
        "avg_price_per_gallon": round(total_cost / total_gallons_bought, 3)
                                if total_gallons_bought else 0,
    }