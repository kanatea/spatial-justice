# requirements

## 1. Preprocessing (a_preprocessing.py)
- Transform the data to match all to one projection (EPSG:5514 / S-JTSK)
- Standardize data (by calculating relative demographic proportions/rates and applying z-score scaling)
- Hospital Filtering - fFilter raw healthcare provider CSV points from NRPZS:
  - Emergency Care - Filter into Level 1 & 2 acute departments. Discarding ambulance dispatch stations.
  - Maternity Care - Filter into Level 1 & 2 accredited inpatient maternity wards (porodnice) and obstetrical ICUs, discarding non-acute outpatient clinics.
- Aggregate POIs - calculate count and density (total population) of hospital points for ORPs (districts) - by adding a column 

## 2. Clustering (b_clustering.py)
- Demografic parameters selection:
  - POP_DENS_scaled,
  - PCT_WOMEN_scaled,
  - PCT_ELDERLY_scaled,
  - DEPENDENCY_scaled,
  - NATURAL_INC_RATE_scaled,
  - MIG_BAL_RATE_scaled.
- Perform K-Means clustering using the census parameters. 
- Save separate geojsons for each cluster
  - data/processed/clusters/cluster_X.geojson
- Visualize clusters
- Create a box-plot chart of each cluster to visualize the defining characteristics.

## 3. ESDA using Moran's I (c_analysis_moran.py)
- Create queen contiguity spatial weight matrices (create_weights_matrices)
- Compute LISA (Local Indicators of Spatial Association) to identify statistically significant spatial hotspots, coldspots and outliers.
- Calculate Global Moran's I
- Visualize LISA results in a map
- Build Global Moran's table

## 4. Accessibility analysis - travel time using Valhalla (d_analysis_accessibility.py)
- Install Docker, start valhalla and generate the Valhalla tiles
- Extract centroids of ORPs
- Matrix calculation --> Calculate the driving time (in minutes) from each ORP centroid to the nearest level 1 or 2 emergency care and maternity units
-  Error mitigation:
  - Group travel requests into small batches to not overload Valhalla
  - If batches still fail -- create "routing location one by one"
  - If that also fails --> replace the travel time with a simple straight-line calculation

## 5. Visualizations (visualization.py)
- Visualizing the outcomes of each step along the way
A1) Clusters A2) Clusters with emergency/materninty points
B) LISA results (emergency / materninty / combined)
C1) Accessibility (time_travel) ranking of ORPs within each cluster / inbetween clusters
C2) Accessibility comparison between emergency and materninty units --> calculate a "time gap"

A. Cluster profiles:
- Cluster choropleth map over grey context basemap
- Cluster map with point facility overlays for emergency cicles and maternity crosses (can be added using a flag).
- 3x2 grid layout summarizing count vs. per-capita supply metrics per cluster (cluster_X_metrics_summary.png).
- Distribution boxplots characterizing demographic feature spread per cluster.

B. ESDA - spatial autocorrelation:
- Five-color LISA spatial cluster map displaying hotspots, coldspots, and spatial outliers.

C. Accessibility:
- Nationwide driving accessibility choropleths.
- 8-panel comparison grids displaying global-scale vs. within-cluster local-scale driving times.
- Dual-map access pair exports for each cluster highlighting top-ranked (best) and lowest-ranked (worst) ORPs with summary statistics tables.
- Socioeconomic scatter plots assessing travel time against demographic vulnerability.