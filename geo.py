"""직선거리 계산. 경로시간이나 통근 가능성을 의미하지 않는다."""
from math import radians, sin, cos, atan2, sqrt

def distance_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    a = min(1.0, max(0.0, a))
    return 6371008.8 * 2 * atan2(sqrt(a), sqrt(1-a))

def stations_within(stations, latitude, longitude, radius_km):
    result = []
    for station in stations:
        distance = distance_m(latitude, longitude, station["latitude"], station["longitude"])
        if distance <= radius_km * 1000:
            result.append({**station, "distance_m": round(distance)})
    return sorted(result, key=lambda x: (x["distance_m"], x["id"]))
