# requirements

1. Preprocessing
- Transform the data to match all to one projection
- Standardize data (recalculating to relative values --> z-score normalization)
- Aggregate POIs - calculate count and density (total population) of hospital points for ORPs (districts) - by adding a column

2. Clustering
- Perform K-Means clustering using 9 census parameters
- Create a table to visualize characterics of each cluster
(Urban, suburban, ?rural?, semi-peripheral, peripheral)
- Visualize clusters
- Create separate geojsons for each cluster

3. ESDA using Moran's I (LISA and Global)
- Create different spatial weights matrices
- Compute Global Moran's I
- Compute LISA and visualize in a map
- Build Global Moran's table

4. Accessibility analysis - travel time using Valhalla
- Install Docker
- Create centroids of ORPs
- Calculate the travel time distance to emergency / maternity units
- Calculate the average times per clusters


5. Visualizations
- Visualizing the outcomes of each step along the way
A1) Clusters A2) Clusters with emergency/materninty points
B) LISA results (emergency / materninty / combined)
C1) Accessibility (time_travel) ranking of ORPs within each cluster / inbetween clusters
C2) Accessibility comparison between emergency and materninty units --> calculate a "time gap"
