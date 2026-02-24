import os
import hashlib
import requests
import polyline

from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.cache import cache
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from .services import (
    find_stations_along_route,
    optimize_fuel_stops,
    calculate_total_cost,
)

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

_geolocator = Nominatim(user_agent="fuel_route_api_v1")


def geocode_address(address: str):
    cache_key = "geocode_" + hashlib.md5(address.lower().encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        location = _geolocator.geocode(address + ", USA", exactly_one=True, timeout=10)
    except (GeocoderTimedOut, GeocoderServiceError):
        return None

    if not location:
        return None

    result = [location.longitude, location.latitude]
    cache.set(cache_key, result, timeout=86400 * 7)
    return result


class FuelRouteAPIView(APIView):

    def post(self, request):
        start_str = request.data.get("start", "").strip()
        end_str   = request.data.get("end",   "").strip()

        if not start_str or not end_str:
            return Response(
                {"error": "'start' and 'end' location strings are required."},
                status=400,
            )

        route_cache_key = "route_" + hashlib.md5(
            f"{start_str.lower()}|{end_str.lower()}".encode()
        ).hexdigest()
        cached_response = cache.get(route_cache_key)
        if cached_response is not None:
            return Response({**cached_response, "cached": True})

        start_coords = geocode_address(start_str)
        if not start_coords:
            return Response(
                {"error": f"Could not geocode start: '{start_str}'"},
                status=400,
            )
        end_coords = geocode_address(end_str)
        if not end_coords:
            return Response(
                {"error": f"Could not geocode end: '{end_str}'"},
                status=400,
            )

        headers = {
            "Authorization": os.getenv("ORS_API_KEY", ""),
            "Content-Type":  "application/json",
        }
        body = {"coordinates": [start_coords, end_coords]}

        try:
            ors_resp   = requests.post(ORS_DIRECTIONS_URL, json=body, headers=headers, timeout=30)
            route_data = ors_resp.json()
        except requests.RequestException as e:
            return Response({"error": "Routing API failed.", "detail": str(e)}, status=502)

        if "routes" not in route_data:
            return Response({"error": "Routing API error.", "detail": route_data}, status=400)

        route = route_data["routes"][0]

        distance_miles = route["summary"]["distance"] / 1609.344
        decoded        = polyline.decode(route["geometry"])
        geometry       = [[lng, lat] for lat, lng in decoded]

        stations_on_route = find_stations_along_route(geometry)
        fuel_stops        = optimize_fuel_stops(stations_on_route, distance_miles)
        cost_summary      = calculate_total_cost(fuel_stops, distance_miles)

        response_body = {
            "start":          start_str,
            "end":            end_str,
            "distance_miles": round(distance_miles, 2),
            "fuel_stops":     fuel_stops,
            "cost_summary":   cost_summary,
            "route_geometry": geometry,
            "cached":         False,
        }

        cache.set(route_cache_key, response_body, timeout=3600)
        return Response(response_body)