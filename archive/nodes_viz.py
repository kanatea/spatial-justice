# broken code RIGHT NOT - BUT CAN BE IMPLEMENTED

if not skip_accessibility_viz:
            if not access_output.exists():
                logger.error("Accessibility file missing. Run accessibility calculation first.")
            else:
                logger.info("Generating accessibility maps...")

                gdf_access = gpd.read_file(access_output)
                gdf_vars = gpd.read_file(census_output)


# 5. STREET NETWORK NODES ANALYSIs --> this part goes to main
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