def plot_lisa_overlay(gdf_clustered, lisa_results, output_path):
    fig, ax = plt.subplots(figsize=(12, 12))
    
    if 'lisa_cluster' not in gdf_clustered.columns:
        category_map = {0: 'Insignificant', 1: 'Hotspot (HH)', 2: 'Low-High (LH)', 3: 'Coldspot (LL)', 4: 'High-Low (HL)'}
        gdf_clustered['lisa_cluster'] = [category_map[val] for val in lisa_results.q]

    # 1. Plot the socio-economic clusters as the base layer
    gdf_clustered.plot(
        column='cluster', 
        ax=ax, 
        cmap='Pastel1', 
        legend=True, 
        legend_kwds={'label': "Socio-Economic Cluster"}
    )
    
    # 2. Filter the Coldspots
    coldspots = gdf_clustered[gdf_clustered['lisa_cluster'] == 'Coldspot (LL)']
    
    # 3. Overlay the Coldspots
    if not coldspots.empty:
        coldspots.plot(
            ax=ax, 
            color='red', 
            edgecolor='black', 
            linewidth=1
        )
        
        # 4. FIX: Create a manual proxy artist for the legend
        # This creates a small red square for the legend without needing to link it to the plot
        red_patch = mpatches.Patch(facecolor='red', edgecolor='black', label='Care Center Desert (Coldspot)')
        plt.legend(handles=[red_patch])
    else:
        # If no coldspots, we still want the socio-economic legend to show, 
        # but we don't need the red patch.
        plt.legend()
    
    plt.title("Care Center Deserts vs. Socio-Economic Clusters")
    plt.savefig(output_path)
    plt.close()