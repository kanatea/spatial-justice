# requirements

1. Preprocessing
- Transform the data to match all to one projection
- Standardize data
- Aggregate POIs - asign hospital points to ORPs (districts) - by adding a column

2. Clustering
- Perform K-Means clustering using explicit parameters
- 

3. ESDA using Moran's I (LISA and Global)
- Creates different spatial weights matrices
- Compute Global Moran's I
- Compute LISA
- Build Moran's table

4. Accessibility analysis - travel time using Valhalla

5. Visualizations
- Visualizing the outcomes of each step along the way
A1) Clusters A2) Clusters with emergency/materninty points
B) Moran's I results (emergency / materninty / combined)
C1) Accessibility (time_travel) ranking of ORPs within each cluster / inbetween clusters
C2) Accessibility comparison between emergency and materninty units --> calculate a "time gap"
