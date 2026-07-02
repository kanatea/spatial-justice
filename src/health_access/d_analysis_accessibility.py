import requests
import geopandas as gpd
import time

VALHALLA_URL = "http://localhost:8002"

"""
Calculates travel time matrices using the Valhalla routing engine.
Instead of downloading a road network like Pandana,
this version sends routing requests to Valhalla running locally in Docker.
Returns travel time in minutes instead of distance in metres.
"""

def get_travel_time_matrix(origins, destinations, costing="auto"):
    """
    origins/destinations: list of (lat, lon) tuples.
    Returns times[i][j] = minutes from origin i to destination j (None if unreachable).
    """
    body = {
        "sources": [{"lat": lat, "lon": lon} for lat, lon in origins],
        "targets": [{"lat": lat, "lon": lon} for lat, lon in destinations],
        "costing": costing,
    }
    r = requests.post(f"{VALHALLA_URL}/sources_to_targets", json=body, timeout=120) # I had to rise the timeout to 120 seconds for large batches, otherwise Valhalla would time out and return an error.
    if r.status_code != 200:
        print("Valhalla error response:", r.text)
    r.raise_for_status()
    data = r.json()["sources_to_targets"]
    return [
        [round(cell["time"] / 60, 1) if cell.get("time") is not None else None for cell in row]
        for row in data
    ]

def get_travel_time_matrix_safe(origins, destinations, costing="auto", max_retries=3):
    """
    Tries the batch - if Valhalla rejects it or times out, recursively splits origins
    in half until the offending pair is isolated (marked None) instead
    of failing the whole batch.
    HTTPError (400, e.g. distance-limit rejection) --> genuinely unroutable, split and isolate.
    ConnectionError/Timeout (server down/restarting) --> wait and retry, don't mark None.
    """
    for attempt in range(max_retries):
        try:
            return get_travel_time_matrix(origins, destinations, costing=costing)
        except requests.exceptions.HTTPError:
            if len(origins) == 1:
                print(f"  !! unroutable origin, marking None: {origins[0]}")
                return [[None] * len(destinations)]
            mid = len(origins) // 2
            left  = get_travel_time_matrix_safe(origins[:mid], destinations, costing)
            right = get_travel_time_matrix_safe(origins[mid:], destinations, costing)
            return left + right
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            wait = 10 * (attempt + 1)
            print(f"  !! server unavailable ({type(e).__name__}), waiting {wait}s and retrying... (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
        
    print(f"  !! giving up after {max_retries} retries for {len(origins)} origins — marking all None")
    return [[None] * len(destinations) for _ in origins]

def get_min_travel_times_batched(origins, destinations, batch_size=10, costing="auto", max_matrix_locations=2500):
    """
    Chunks origins into batches to stay under Valhalla's matrix size limits.
    Returns a flat list: min travel time per origin, in original order.
    """
    if batch_size is None:
        batch_size = max(1, max_matrix_locations // len(destinations)) # this ensures that we don't exceed the max matrix size and the system doesn't crash.
        print(f" auto batch_size = {batch_size} (destinations: {len(destinations)})")

    results = []
    for i in range(0, len(origins), batch_size):
        chunk = origins[i:i + batch_size]
        print(f"  batch {i // batch_size + 1}: origins {i}-{i + len(chunk)}")
        matrix = get_travel_time_matrix_safe(chunk, destinations, costing=costing)
        for row in matrix:
            valid = [t for t in row if t is not None]
            results.append(min(valid) if valid else None)
    return results


def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf, batch_size=10):
    """
    census_gdf:    The GDF containing ORP/census data
    emergency_gdf: The GDF of Emergency care points
    maternity_gdf: The GDF of Maternity care points
    """
    census_gdf = census_gdf.copy()
    # Centroid computed in metric CRS, then reprojected to WGS84 = more accurate than computing centroid in WGS84 directly
    centroids_wgs = census_gdf.geometry.centroid.to_crs("EPSG:4326")
    origins = [(pt.y, pt.x) for pt in centroids_wgs]

    emergency_wgs = emergency_gdf.to_crs("EPSG:4326")
    maternity_wgs = maternity_gdf.to_crs("EPSG:4326")
    em_dest  = [(pt.y, pt.x) for pt in emergency_wgs.geometry]
    mat_dest = [(pt.y, pt.x) for pt in maternity_wgs.geometry]

    print(f"Calculating travel times to {len(em_dest)} Emergency Care sites for {len(origins)} ORPs...")
    census_gdf["travel_time_emergency"] = get_min_travel_times_batched(origins, em_dest, batch_size)

    print(f"Calculating travel times to {len(mat_dest)} Maternity Care sites for {len(origins)} ORPs...")
    census_gdf["travel_time_maternity"] = get_min_travel_times_batched(origins, mat_dest, batch_size)

    return census_gdf