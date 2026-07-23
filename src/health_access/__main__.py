import logging
import geopandas as gpd
import sys
import typer
from pathlib import Path
import matplotlib.pyplot as plt

from health_access.a_preprocessing import transform_projections, standardize_data, aggregate_poi
from health_access.b_clustering import find_optimal_k, apply_clustering, print_cluster_characteristics, print_defining_features, plot_cluster_characteristics
from health_access.c_analysis_moran import create_weights_matrices, build_morans_table, compute_lisa
from health_access.d_analysis_accessibility import calculate_health_accessibility, add_access_rankings, export_clusters_separately
from health_access.visualization import create_cluster_map, plot_accessibility_map, plot_access_vs_socio, run_cluster_viz, plot_lisa, visualize_cluster_accessibility_8panel, visualize_all_clusters_access_pairs, plot_hospital_distribution

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

CLUSTER_COLORS = ["#e6194b", "#4363d8", "#f58231", "#3cb44b", "#ffe119", "#f032e6", "#911eb4", "#42d4f4", "#a9a9a9"]


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
        True, 
        "--skip-nodes", 
        "-sn", 
        help="Skip street network node density/accessibility analysis."
        ),
    hospital_filter: bool = typer.Option(
        True, 
        "--hospital_filter", 
        "-h_filter", 
        help="Remove Level 2 Hospital Filter." 
        ),    
    skip_projection: bool = typer.Option(
        False, 
        "--skip-projection", 
        "-sp", 
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
    skip_accessibility_viz: bool = typer.Option( # define
        False, 
        "--skip-accessibility-viz", 
        "-sav", 
        help="Skip accessibility visualization step."
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
    # Load hospital points 
    em_path  = transformed_dir / "OD_emergency_care.geojson"
    mat_path = transformed_dir / "OD_maternity_care.geojson"

    # Define the bounding box logic for the network analysis node module
    bbox = None
    if analysis_scope == "PRAGUE":
        logger.info("Setting global extent properties to Prague limits.")
        bbox = {
            "lat_min": 49.85, "lat_max": 50.25,
            "lon_min": 14.15, "lon_max": 14.80
        }

    # Define the bounding box logic for the network analysis node module
    bbox = None
    if analysis_scope == "PRAGUE":
        logger.info("Setting global extent properties to Prague limits.")
        bbox = {
            "lat_min": 49.85, "lat_max": 50.25,
            "lon_min": 14.15, "lon_max": 14.80
        }

   # 1. PREPROCESSING:
   # a) Transform (reproject) all raw files to EPSG:5514
    if not skip_projection:
        logger.info("Starting Projection Transformation...")
        transform_projections(
            raw_dir, 
            transformed_dir, 
            target_epsg
        )
    else:
        logger.info("Skipping transform.")


    # b) Calculate Standardized Census Variables + Add POI 
    # We only run this if the file was successfully created in the prior step
    if not skip_standardize:
        if input_file.exists():
            logger.info("Starting Census Variable Standardization...")
            standardize_data(input_file, census_output)

            # We load the GDF here so we can pass it to the aggregator
            gdf = gpd.read_file(census_output)

            # AGGREGATE POINTS
            logger.info("Aggregating point data...")

            #LOOKING AT POINTS
            emergency_gdf = gpd.read_file(em_path) #405
            maternity_gdf = gpd.read_file(mat_path) #1741
            if hospital_filter:
                logger.info("Applying Level 2 Hospital Filter: Keeping only levels 1 and 2.")
                emergency_gdf = emergency_gdf[emergency_gdf["level"] <= 2] #139
                maternity_gdf = maternity_gdf[maternity_gdf["level"] <= 2] #115
            else:
                logger.info("Skipping hospital filtering: Using all available points (including ambulance stations).")

            gdf = aggregate_poi(gdf, {
                'COUNT_EMERGENCY': emergency_gdf, 
                'COUNT_MATERNITY': maternity_gdf
            })
            
            # Save the updated GDF to the variables file
            gdf.to_file(census_output, driver="GeoJSON")


        else:
            logger.error(f"Input file not found at {input_file}. Skipping calculation.")

    else:
        
        logger.info("Data preprocessing complete!")

    # 2. CLUSTERING - We only run this if the file was successfully created in the prior step,
    # and if the user didn't specify to skip clustering
    if not skip_clustering: # We check for the file first.
        if census_output.exists():
            logger.info(f"Starting Clustering with {n_clusters} clusters...")
            gdf_vars = gpd.read_file(census_output)

            find_optimal_k(
                gdf_vars,
                features = CLUSTERING_FEATURES,
                random_state = random_state,
                max_k = 10 
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

            #CLUSTER MAP
            logger.info("Generating cluster map...")

            fig = plt.figure(figsize=(14, 17)) 
            gs = fig.add_gridspec(2, 1, height_ratios=[3, 1.2]) 
            ax_map = fig.add_subplot(gs[0])
            ax_chart = fig.add_subplot(gs[1])

            create_cluster_map(
                gdf = gdf_clustered,
                basemap_gdf = gdf_vars,
                project_root = project_root, 
                n_clusters = n_clusters,
                color_palette = CLUSTER_COLORS,
                show_legend = show_legend,
                title = "ORP Clusters based on 6 Selected Variables",
                ax = ax_map 
            )

            #BOXPLOT CHART FOR CLUSTERS
            plot_cluster_characteristics(
                df = gdf_vars, 
                scaled_features = CLUSTERING_FEATURES, 
                color_palette = CLUSTER_COLORS,
                ax = ax_chart
            )

            plt.tight_layout()
            plt.savefig(viz_dir / f"map_clusters_{n_clusters}.png", bbox_inches='tight', dpi=300)
            plt.close()

            logger.info(f"Visualization saved to: {viz_dir}")

            # Image B: Clusters + Points
            logger.info("Generating cluster map with point overlays...")

            emergency_gdf = gpd.read_file(em_path) #405
            maternity_gdf = gpd.read_file(mat_path) #1741
            if hospital_filter:
                emergency_gdf = emergency_gdf[emergency_gdf["level"] <= 2] #139
                maternity_gdf = maternity_gdf[maternity_gdf["level"] <= 2] #115
            else:
                logger.info("Skipping hospital filtering: Using all available points (including ambulance stations).")
            
            fig2 = plt.figure(figsize=(14, 17)) 
            gs2 = fig2.add_gridspec(2, 1, height_ratios=[3, 1]) 
            ax_map2 = fig2.add_subplot(gs2[0])
            ax_chart2 = fig2.add_subplot(gs2[1])

            create_cluster_map(
                gdf = gdf_clustered,
                basemap_gdf = gdf_vars,
                project_root = project_root,
                n_clusters = n_clusters,
                color_palette = CLUSTER_COLORS,
                with_points = True,
                point_mapping = {
                    "Emergency": emergency_gdf, 
                    "Maternity": maternity_gdf
                },
                show_legend = True,
                title = "ORP Clusters based on 6 Selected Variables with Care Locations",
                ax = ax_map2 
            )
            logger.info(f"Visualization saved to: {viz_dir}")

            #BOXPLOT CHART FOR CLUSTERS
            plot_cluster_characteristics(
                df = gdf_vars, 
                scaled_features = CLUSTERING_FEATURES, 
                color_palette = CLUSTER_COLORS,
                ax = ax_chart2
            )

            plt.tight_layout()
            plt.savefig(viz_dir / f"map_clusters_{n_clusters}_points.png", bbox_inches='tight', dpi=300)
            plt.close()

        else:
            logger.error("Variables file missing. Skipping clustering.")
            return  # Exit the function if the variables file is missing

    # 3. ESDA
    # Analyzing patterns WITHIN each cluster
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
    # RUNS USING VALHALLA - WE NEED TO ACTIVATE THAT USING DOCKER FIRST
    # For future improvement: the user could choose only some of them using flags.
    if not skip_accessibility:
        if not clustered_output.exists():
            logger.error("Clustered file missing. Run clustering first.")
        else:
            logger.info("Starting accessibility calculation...")

            gdf_clustered = gpd.read_file(clustered_output)

            if not em_path.exists() or not mat_path.exists():
                logger.error("Hospital GeoJSON files not found in data/transformed/. Skipping.")
            else:
                emergency_gdf = gpd.read_file(em_path)
                maternity_gdf = gpd.read_file(mat_path)

                emergency_gdf = emergency_gdf.to_crs("EPSG:4326")
                maternity_gdf = maternity_gdf.to_crs("EPSG:4326")

                if hospital_filter:
                    logger.info("Applying Level 2 Hospital Filter: Keeping only levels 1 and 2.")
                    emergency_gdf = emergency_gdf[emergency_gdf["level"] <= 2]
                    maternity_gdf = maternity_gdf[maternity_gdf["level"] <= 2]
                else:
                    logger.info("Skipping hospital filtering: Using all available points (including ambulance stations).")

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
    else:
        logger.info("Skipping Accessibility Calculation...")


    # ACCESSIBILITY VISUALIZATION 
    if not skip_accessibility_viz:
            if not access_output.exists():
                logger.error("Accessibility file missing. Run accessibility calculation first.")
            else:
                logger.info("Generating accessibility maps...")

                gdf_access = gpd.read_file(access_output)
                gdf_vars = gpd.read_file(census_output)

                # Add global rankings to the full clustered file
                gdf_access = add_access_rankings(
                    gdf_access,
                    maternity_col="time_maternity",
                    emergency_col="time_emergency",
                    rank_maternity_col="ranking_maternity",
                    rank_emergency_col="ranking_emergency",
                )

                # Optionally overwrite the original clustered access file
                gdf_access.to_file(access_output, driver="GeoJSON")


                clusters_dir.mkdir(parents=True, exist_ok=True)
                export_clusters_separately(
                    gdf_access, 
                    clusters_dir, 
                    cluster_col="cluster",
                    maternity_col="time_maternity",
                    emergency_col="time_emergency"
                )
                
                fig_em = plot_accessibility_map(
                    gdf=gdf_access,
                    column="time_emergency",
                    district_col="NAZ_ORP",
                    title="Travel Time to Nearest Emergency Hospital (minutes)",
                    output_path=viz_dir / "map_access_emergency.png",
                    #poi_type="emergency hospital",
                    cmap="RdYlGn_r",
                    show_legend=show_legend,
                )
                # should we have this or a map with the points? or both?
                # we can have both, but then we need to add a legend for the points.
                # Map C: maternity map
                fig_mat = plot_accessibility_map(
                    gdf=gdf_access,
                    column="time_maternity",
                    district_col="NAZ_ORP",
                    title="Travel Time to Nearest Maternity Hospital (minutes)",
                    output_path=viz_dir / "map_access_maternity.png",
                    #poi_type="maternity hospital",
                    cmap="RdYlGn_r",
                    show_legend=show_legend,
                )

                logger.info("Generating cluster accessibility profile visualizations.")
                #CLUSTER TRAVEL TIME VISUALIZATIONS  
                visualize_cluster_accessibility_8panel(
                    cluster_gdf=gdf_access,
                    viz_dir=viz_dir,
                    basemap_gdf=gdf_vars,
                    value_col="time_maternity",
                    output_path=viz_dir /"cluster_maternity_accessibility_8panel.png",
                    cluster_col="cluster",
                    title_label="Nearest Maternity Care Center Drive Time"
                )
    
                visualize_cluster_accessibility_8panel(
                    cluster_gdf=gdf_access,
                    viz_dir=viz_dir,
                    basemap_gdf=gdf_vars,
                    value_col="time_emergency",
                    output_path=viz_dir / "cluster_emergency_accessibility_8panel.png",
                    cluster_col="cluster",
                    title_label="Nearest Emergency Center Drive Time"
                )
                
                #CARE CENTER COUNT VISUALIZATIONS
                logger.info("Generating detailed 3x2 grid metric summaries for each demographic slice...")
                
                # This triggers your new consolidated layout logic internally
                run_cluster_viz(
                    clusters_dir = clusters_dir, 
                    viz_dir = viz_cluster_output,
                    basemap_gdf = gdf_vars
                )
                # MAP: access gap (maternity minus emergency)
                # this needs to be added in the visualization.py first
                #plot_accessibility_gap_map(
                #    gdf=gdf_access,
                #    output_path=project_root / "visualizations/map_access_gap.png",
                #)

                visualize_all_clusters_access_pairs(
                    cluster_gdf=gdf_access,
                    basemap_gdf=gdf_vars,
                    output_dir=viz_dir / "final_cluster_maps",
                    cluster_col="cluster",
                    label_col="NAZ_ORP", 
                    maternity_col="time_maternity",
                    emergency_col="time_emergency",
                    maternity_count_col="COUNT_MATERNITY",
                    emergency_count_col="COUNT_EMERGENCY",
                    maternity_rank_col="ranking_maternity",
                    emergency_rank_col="ranking_emergency",
                    cmap="RdYlGn_r"
                )

                gdf_access_gap = gdf_access.copy()

                logger.info("Generating scatter plots.")

                # MAP: scatter - maternity travel time vs elderly population (for example)
                fig_scatter = plot_access_vs_socio(
                    gdf=gdf_access_gap,
                    travel_col = "time_maternity",
                    socio_col="PCT_ELDERLY",
                    district_col="NAZ_ORP",
                    poi_type="maternity hospital",
                    max_distance=gdf_access_gap["time_maternity"].max(),
                    show_legend=show_legend,
                )
                fig_scatter.savefig(
                    project_root / "visualizations/scatter_maternity_vs_elderly.png",
                    bbox_inches="tight", dpi=300
                )

                # MAP: scatter - emergency travel time vs elderly population (for example)
                fig_scatter = plot_access_vs_socio(
                    gdf=gdf_access_gap,
                    travel_col = "time_emergency",
                    socio_col="PCT_ELDERLY",
                    district_col="NAZ_ORP",
                    poi_type="emergency hospital",
                    max_distance=gdf_access_gap["time_emergency"].max(),
                    show_legend=show_legend,
                )
                fig_scatter.savefig(
                    project_root / "visualizations/scatter_emergency_vs_elderly.png",
                    bbox_inches="tight", dpi=300
                )
    else:
        logger.info("Skipping accessibility map (--skip-accessibility-maps set).")

    logger.info("Complete! :)")


if __name__ == "__main__":
    app()