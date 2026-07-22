#  CLUSTER CONT  - VISUALIZATION
    # Consolidates all 6 metrics into unified grid layouts per cluster
    if clustering_viz:
        logger.info("Generating individual cluster profiles...")
        
        if not clusters_dir.exists() or not list(clusters_dir.glob("cluster_*.geojson")):
            logger.warning(f"No isolated cluster GeoJSON files found at {clusters_dir}. Re-running export split...")
            if access_output.exists():
                gdf_access = gpd.read_file(access_output)
                gdf_vars = gpd.read_file(census_output)
                clusters_dir.mkdir(parents=True, exist_ok=True)
                export_clusters_separately(gdf_access, clusters_dir)

            #CLUSTER TRAVEL TIME VISUALIZATIONS  
            visualize_cluster_accessibility_8panel(
                cluster_gdf=gdf_access,
                viz_dir=viz_dir,
                basemap_gdf=gdf_vars,
                value_col="time_maternity",
                output_name="cluster_maternity_accessibility_8panel.png",
                title_label="Nearest Maternity Care Center Drive Time"
            )

            visualize_cluster_accessibility_8panel(
                cluster_gdf=gdf_access,
                viz_dir=viz_dir,
                basemap_gdf=gdf_vars,
                value_col="time_emergency",
                output_name="cluster_emergency_accessibility_8panel.png",
                title_label="Nearest Emergency Drive Time"
            )

           
            #CARE CENTER COUNT VISUALIZATIONS
            logger.info("Generating detailed 3x2 grid metric summaries for each demographic slice...")
            
            # This triggers your new consolidated layout logic internally
            run_cluster_viz(
                clusters_dir = clusters_dir, 
                viz_dir = viz_cluster_output,
                basemap_gdf = gdf_vars
            )

        else:
                        logger.error("Clustered data output not found. Cannot generate cluster profiles.")
        
    else:
        logger.info("Skipping clustering visualization (--clustering-viz turned off).")

