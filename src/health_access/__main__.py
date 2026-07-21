import logging
import geopandas as gpd
import sys
import typer
from pathlib import Path

from health_access.a_preprocessing import transform_projections, standardize_data, aggregate_poi
from health_access.b_clustering import find_optimal_k, apply_clustering, export_clusters_separately, print_cluster_characteristics, print_defining_features
from health_access.c_analysis_moran import create_weights_matrices, build_morans_table, compute_lisa
from health_access.d_analysis_accessibility import calculate_health_accessibility
from health_access.visualization import create_cluster_map, plot_accessibility_map, plot_access_vs_socio, plot_network_accessibility, run_cluster_viz, plot_lisa
from health_access.d_nodes_analysis import run_nodes_analysis, extract_intersection_nodes, get_valhalla_matrix, plot_node_accessibility

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

CLUSTERING_FEATURES = [
    "POP_DENS_scaled", 
    "PCT_WOMEN_scaled", 
    #"PCT_CHILD_scaled", 
    #"PCT_WORKING_scaled", 
    "PCT_ELDERLY_scaled", 
    #"AGEING_INDEX_scaled", 
    "DEPENDENCY_scaled", 
    "NATURAL_INC_RATE_scaled", 
    "MIG_BAL_RATE_scaled"
]

# Define the mapping for the point files
POINT_MAPPING = {
    "OD_emergency_care.geojson": "COUNT_EMERGENCY",
    "OD_maternity_care.geojson": "COUNT_MATERNITY"
}

@app.command()
def main(
    filename: str = typer.Option(
        "admin_boundaries_ORP.geojson",
        "--input",
        "-i",
        help="GeoJSON filename inside the data/transformed/ folder to be used for clustering.",
    ),
    target_epsg: int = typer.Option(
        5514,
        "--epsg_projection",
        "-proj",
        help="EPSG Projection",
    ),
    #target_col: int = typer.Option(
    #    "EMERGENCY_PER_CAPITA",
    #    "--target_moran_var",
    #    "-moran",
    #    help="Target variable for Moran's I analyses",
    #),
    n_clusters: int = typer.Option(
        4, 
        "--n-clusters", 
        "-n", 
        help="Number of KMeans clusters (overrides config). Default: 5."
        ),
    random_state: int = typer.Option(
        42, 
        "--random_state", 
        "-rs", 
        help="Randomization seed for replicability (overrides config). Default: 42."
        ),    
    skip_project: bool = typer.Option(
        False, 
        "--skip-project", 
        "-st", 
        help="Skip projection transformation (use already transformed data)."
        ),
    skip_standardize: bool = typer.Option(
        False, 
        "--skip_standardize",
        "-ss",
        help="Skip variable standardization."
    ),
    skip_clustering: bool = typer.Option(
        False, 
        "--skip-clustering", 
        "-sc", 
        help="Skip clustering step."
        ),
    clustering_viz: bool = typer.Option(
        False, 
        "--clustering-viz", 
        "-cv", 
        help="Enable clustering visualization step."
        ),
    skip_esda: bool = typer.Option(
        False, 
        "--skip-esda", 
        "-sesda", 
        help="Skip clustering visualization step."
        ),
    skip_accessibility: bool = typer.Option( # define
        False, 
        "--skip-accessibility", 
        "-sa", 
        help="Skip accessibility analysis step."
        ),
    show_legend: bool = typer.Option(
        True, 
        "--no_legend", 
        "-nl", 
        help="Add a legend to the cluster map." 
        ),
    analysis_scope: str = typer.Option(
        "COUNTRY",
        "--scope",
        help="Analysis scope option: 'PRAGUE' or 'COUNTRY'."
        ),
    skip_nodes: bool = typer.Option(
        False, 
        "--skip-nodes", 
        "-sn", 
        help="Skip street network node density/accessibility analysis."
        ),
):
    
    # Loading Configuration
    project_root = Path(__file__).resolve().parents[2] 

   # Resolve paths relative to project root
    raw_dir = project_root / "data/raw"
    transformed_dir = project_root / "data/transformed"
    input_file = transformed_dir / filename
    census_output = transformed_dir / "data_variables.geojson"
    processed_dir = project_root / "data/processed"
    clusters_dir = processed_dir / "clusters"
    clustered_output = processed_dir / f"clusters_{n_clusters}.geojson"
    spatial_dir = processed_dir / "spatial_analysis"
    access_output = processed_dir / f"accessibility_{n_clusters}.geojson"
    viz_dir = project_root/"visualizations"
    viz_cluster_output = viz_dir / "cluster_viz"

    # Define the bounding box logic for the network analysis node module
    bbox = None
    if analysis_scope == "PRAGUE":
        logger.info("Setting global extent properties to Prague limits.")
        bbox = {
            "lat_min": 49.85, "lat_max": 50.25,
            "lon_min": 14.15, "lon_max": 14.80
        }

   # 1. PREPROCESSING: Transform (reproject) all raw files to EPSG:5514
    if not skip_project:
        logger.info("Starting Projection Transformation...")
        transform_projections(
            raw_dir, 
            transformed_dir, 
            target_epsg
        )
    else:
        logger.info("Skipping transform.")


    # PREPROCESSING CONT: Calculate Standardized Census Variables + Add POI 
    # We only run this if the file was successfully created in the prior step
    if not skip_standardize:
        if input_file.exists():
            logger.info("Starting Census Variable Standardization...")
            standardize_data(input_file, census_output)

            # We load the GDF here so we can pass it to the aggregator
            gdf = gpd.read_file(census_output)

            # AGGREGATE POINTS
            logger.info("Aggregating point data...")
            gdf = aggregate_poi(gdf, POINT_MAPPING, transformed_dir)
            
            # Save the updated GDF to the variables file
            gdf.to_file(census_output, driver="GeoJSON")


        else:
            logger.error(f"Input file not found at {input_file}. Skipping calculation.")

    else:
        
        logger.info("Data preprocessing complete!")

    # 2. CLUSTERING - We only run this if the file was successfully created in the prior step, and if the user didn't specify to skip clustering
    if not skip_clustering: # We check for the file first.
        if census_output.exists():
            logger.info(f"Starting Clustering with {n_clusters} clusters...")
            gdf_vars = gpd.read_file(census_output)

            find_optimal_k(
                gdf_vars,
                features = CLUSTERING_FEATURES,
                random_state = random_state,
                max_k = 10 #should i let this be customizable by the user?
            )


            gdf_clustered = apply_clustering(
                gdf_vars,
                features = CLUSTERING_FEATURES,
                n_clusters = n_clusters,
                random_state = random_state
            )

            gdf_clustered.to_file(clustered_output, driver="GeoJSON")

            logger.info(f"Clustered data saved to: {clustered_output}")

            #comparing the scaled data to the original data for interpretation
            RAW_FEATURES = [feat.replace('_scaled', '') for feat in CLUSTERING_FEATURES]
            gdf_vars['cluster'] = gdf_clustered['cluster']

            # print the output to characterize and define features
            char_df = print_cluster_characteristics(gdf_vars, features = RAW_FEATURES)
            zscore_df = print_defining_features(gdf_vars, features = RAW_FEATURES)

            clusters_dir = project_root / "data/processed/clusters"
            clusters_dir.mkdir(parents=True, exist_ok=True)
            export_clusters_separately(gdf_clustered, clusters_dir)


            logger.info("Generating cluster map...")

            saved_map_path = create_cluster_map(
                gdf = gdf_clustered,
                basemap_gdf = gdf_vars,
                project_root = project_root, 
                n_clusters = n_clusters,
                show_legend = show_legend,
                title = "ORP Clusters based on 9 Selected Variables"
            )

            # Image B: Clusters + Points
            logger.info("Generating cluster map with point overlays...")
            create_cluster_map(
                gdf = gdf_clustered, 
                basemap_gdf = gdf_vars,
                project_root = project_root, 
                n_clusters = n_clusters, 
                with_points = True, 
                point_mapping = POINT_MAPPING, 
                points_dir = raw_dir, 
                show_legend = show_legend,
                title = "ORP Clusters based on 9 Selected Variables with Care Locations"
            )
            logger.info(f"Visualization saved to: {saved_map_path}")
        
        else:
            logger.error("Variables file missing. Skipping clustering.")
            return  # Exit the function if the variables file is missing


    #  CLUSTER CONT  - VISUALIZATION
    # Consolidates all 6 metrics into unified grid layouts per cluster
    if not clustering_viz:
        logger.info("Generating individual cluster profiles...")
        
        if not clusters_dir.exists() or not list(clusters_dir.glob("cluster_*.geojson")):
            logger.warning(f"No isolated cluster GeoJSON files found at {clusters_dir}. Re-running export split...")
            if clustered_output.exists():
                gdf_clustered = gpd.read_file(clustered_output)
                clusters_dir.mkdir(parents=True, exist_ok=True)
                export_clusters_separately(gdf_clustered, clusters_dir)
            else:
                logger.error("Clustered data output not found. Cannot generate metric profiles.")
        
        if clusters_dir.exists():
            gdf_vars = gpd.read_file(census_output)
            logger.info("Generating detailed 3x2 grid metric summaries for each demographic slice...")
            
            # This triggers your new consolidated layout logic internally
            run_cluster_viz(
                clusters_dir = clusters_dir, 
                viz_dir = viz_cluster_output,
                basemap_gdf = gdf_vars
            )
    else:
        logger.info("Skipping clustering visualization (--clustering-viz turned off).")


    # 3. ESDA
    # Analyzing patterns WITHIN each cluster
    #NEED TO ADD FLAG
    if not skip_esda:
        logger.info("ESDA: Global Moran's and LISA analysis...")
            
        try:
            gdf_clustered = gpd.read_file(clustered_output)

            target_col = "EMERGENCY_PER_CAPITA" #can be maternity or total  "MATERNITY_PER_CAPITA" / "TOTAL_PER_CAPITA"
            target_col2 = "MATERNITY_PER_CAPITA"
            target_col3 = "TOTAL_PER_CAPITA"
                
            # B. Create Weights for the entire city
            # This ensures we find clusters of low-access regardless of socio-economic status
            weights = create_weights_matrices(gdf_clustered)
            queen_w = weights["Queen"]
                #can y
                
            # C. Global Moran's I
            # Tells us if health access is generally clustered or random across the city
            moran_table_emergency = build_morans_table(gdf_clustered, weights, target_col) 
            moran_table_emergency.to_csv(spatial_dir / "global_moran_emergency_results.csv", index=False)

            moran_table_maternity = build_morans_table(gdf_clustered, weights, target_col2)
            moran_table_maternity.to_csv(spatial_dir / "global_moran_maternity_results.csv", index=False)
            
            moran_table_total = build_morans_table(gdf_clustered, weights, target_col3) 
            moran_table_total.to_csv(spatial_dir / "global_moran_total_results.csv", index=False)  

            # D. LISA (Local Indicators of Spatial Association)
            # This identifies the actual "Coldspots" (Low-Low)
            lisa_gdf, lisa_obj = compute_lisa(gdf_clustered, queen_w, target_col)
            # Save the results. Use the GDF (lisa_gdf) for the file export
            lisa_output = spatial_dir / "global_lisa_results.geojson"
            lisa_gdf.to_file(lisa_output, driver="GeoJSON")
            #NEED TO BRAINSTORM HOW TO DO THIS BETTER
            #MAYBE INPUT FLAGS OR SOMETHING
            
            logger.info(f"Spatial analysis complete. Results saved to: {lisa_output}")
            
            # Now call the visualization function
            plot_lisa(
                gdf_lisa = lisa_gdf, 
                output_path=viz_dir / f"lisa_overlay_{n_clusters}.png"
            )
                        
        except Exception as e:
            logger.error(f"Spatial analysis failed: {e}")
                #else:
                #logger.error("Clustered file missing. Skipping spatial analysis.")
    else:
        logger.info("Skipping ESDA...")

    

    # 4. ACCESSIBILITY ANALYSIS
    # RUNS USING VALHALLA - WE NEED TO ACTIVATE THAT USING DOCKER
    # we could divide this step into a separate script OR have at least separated some steps - the user could choose only some of them using flags.
    if not skip_accessibility:
        if not clustered_output.exists():
            logger.error("Clustered file missing. Run clustering first.")
        else:
            logger.info("Starting accessibility calculation...")

            gdf_clustered = gpd.read_file(clustered_output)

            # Load hospital points (only actual hospitals, levels 1 and 2)
            em_path  = raw_dir / "OD_emergency_care.geojson"
            mat_path = raw_dir / "OD_maternity_care.geojson"

            if not em_path.exists() or not mat_path.exists():
                logger.error("Hospital GeoJSON files not found in data/raw/. Skipping.")
            else:
                emergency_gdf = gpd.read_file(em_path)
                maternity_gdf = gpd.read_file(mat_path)

                # Keep only actual hospitals (levels 1 and 2), not ambulance stations
                # Should this step be done in the preprocessing step? Or is it better to keep all points for other analyses?
                emergency_gdf = emergency_gdf[emergency_gdf["level"] <= 2]
                maternity_gdf = maternity_gdf[maternity_gdf["level"] <= 2]

                # Dynamic geographic area filter switch
                if analysis_scope == "PRAGUE":
                    logger.info("Applying local spatial filter: Prague + Surroundings")
                    lat_min, lat_max = 49.85, 50.25
                    lon_min, lon_max = 14.15, 14.80
                    
                    emergency_gdf = emergency_gdf[
                        emergency_gdf.geometry.y.between(lat_min, lat_max) & 
                        emergency_gdf.geometry.x.between(lon_min, lon_max)
                    ].copy()
                    
                    maternity_gdf = maternity_gdf[
                        maternity_gdf.geometry.y.between(lat_min, lat_max) & 
                        maternity_gdf.geometry.x.between(lon_min, lon_max)
                    ].copy()
                else:
                    logger.info("Scope set to COUNTRY. Retaining nationwide care facilities.")

                logger.info(f"Loaded {len(emergency_gdf)} Emergency and {len(maternity_gdf)} Maternity target locations.")
                
                # Calculate travel times - this might take a few minutes
                gdf_access = calculate_health_accessibility(
                    gdf_clustered, emergency_gdf, maternity_gdf
                )

                gdf_access.to_file(access_output, driver="GeoJSON")
                logger.info(f"Accessibility data saved to: {access_output}")

                # MAP: plot_accessibility_map for emergency units
                logger.info("Generating accessibility maps...")
                fig_em = plot_accessibility_map(
                    gdf=gdf_access,
                    column="travel_time_emergency",
                    district_col="NAZ_ORP",
                    title="Travel Time to Nearest Emergency Hospital (minutes)",
                    poi_type="emergency hospital",
                    cmap="RdYlGn_r",
                    show_legend=show_legend,
                )
                # should we have this or a map with the points? or both?
                # we can have both, but then we need to add a legend for the points.
                fig_em.savefig(
                    project_root / "visualizations/map_access_emergency.png",
                    bbox_inches="tight", dpi=300
                    )

                # Map C: plot_accessibility_map (travel time choropleth) for maternity units
                fig_mat = plot_accessibility_map(
                    gdf=gdf_access,
                    column="travel_time_maternity",
                    district_col="NAZ_ORP",
                    title="Travel Time to Nearest Maternity Hospital (minutes)",
                    poi_type="maternity hospital",
                    cmap="RdYlGn_r",
                    show_legend=show_legend,
                )
                # should we have this or a map with the points? or both?
                # we can have both, but then we need to add a legend for the points.
                fig_mat.savefig(
                    project_root / "visualizations/map_access_maternity.png",
                    bbox_inches="tight", dpi=300
                    )

                # MAP: access gap (maternity minus emergency)
                # this needs to be added in the visualization.py first
                #plot_accessibility_gap_map(
                #    gdf=gdf_access,
                #    output_path=project_root / "visualizations/map_access_gap.png",
                #)

                gdf_access["travel_time"] = gdf_access["travel_time_maternity"]
                
                # MAP: scatter - travel time vs elderly population (for example)
                fig_scatter = plot_access_vs_socio(
                    gdf=gdf_access,
                    socio_col="PCT_ELDERLY",
                    district_col="NAZ_ORP",
                    poi_type="maternity hospital",
                    max_distance=gdf_access["travel_time"].max(),
                    show_legend=show_legend,
                )
                fig_scatter.savefig(
                    project_root / "visualizations/scatter_maternity_vs_elderly.png",
                    bbox_inches="tight", dpi=300
                )
    else:
        logger.info("Skipping accessibility (--skip-accessibility set).")

    # 5. STREET NETWORK NODES ANALYSIs
    if not skip_nodes:
        logger.info("Starting street network node analysis...")
        
        # 1. Dynamically locate the local Prague PBF road network file
        pbf_path = project_root.parent / "valhalla_tiles/praha-260714.osm.pbf"
        if not pbf_path.exists():
            pbf_path = project_root / "valhalla_tiles/praha-260714.osm.pbf"
            
        # 2. Load and isolate raw hospital files matching our target layout
        em_path = raw_dir / "OD_emergency_care.geojson"
        emergency_gdf = gpd.read_file(em_path).to_crs("EPSG:4326")
        
        # 3. Filter hospitals down to the active Prague window if scope matches
        if analysis_scope == "PRAGUE" and bbox:
            emergency_prah = emergency_gdf[
                emergency_gdf.geometry.y.between(bbox["lat_min"], bbox["lat_max"]) & 
                emergency_gdf.geometry.x.between(bbox["lon_min"], bbox["lon_max"])
            ].copy()
        else:
            emergency_prah = emergency_gdf.copy()
            
        # 4. Extract real intersection nodes from the PBF network map
        nodes_gdf = extract_intersection_nodes(pbf_path, bbox=bbox, sample_size=1000)
        
        # 5. Route travel matrices using Valhalla engine chunks
        origins = [(geom.y, geom.x) for geom in nodes_gdf.geometry]
        em_dest = [(geom.y, geom.x) for geom in emergency_prah.geometry]
        
        logger.info("Routing from network nodes to nearest Emergency Care tracking...")
        nodes_gdf["travel_time_emergency"] = get_valhalla_matrix(origins, em_dest)
        
        # 6. Run the original localized map rendering function 
        plot_node_accessibility(
            nodes_gdf=nodes_gdf,
            output_path=project_root / "visualizations/nodes/prague_nodes_accessibility.png",
            target_col="travel_time_emergency"
        )
        
    else:
        logger.info("Skipping street network node analysis (--skip-nodes / -sn set).")

    logger.info("Complete! :)")


if __name__ == "__main__":
    app()