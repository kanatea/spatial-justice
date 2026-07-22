# Travel Time Accessibility of Emergency Care vs. Maternity Care Units in Czechia
*Spatial Justice Final Project by Marie Tranová and Kana Tateishi*

## Overview :)
This project aims to compare and examine the differences of the travel accessibility of emergency care and maternity care services. Potential research questions include:
- How long do women have to travel to give birth compared to someone seeking general emergency care? 
- Who is traveling longer to seek care? 
- Where do they live? 
- Do they share socioeconomic or demographic characteristics?

We will map travel times to the emergency and maternity units and identify outliers. If areas with very long travel time will be discovered, it will be a potential area for improvement to increase the connectivity.

| | |
| ----------- | ----------- |
| **Geographic Area of Interest:** | Czech Republic ORPs (Obec s rozšířenou působností = Municipality with extended jurisdiction) |
| **Spatial Socioeconomic Problem:** | Travel accessibility of two types of medical care (emergency care vs maternity care) according to region and sociodemographic factors; examining inaccessibility on a regional scale and an individual health accessibility scale. |
| **Justice Concept:** | Unequal distribution of emergency and maternity healthcare between regions and differences in travel time to seek care at emergency or maternity centers. |
| **Spatial Representation:** | Point data of hospitals and maternity care centers and road networks, as well as major cities, subregions (municipalities with extended jurisdiction), in which sociodemographic factors such as population density and age indicators can be aggregated. |
| **Analysis:** | Service network analysis, drawing threshold line of what is outside a service area. |
| **Decision Support:** | Identify areas that do not have good healthcare distribution and which are therefore suitable for the construction of new facilities (hospitals or maternity units) AND/OR roads |
| **Proposed Solution:** | Clustering of areas similar in sociodemographic characteristics and ranking within each cluster of the ORPs that have the least/most difficult access to emergency care centers and maternity care centers, respectively. Those identified ORPs will be suggested sites of intervention. |

## Data Sources
- [Geoportal ČÚZK](https://cuzk.gov.cz/) (administrative and cadastral boundaries, road networks); [Link to portal](https://geoportal.cuzk.gov.cz/mGeoportal/)
- [National Registry of Healthcare Providers](https://nrpzs.uzis.cz/) (csv file of all healthcare providers)
- [OpenStreetMap](https://download.geofabrik.de/europe/czech-republic.html) (road networks, regional boundaries, hospital location backup)
- [Czech Statistical Office](https://csu.gov.cz/2021-census?pocet=10&start=0&podskupiny=171&razeni=-datumVydani) for 2021 Census


## Proposed Method
Data Preprocessing --> Clustering --> Accessibility Analysis --> Visualizations of Outcomes
For a more detailed breakdown, please refer to `requirements.md`

1. Data preprocessing includes filtering emergency care (build_emergency). It scans the specialties and care_form columns in the csv to classify every facility into one of three levels: hospitals with a formal emergency department (urgentní medicína), hospitals with ICU-level acute care but no dedicated ED, and ambulance dispatch stations (ZZS). Everything else is discarded.
    - What kind of services are included in maternity care?
2. For clustering, a multivariate clustering method will be conducted based on relevant sociodemographic, such as population density, average age, natality rate, % women in fertile age, and more.
    - Expecting 3-5 clusters of administrative districts. 
    - We will use the [scikit-learn module](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html#sklearn.cluster.KMeans) to conduct k-means clustering. Github repository [here](https://github.com/scikit-learn/scikit-learn/tree/fe2edb3cdbd75ae4e662fda67dcb19277258792b).

3. Assess accessibility to emergency and maternity care centers within clusters 
    - [Valhalla](https://github.com/valhalla/valhalla) is a routing agent that calculates the distances between two points; in this case, we will calculate the distance between the centroids of the districts to the nearest healthcare center, with distinction between emergency care and maternity care. 

## Project Structure

```
spatial-justice/
├── data/
│   ├── raw/                  # Administrative boundaries with census data + healthcare units
│   ├── transformed/          
│   └── processed/            
│       ├── clusters/         # GeoJSON files separated by clusters
│       └── spatial_analysis/ 
├── visualizations/           
│   ├── cluster_viz/          
│   └── final_cluster_maps/   # Comparative access maps by cluster
├── valhalla_tiles/           # Local OpenStreetMap PBF network files for Valhalla
├── src/health_access/
│   ├── init.py
│   ├── main.py           
│   ├── a_preprocessing.py          # Spatial transformations & data standardization
│   ├── b_clustering.py             # KMeans optimization & cluster characterization
│   ├── c_analysis_moran.py         # Global Moran's I & Local LISA spatial autocorrelation
│   ├── d_analysis_accessibility.py # Valhalla driving time main analysis
│   ├── d_nodes_analysis.py         # This code is currently not being used.
│   └── visualization.py      
├── pyproject.toml
└── README.md
```

## How To Run
Install UV: [UV reference](https://docs.astral.sh/uv/guides/projects/#creating-a-new-project)

Install [Docker](https://docs.docker.com/desktop/setup/install/windows-install/)
- download valhalla container
- command line `docker start valhalla`

Please reference `pyproject.toml` for requirements and dependencies.

`uv run health_access` to run the project. 

OLD TABLE
| Command Flags (TO BE UPDATED) | Long Flags | Default | Description |
| ----------- | ----------- | ----------- | ----------- | ----------- |
| -h, --help | To show options |
| --skip-transform | Skip projection transformation (use already transformed data). |
| --skip-clustering | Skip clustering step. |
| --n-clusters INSERT NUMBER | Number of clusters; overrides the configuration default of 5 clusters |

TESTING NEW TABLE
| Command Flags | Long Flags | Default | Description |
| ----------- | ----------- | ----------- | ----------- |
| -h | --help | | Show options and exit |
| -i | --input | admin_boundaries_ORP.geojson | GeoJSON input file in data/transformed/ for clustering |
| -proj | --epsg_projection | 5514 | Target EPSG projection system |
| -n | --n-clusters | 4 | Number of KMeans clusters |
| -rs | --random_state | 42 | Randomization seed for replicability |
| -st | --skip-project | False | Skip projection transformation (use already transformed data) |
| -ss | --skip_standardize | False | Skip census variable scaling and POI aggregation |
| -sc | --skip-clustering | False | Skip clustering step |
| -sesda | --skip-esda | False | Skip ESDA (Moran's I and LISA analysis) step |
| -sa | --skip-accessibility | False | Skip Valhalla accessibility calculation step |
| -sav | --skip-accessibility-viz | False | Skip accessibility visualization map rendering |
| -nl | --no_legend | True | Add legend to cluster map |
| | --scope | COUNTRY | Analysis spatial scope: 'COUNTRY' or 'PRAGUE' |
| -sn | --skip-nodes | True | Skip street network intersection node analysis |
| -h_filter | --hospital_filter | True | Filter facilities to Level 1 & 2 acute care centers |