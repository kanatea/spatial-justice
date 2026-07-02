import logging
import geopandas as gpd
import sys
import typer
from pathlib import Path

from health_access.a_preprocessing import transform_projections, standardize_data, aggregate_poi
from health_access.b_clustering import apply_clustering, export_clusters_separately
from health_access.c_analysis_moran import create_weights_matrices, build_morans_table, compute_lisa
from health_access.d_analysis_accessibility import calculate_health_accessibility
from health_access.visualization import create_cluster_map, plot_accessibility_map, plot_access_vs_socio, plot_network_accessibility, run_cluster_viz, plot_lisa_overlay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

CLUSTERING_FEATURES = [
    "POP_DENS", "PCT_WOMEN", "PCT_CHILD", 
    "PCT_WORKING", "PCT_ELDERLY", "AGEING_INDEX", 
    "DEPENDENCY", "NATURAL_INC_RATE", "MIG_BAL_RATE" #,
    # "COUNT_EMERGENCY", "COUNT_MATERNITY", "COUNT_TOTAL_CARE"
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
    n_clusters: int = typer.Option(
        5, 
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
    skip_transform: bool = typer.Option(
        False, 
        "--skip-transform", 
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
    skip_accessibility: bool = typer.Option( # define
        False, 
        "--skip-accessibility", 
        "-sa", 
        help="Skip accessibility analysis step."
        ),
    show_legend: bool = typer.Option(
        False, 
        "--legend", 
        "-l", 
        help="Add a legend to the cluster map." # is this just for the cluster map or all legends?
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

   # 1. PREPROCESSING: Transform (reproject) all raw files to EPSG:5514
    if not skip_transform:
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

            gdf_clustered = apply_clustering(
                gdf_vars,
                features = CLUSTERING_FEATURES,
                n_clusters = n_clusters,
                random_state = random_state
            )

            gdf_clustered.to_file(clustered_output, driver="GeoJSON")

            logger.info(f"Clustered data saved to: {clustered_output}")

            clusters_dir = project_root / "data/processed/clusters"
            clusters_dir.mkdir(parents=True, exist_ok=True)
            export_clusters_separately(gdf_clustered, clusters_dir)
        
            #logger.info("Generating detailed density visualizations for each cluster...")
            #run_cluster_viz(
            #    clusters_dir=clusters_dir, 
            #    viz_dir=viz_cluster_output
            #)

        else:
            logger.error("Variables file missing. Skipping clustering.")
            return  # Exit the function if the variables file is missing

    #  CLUSTER CONT  - VISUALIZATION
        # Image A: Clusters only
        logger.info("Generating cluster map...")
        saved_map_path = create_cluster_map(
            gdf_clustered,
            project_root = project_root, 
            n_clusters = n_clusters,
            show_legend=show_legend,
            title="ORP Clusters based on 9 Selected Variables"
        )

        # Image B: Clusters + Points
        logger.info("Generating cluster map with point overlays...")
        create_cluster_map(
            gdf_clustered, 
            project_root=project_root, 
            n_clusters=n_clusters, 
            with_points=True, 
            point_mapping=POINT_MAPPING, 
            points_dir=raw_dir, 
            show_legend=show_legend,
            title="Spatial Justice Analysis"
        )
        logger.info(f"Visualization saved to: {saved_map_path}")

    else:
        logger.info("Skipping clustering (--skip-clustering set).")
    # logger.error("Variables file missing. Skipping Clustering and Visualization.")



    # 3. INTRA-CLUSTER SPATIAL ANALYSIS 
    # Analyzing patterns WITHIN each cluster
    #if not skip_clustering: # Only run if clustering was performed
    logger.info("Step 3: Global Spatial Analysis (Healthcare Desert Detection)...")
        
    try:
            # A. Define the Justice Metric (Per Capita Density)
            # Using the population column POCET_OBYV from your logic
            population = gdf_clustered['POCET_OBYV'].replace(0, 1)
            gdf_clustered['EMERGENCY_PER_CAPITA'] = (gdf_clustered['COUNT_EMERGENCY'] / population) * 1000
            gdf_clustered['MATERNITY_PER_CAPITA'] = (gdf_clustered['COUNT_MATERNITY'] / population) * 1000
            gdf_clustered['TOTAL_PER_CAPITA'] = (gdf_clustered['COUNT_TOTAL_CARE'] / population) * 1000

            target_col = "EMERGENCY_PER_CAPITA" #can be maternity or total 
            
            # B. Create Weights for the entire city
            # This ensures we find clusters of low-access regardless of socio-economic status
            weights = create_weights_matrices(gdf_clustered)
            queen_w = weights["Queen"]
            
            # C. Global Moran's I
            # Tells us if health access is generally clustered or random across the city
            moran_table = build_morans_table(gdf_clustered, weights, target_col) #NEED TO ADD FLAG
            moran_table.to_csv(spatial_dir / "global_moran_results.csv", index=False)
            
            # D. LISA (Local Indicators of Spatial Association)
            # This identifies the actual "Coldspots" (Low-Low)
            lisa_gdf, lisa_obj = compute_lisa(gdf_clustered, queen_w, target_col) #NEED TO ADD FLAG

            # Save the results. Use the GDF (lisa_gdf) for the file export
            lisa_output = spatial_dir / "global_lisa_results.geojson"
            lisa_gdf.to_file(lisa_output, driver="GeoJSON")

            logger.info(f"Spatial analysis complete. Results saved to: {lisa_output}")

           
            # Now call the visualization function
            plot_lisa_overlay(
                gdf_clustered=lisa_gdf, 
                lisa_results=lisa_obj,  
                output_path=viz_dir / f"lisa_overlay_{n_clusters}.png"
            )
                    
    except Exception as e:
        logger.error(f"Spatial analysis failed: {e}")
            #else:
            #        logger.error("Clustered file missing. Skipping spatial analysis.")




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

    logger.info("Complete! :)")


if __name__ == "__main__":
    app()
