#VISUALIZATOIN
    # --- Assuming you already have census_gdf and the 'origins' list ---
    # origins = [(lat, lon), (lat, lon), ...]

    # 2. Convert the 'origins' list of tuples back into a GeoDataFrame of Points
    points_geometry = [Point(lon, lat) for lat, lon in origins]
    gdf_centroids = gpd.GeoDataFrame(geometry=points_geometry, crs="EPSG:4326")

    # 3. Ensure the original census_gdf is also in WGS84
    census_wgs = census_gdf.to_crs("EPSG:4326")
    

    # 4. Create the Static Map
    fig, ax = plt.subplots(figsize=(15, 15))

    # Plot the polygons (the ORPs) as the background
    census_wgs.plot(ax=ax, color='white', edgecolor='black', linewidth=0.5)

    # Plot the centroids (the 'origins') as red dots
    gdf_centroids.plot(ax=ax, color='red', markersize=10, zorder=3)

    # 5. Label each centroid with its Index/ID
    for idx, pt in zip(centroids_wgs.index, centroids_wgs):
    # Offset the text slightly (0.01 degrees) so it doesn't sit directly on the dot
        ax.text(pt.x + 0.01, pt.y + 0.01, str(idx), 
                fontsize=8, 
                fontweight='bold', 
                ha='left', 
                va='bottom', 
                zorder=4)
    # We iterate through the census_wgs index and the coordinates
    #for idx, geom in zip(census_wgs.index, census_wgs):
    #    # Offset the text slightly (0.01 degrees) so it doesn't sit directly on the dot
    #    ax.text(geom.x + 0.01, geom.y + 0.01, str(idx), 
    #            fontsize=8, 
    #            fontweight='bold', 
    #            ha='left', 
    #            va='bottom', 
    #            zorder=4)

    # Formatting
    plt.title("Czechia ORP Centroids with ID Labels", fontsize=16)
    plt.axis('off') 

    output_folder = "visualizations"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    # 6. Save to the visualizations folder instead of showing the popup
    save_path = os.path.join(output_folder, "orp_centroids_labeled.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close() # Closes the plot so it doesn't pop up in the notebook

    print(f"Map successfully saved to: {save_path}")