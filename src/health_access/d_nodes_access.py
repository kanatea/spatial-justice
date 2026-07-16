import os
import logging
import time
import requests
import geopandas as gpd
import matplotlib.pyplot as plt
from pyrosm import OSM

# Setup logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

VALHALLA_API_URL = "http://localhost:8002"
VALHALLA_MATRIX_LIMIT = 2400

# File Paths
OSM_PBF_PATH = r"C:\Users\marie\Projects\spatial-justice\valhalla_tiles\praha-latest.osm.pbf"

# NEW OUTPUT PATHS (Saving inside the 'nodes' subdirectory):
OUTPUT_GEOJSON_PATH = r"C:\Users\marie\Projects\spatial-justice\spatial-justice\data\processed\nodes\nodes_accessibility.geojson"
OUTPUT_MAP_PATH = r"C:\Users\marie\Projects\spatial-justice\spatial-justice\src\health_access\visualizations\nodes\prague_nodes_accessibility.png"

EMERGENCY_PATH = r"C:\Users\marie\Projects\spatial-justice\spatial-justice\data\raw\OD_emergency_care.geojson"
MATERNITY_PATH = r"C:\Users\marie\Projects\spatial-justice\spatial-justice\data\raw\OD_maternity_care.geojson"

def extract_intersection_nodes(pbf_path, sample_size=1000):
    """
    Parses the local Prague OSM PBF file to extract real street intersection nodes.
    """
    logger.info(f"Reading street network from {pbf_path}...")
    osm = OSM(pbf_path)
    nodes, edges = osm.get_network(nodes=True)
    
    # Identify intersections connected to 2 or more road segments
    intersection_ids = edges.groupby("u").size()
    intersection_ids = intersection_ids[intersection_ids >= 2].index
    
    intersection_nodes = nodes[nodes["id"].isin(intersection_ids)].copy()
    logger.info(f"Extracted {len(intersection_nodes)} unique road intersection nodes.")
    
    if len(intersection_nodes) > sample_size:
        logger.info(f"Downsampling to {sample_size} random intersections for stable routing...")
        intersection_nodes = intersection_nodes.sample(n=sample_size, random_state=42)
        
    return intersection_nodes.to_crs("EPSG:4326")


def get_valhalla_matrix(origins, destinations, costing="auto", units="km"):
    """
    Dynamically batches the street nodes and queries Valhalla.
    """
    endpoint = f"{VALHALLA_API_URL}/sources_to_targets"
    sources = [{"lat": float(lat), "lon": float(lon), "radius": 1000} for lat, lon in origins]
    targets = [{"lat": float(lat), "lon": float(lon), "radius": 2000} for lat, lon in destinations]

    total_sources = len(sources)
    total_targets = len(targets)
    
    calculated_batch_size = int(VALHALLA_MATRIX_LIMIT / total_targets)
    batch_size = max(1, min(calculated_batch_size, 50))
    
    logger.info(f"⚡ Calculated Batch Size: {batch_size} nodes per request.")
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
            response = requests.post(endpoint, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                batch_results = data.get("sources_to_targets", [])

                for local_idx, target_list in enumerate(batch_results):
                    global_idx = i + local_idx
                    times = [cell["time"] / 60 for cell in target_list if cell.get("time") is not None]
                    min_travel_times[global_idx] = round(min(times), 1) if times else None
                i += batch_size
            else:
                raise ValueError(f"Server error {response.status_code}")
        except Exception as e:
            logger.warning(f"  !! Batch failed: {e}. Falling back to individual routing...")
            for local_offset in range(current_chunk_size):
                global_idx = i + local_offset
                single_source = sources[global_idx]
                
                single_payload = {
                    "sources": [single_source],
                    "targets": targets,
                    "costing": costing,
                    "units": units,
                    "matrix_locations": 1
                }
                try:
                    res = requests.post(endpoint, json=single_payload, timeout=10)
                    if res.status_code == 200:
                        single_data = res.json().get("sources_to_targets", [[]])[0]
                        times = [cell["time"] / 60 for cell in single_data if cell.get("time") is not None]
                        min_travel_times[global_idx] = round(min(times), 1) if times else None
                except Exception:
                    min_travel_times[global_idx] = None
            i += batch_size
            
        time.sleep(0.05)
    return min_travel_times


def plot_node_accessibility(nodes_gdf, hospitals_gdf, output_path):
    """
    Generates a map of Prague showing street intersections colored by travel time,
    paired with hospital locations and a scale legend.
    """
    logger.info("Generating accessibility map...")
    
    # Filter out nodes that couldn't find a route
    plot_nodes = nodes_gdf.dropna(subset=["travel_time_emergency"]).copy()
    
    if len(plot_nodes) == 0:
        logger.error("No valid travel times found to map!")
        return

    # Calculate scale thresholds
    min_val = 0
    max_val = plot_nodes["travel_time_emergency"].max()

    fig, ax = plt.subplots(figsize=(12, 10))
    
    # 1. Plot the street intersection nodes colored by travel time
    scatter = plot_nodes.plot(
        ax=ax,
        column="travel_time_emergency",
        cmap="RdYlGn_r",  # Green is fast, Red is slow
        markersize=15,
        alpha=0.8,
        legend=True,
        legend_kwds={
            "label": "Driving Time to Nearest Hospital (minutes)",
            "orientation": "horizontal",
            "pad": 0.05,
            "shrink": 0.7
        },
        vmin=min_val,
        vmax=max_val
    )

    # 2. Overlay actual hospital locations as prominent stars
    hospitals_gdf.plot(
        ax=ax,
        color="blue",
        marker="*",
        markersize=120,
        edgecolor="black",
        linewidth=1,
        label="Emergency Hospital"
    )

    # Styling elements
    ax.set_title(
        f"Prague Accessibility: Travel Time to Nearest Emergency Hospital\n"
        f"Range: {min_val} to {max_val:.1f} mins (Car Travel Time)",
        fontsize=14, 
        pad=15
    )
    ax.set_axis_off()
    ax.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Map successfully saved to: {output_path}")


def main():
    logger.info("--- Starting Street Node Accessibility Analysis ---")
    
    # 1. Read and Filter Hospitals to Prague Area
    emergency_gdf = gpd.read_file(EMERGENCY_PATH).to_crs("EPSG:4326")
    maternity_gdf = gpd.read_file(MATERNITY_PATH).to_crs("EPSG:4326")
    
    lat_min, lat_max = 49.9, 50.2
    lon_min, lon_max = 14.2, 14.7
    
    emergency_prah = emergency_gdf[
        emergency_gdf.geometry.y.between(lat_min, lat_max) & 
        emergency_gdf.geometry.x.between(lon_min, lon_max)
    ]
    maternity_prah = maternity_gdf[
        maternity_gdf.geometry.y.between(lat_min, lat_max) & 
        maternity_gdf.geometry.x.between(lon_min, lon_max)
    ]
    
    em_dest = [(geom.y, geom.x) for geom in emergency_prah.geometry]
    mat_dest = [(geom.y, geom.x) for geom in maternity_prah.geometry]
    
    logger.info(f"Loaded {len(em_dest)} Prague Emergency and {len(mat_dest)} Prague Maternity targets.")

    # 2. Extract Prague Street Intersections
    nodes_gdf = extract_intersection_nodes(OSM_PBF_PATH, sample_size=1000)
    origins = [(geom.y, geom.x) for geom in nodes_gdf.geometry]

    # 3. Calculate Travel Times
    logger.info("Routing from nodes to nearest Emergency Care...")
    nodes_gdf["travel_time_emergency"] = get_valhalla_matrix(origins, em_dest)

    logger.info("Routing from nodes to nearest Maternity Care...")
    nodes_gdf["travel_time_maternity"] = get_valhalla_matrix(origins, mat_dest)

    # 4. Save GeoJSON Dataset
    os.makedirs(os.path.dirname(OUTPUT_GEOJSON_PATH), exist_ok=True)
    nodes_gdf.to_file(OUTPUT_GEOJSON_PATH, driver="GeoJSON")
    logger.info(f"Saved dataset to: {OUTPUT_GEOJSON_PATH}")

    # 5. Generate and Save the Visualization Map
    plot_node_accessibility(nodes_gdf, emergency_prah, OUTPUT_MAP_PATH)
    logger.info("🎉 Process finished successfully!")


if __name__ == "__main__":
    main()