import requests
import geopandas as gpd
# import pandas as pd


VALHALLA_URL = "http://localhost:8002"

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
    r = requests.post(f"{VALHALLA_URL}/sources_to_targets", json=body, timeout=60)
    r.raise_for_status()
    data = r.json()["sources_to_targets"]
    return [
        [round(cell["time"] / 60, 1) if cell.get("time") is not None else None for cell in row]
        for row in data
    ]


def get_min_travel_times_batched(origins, destinations, batch_size=50, costing="auto"):
    """
    Chunks origins into batches to stay under Valhalla's matrix size limits.
    Returns a flat list: min travel time per origin, in original order.
    """
    results = []
    for i in range(0, len(origins), batch_size):
        chunk = origins[i:i + batch_size]
        print(f"  batch {i // batch_size + 1}: origins {i}-{i + len(chunk)}")
        matrix = get_travel_time_matrix(chunk, destinations, costing=costing)
        for row in matrix:
            valid = [t for t in row if t is not None]
            results.append(min(valid) if valid else None)
    return results


def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf, batch_size=50):
    """
    census_gdf:    The GDF containing ORP/census data
    emergency_gdf: The GDF of Emergency care points
    maternity_gdf: The GDF of Maternity care points

    Instead of downloading a road network like Pandana,
    this version sends routing requests to Valhalla running locally in Docker.
    Returns travel time in minutes instead of distance in metres.
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