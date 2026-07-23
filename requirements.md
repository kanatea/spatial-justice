# Requirements

## 1. Preprocessing (a_preprocessing.py)
- Transform the data to match all to one projection (EPSG:5514 / S-JTSK)
- Standardize data by calculating percentages, rates, and indices, and applying z-score standardization
- Hospital Filtering - fFilter raw healthcare provider CSV points from NRPZS:
  - Emergency Care - Filter into Level 1 & 2 acute departments. Discarding ambulance dispatch stations.
  - Maternity Care - Filter into Level 1 & 2 accredited inpatient maternity wards (porodnice) and obstetrical ICUs, discarding non-acute outpatient clinics.
- Aggregate POIs - calculate count and density (total population) of hospital points for ORPs (districts) - by adding a column 

## 2. Clustering (b_clustering.py)
- Demografic parameters selection:
  - POP_DENS_scaled (population density)
  - PCT_WOMEN_scaled (% women)
  - PCT_ELDERLY_scaled (% age 65+)
  - DEPENDENCY_scaled (dependency index: age under 14 + age over 65 / age 25-64) * 100))
  - NATURAL_INC_RATE_scaled (natural population increase rate per 1000 inhabitants: (births - deaths) / total population * 1000)
  - MIG_BAL_RATE_scaled (migration balance rate per 1000 inhabitants: (people who moved in - people who moved out) / total population * 1000)
- Perform K-Means clustering using the census parameters. 
  - Number of appropriate clusters were determined with the pseudo-f (calinski harabasz) score and the silhouette value, which is a defined function and prints out in the console
- Visualize clusters
- Create a box-plot chart of global vs. per cluster standardized means of each variable to visualize and understand the defining characteristics of each cluster.
  - Console also prints the cluster characteristics, or the raw means of each variable, per cluster, as well as the z-scores of each variable per cluster.

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
  - If batches still fail -- create "routing location one by one" for each district
  - If that also fails --> replace the travel time with a simple straight-line calculation
- Save separate geojsons for each cluster with additional travel time column for all districts
  - data/processed/clusters/cluster_X.geojson

## 5. Visualizations (visualization.py)
A. Cluster profiles:
- Cluster choropleth map over grey context basemap
- Cluster map with point facility overlays for emergency cicles and maternity crosses
- 3x2 grid layout summarizing count vs. per-capita supply metrics per cluster (cluster_X_metrics_summary.png).
- Distribution boxplots characterizing demographic feature spread per cluster.

B. ESDA - spatial autocorrelation:
- Five-color LISA spatial cluster map displaying hotspots, coldspots, and spatial outliers.

C. Accessibility:
- Nationwide driving accessibility choropleths.
- 8-panel comparison grids displaying global-scale vs. within-cluster local-scale driving times.
- Dual-map access pair exports for each cluster highlighting top-ranked (best) and lowest-ranked (worst) ORPs with summary statistics tables.
- Socioeconomic scatter plots assessing travel time against demographic vulnerability.