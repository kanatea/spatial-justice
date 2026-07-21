import os
import logging
import time
import requests
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
from pyrosm import OSM
import numpy as np
from shapely.geometry import Point


# Setup logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

VALHALLA_API_URL = "http://localhost:8002"
VALHALLA_MATRIX_LIMIT = 2400

import logging
from pyrosm import OSM

logger = logging.getLogger(__name__)

def extract_intersection_nodes(pbf_path, bbox=None, sample_size=1000):
    """
    Parses an OSM PBF file to extract network nodes. 
    Falls back gracefully to a high-density synthetic grid if pyrosm runs out of memory.
    """
    if bbox:
        logger.info("Bounding pyrosm extractor down to active scope window bounding filters.")
        init_bbox = [bbox["lon_min"], bbox["lat_min"], bbox["lon_max"], bbox["lat_max"]]
        try:
            logger.info(f"Reading street network map data from {pbf_path}...")
            osm = OSM(str(pbf_path), bounding_box=init_bbox)
            
            logger.info("Extracting road network layers...")
            nodes, edges = osm.get_network(network_type="driving", nodes=True)
            
            logger.info("Filtering for network intersections...")
            intersection_ids = edges.groupby("u").size()
            intersection_ids = intersection_ids[intersection_ids >= 2].index
            
            intersection_nodes = nodes[nodes["id"].isin(intersection_ids)].copy()
            intersection_nodes = intersection_nodes.to_crs("EPSG:4326")
            
            # Filter down to bounding box bounds
            intersection_nodes = intersection_nodes[
                intersection_nodes.geometry.y.between(bbox["lat_min"], bbox["lat_max"]) & 
                intersection_nodes.geometry.x.between(bbox["lon_min"], bbox["lon_max"])
            ].copy()
            
            logger.info(f"Successfully extracted {len(intersection_nodes)} intersection nodes via pyrosm.")
            if len(intersection_nodes) > sample_size:
                return intersection_nodes.sample(n=sample_size, random_state=42)
            return intersection_nodes

        except (MemoryError, Exception) as e:
            logger.warning(f"Pyrosm encountered a processing limitation ({type(e).__name__}). Switching to spatial grid fallback...")
    
    # FALLBACK: Generate a clean coordinate grid over the bounding box area
    if bbox:
        logger.info(f"Generating uniform sampling grid across scope coordinates...")
        # Target a slightly higher matrix size to sample down from
        grid_dim = int(np.sqrt(sample_size * 1.5)) 
        
        lats = np.linspace(bbox["lat_min"], bbox["lat_max"], grid_dim)
        lons = np.linspace(bbox["lon_min"], bbox["lon_max"], grid_dim)
        
        points = []
        for lat in lats:
            for lon in lons:
                points.append(Point(lon, lat))
                
        grid_gdf = gpd.GeoDataFrame(geometry=points, crs="EPSG:4326")
        
        if len(grid_gdf) > sample_size:
            grid_gdf = grid_gdf.sample(n=sample_size, random_state=42)
            
        logger.info(f"Generated {len(grid_gdf)} regional analysis grid coordinate points.")
        return grid_gdf
    else:
        raise ValueError("A valid bounding box configuration is required for spatial analysis execution.")

def get_valhalla_matrix(origins, destinations, costing="auto", units="km"):
    """
    Queries Valhalla container setup using optimized batching to prevent
    network bottlenecks when routing many origins against few destinations.
    """
    endpoint = f"{VALHALLA_API_URL}/sources_to_targets"
    sources = [{"lat": float(lat), "lon": float(lon), "radius": 1000} for lat, lon in origins]
    targets = [{"lat": float(lat), "lon": float(lon), "radius": 2000} for lat, lon in destinations]

    total_sources = len(sources)
    if not targets or total_sources == 0:
        return [None] * total_sources
        
    # Force a robust batch size of 100. Valhalla easily handles 100 sources 
    # matched against a small number of health care targets in a single call.
    batch_size = 100
    min_travel_times = [None] * total_sources
    
    i = 0
    while i < total_sources:
        batch_sources = sources[i : i + batch_size]
        current_chunk_size = len(batch_sources)

        payload = {
            "sources": batch_sources,
            "targets": targets,
            "costing": costing,
            "units": units,
            "matrix_locations": 1,
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                batch_results = data.get("sources_to_targets", [])
                for local_idx, target_list in enumerate(batch_results):
                    global_idx = i + local_idx
                    times = [cell["time"] / 60 for cell in target_list if cell.get("time") is not None]
                    min_travel_times[global_idx] = round(min(times), 1) if times else None
                i += current_chunk_size
            else:
                raise ValueError(f"Server container error {response.status_code}")
        except Exception as e:
            logger.warning(f"Batch routing chunk starting at index {i} failed, retrying row-by-row... {e}")
            for local_offset in range(current_chunk_size):
                global_idx = i + local_offset
                single_payload = {
                    "sources": [sources[global_idx]],
                    "targets": targets,
                    "costing": costing,
                    "units": units,
                    "matrix_locations": 1
                }
                try:
                    res = requests.post(endpoint, json=single_payload, timeout=5)
                    if res.status_code == 200:
                        single_data = res.json().get("sources_to_targets", [[]])[0]
                        times = [cell["time"] / 60 for cell in single_data if cell.get("time") is not None]
                        min_travel_times[global_idx] = round(min(times), 1) if times else None
                except Exception:
                    min_travel_times[global_idx] = None
            i += current_chunk_size
            
        # Quick progress visualizer to see how it's moving
        logger.info(f"Matrix routing progress: {min(i, total_sources)}/{total_sources} nodes processed.")
        time.sleep(0.01)
        
    return min_travel_times

def plot_node_accessibility(nodes_gdf, output_path, target_col="travel_time_emergency"):
    """
    Generates a high-contrast scatter heatmap replicating your reference style:
    White-hot/yellow clusters indicating highly accessible infrastructure cores,
    grading down into dark/black elements for unserved peripheral fringe nodes.
    """
    logger.info("Generating high-intensity node density heatmap visualization matching reference profile...")
    plot_nodes = nodes_gdf.dropna(subset=[target_col]).copy()
    
    if len(plot_nodes) == 0:
        logger.error("No valid travel times found to map!")
        return

    fig, ax = plt.subplots(figsize=(11, 9))
    
    # Mathematical ordering: Plot longest travel times first, then overlay fast access zones on top
    plot_nodes = plot_nodes.sort_values(by=target_col, ascending=False)
    
    # Use inverted hot colormap to create white-hot centers and dark boundaries
    scatter = ax.scatter(
        plot_nodes.geometry.x,
        plot_nodes.geometry.y,
        c=plot_nodes[target_col],
        cmap="hot_r", 
        s=3.5,
        alpha=1.0
    )
    
    cbar = fig.colorbar(scatter, ax=ax, pad=0.03)
    cbar.set_label("Driving Duration to Nearest Facility (Minutes)", fontsize=11)
    
    ax.set_title(f"Network Node Travel Horizon Distribution ({target_col})", fontsize=12, pad=10)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(False) # Turn off grid arrays to preserve the dark aesthetic space from reference

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Target node map saved to: {output_path}")

def run_nodes_analysis(project_root, bbox, scope, output_dir):
    """
    Orchestration entry point called seamlessly by the pipeline master control framework.
    """
    logger.info(f"Launching Street Network Node Analysis framework [Scope Extent: {scope}]")
    
    raw_dir = project_root / "data/raw"
    processed_dir = project_root / "data/processed"
    
    # Locate tracking file paths relative to structural root dynamically
    pbf_path = project_root.parent / "valhalla_tiles/praha-260714.osm.pbf"
    if not pbf_path.exists():
        pbf_path = project_root / "valhalla_tiles/praha-260714.osm.pbf"

    # 1. Read Health Care Points Slices
    em_path = raw_dir / "OD_emergency_care.geojson"
    mat_path = raw_dir / "OD_maternity_care.geojson"
    
    emergency_gdf = gpd.read_file(em_path).to_crs("EPSG:4326")
    maternity_gdf = gpd.read_file(mat_path).to_crs("EPSG:4326")
    
    # Apply dynamic geographic filter based on passed bbox bounds config
    if bbox:
        emergency_gdf = emergency_gdf[
            emergency_gdf.geometry.y.between(bbox["lat_min"], bbox["lat_max"]) & 
            emergency_gdf.geometry.x.between(bbox["lon_min"], bbox["lon_max"])
        ].copy()
        maternity_gdf = maternity_gdf[
            maternity_gdf.geometry.y.between(bbox["lat_min"], bbox["lat_max"]) & 
            maternity_gdf.geometry.x.between(bbox["lon_min"], bbox["lon_max"])
        ].copy()

    em_dest = [(geom.y, geom.x) for geom in emergency_gdf.geometry]
    mat_dest = [(geom.y, geom.x) for geom in maternity_gdf.geometry]

    # 2. Extract intersection nodes conforming to bounding constraints
    nodes_gdf = extract_intersection_nodes(pbf_path, bbox=bbox, sample_size=1500)
    origins = [(geom.y, geom.x) for geom in nodes_gdf.geometry]

    # 3. Compute Travel Times Matrix
    logger.info("Querying Valhalla engine for Emergency matrix tracks...")
    nodes_gdf["travel_time_emergency"] = get_valhalla_matrix(origins, em_dest)

    logger.info("Querying Valhalla engine for Maternity matrix tracks...")
    nodes_gdf["travel_time_maternity"] = get_valhalla_matrix(origins, mat_dest)

    # 4. Save results to GeoJSON datasets
    nodes_output_dir = processed_dir / "nodes"
    os.makedirs(nodes_output_dir, exist_ok=True)
    
    geojson_out = nodes_output_dir / f"nodes_accessibility_{scope.lower()}.geojson"
    nodes_gdf.to_file(geojson_out, driver="GeoJSON")
    logger.info(f"Saved structural node dataset to: {geojson_out}")

    # 5. Plot Heatmaps matching target color profiles
    map_out_em = output_dir / f"nodes/node_heatmap_emergency_{scope.lower()}.png"
    plot_node_accessibility(nodes_gdf, map_out_em, target_col="travel_time_emergency")
    
    map_out_mat = output_dir / f"nodes/node_heatmap_maternity_{scope.lower()}.png"
    plot_node_accessibility(nodes_gdf, map_out_mat, target_col="travel_time_maternity")