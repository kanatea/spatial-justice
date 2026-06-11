# Travel Accessibility (Distance/Distribution) of Emergency Care vs. Maternity Care Units
*Spatial Justice Final Project by Marie Tranov and Kana Tateishi*

[UV reference](https://docs.astral.sh/uv/guides/projects/#creating-a-new-project)

## Overview :)
This project aims to compare and examine the differences of the travel accessibility of emergency care and maternity care services. Potential research questions include:
- How long do women have to travel to give birth compared to someone seeking general emergency care? 
- Who is traveling longer to seek care? 
- Where do they live? 
- Do they share socioeconomic or demographic characteristics?

Based on literature, we will find acceptable travel thresholds and assess accessibility. We aim to identify areas with service area gaps and seek to provide suggestions of new care center locations and/or roads for better connection.

| | |
| ----------- | ----------- |
| **Geographic Area of Interest:** | Czech Republic (Administrative district of a municipality with expanded jurisdiction) |
| **Spatial Socioeconomic Problem:** | Travel accessibility of two types of medical care (emergency care vs maternity care) according to region and sociodemographic factors; examining inaccessibility on a regional scale and an individual health accessibility scale. |
| **Justice Concept:** | Unequal distribution of emergency and maternity healthcare between regions and differences in travel time to seek care at emergency or maternity centers. |
| **Spatial Representation:** | Point data of hospitals and maternity care centers and road networks, as well as major cities, regions, subregions, in which sociodemographic factors such as population density and economic indicators can be aggregated. |
| **Analysis:** | Service network analysis, drawing threshold line of what is outside a service area. |
| **Decision Support:** | Identify areas that do not have good healthcare distribution and provide suggestions on areas to build new hospitals or maternity care centers AND/OR roads |

## Data Sources
- [Geoportal ČÚZK](https://cuzk.gov.cz/) (administrative and cadastral boundaries, road networks); [Link to portal](https://geoportal.cuzk.gov.cz/mGeoportal/)
- [National Registry of Healthcare Providers](https://nrpzs.uzis.cz/) (csv file of all healtcare providers)
- [OpenStreetMap](https://overpass-turbo.eu/) via overpass-turbo (road networks, regional boundaries, hospital location backup)
- [Czech Statistical Office](https://csu.gov.cz/2021-census?pocet=10&start=0&podskupiny=171&razeni=-datumVydani) for 2021 Census

## Proposed Method
Data Preprocessing --> Clustering --> Accessibility Index

1. Data preprocessing includes filtering emergency care (build_emergency). It scans the specialties and care_form columns in the csv to classify every facility into one of three levels: hospitals with a formal emergency department (urgentní medicína), hospitals with ICU-level acute care but no dedicated ED, and ambulance dispatch stations (ZZS). Everything else is discarded.
    - What kind of services are included in maternity care?
2. For clustering, a multivariate clustering method will be conducted based on relevant sociodemographic and land use cover, such as area size, population density, average age, natality rate, % women in fertile age, and % residential area within a given district.
    - Expecting 3-5 clusters of administrative districts 
    - We will use the scikit-learn module to conduct k-means clustering. Github repository [here](https://github.com/scikit-learn/scikit-learn/tree/fe2edb3cdbd75ae4e662fda67dcb19277258792b) and documentation [here](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html#sklearn.cluster.KMeans)

3. Assess accessibility to emergency and maternity care centers within clusters 
    - [Valhalla](https://github.com/valhalla/valhalla) is a routing agent that calculates the distances between two points; in this case, we will calculate the distance between the centroids of the districts to the nearest healthcare center, with distinction between emergency care and maternity care. 


## Supporting Literature/Resources
- Identify thresholds of acceptable travel time for emergency care (e.g., EU standard of emergency care response time)
- Maternity care deserts, rural access to healthcare literature

