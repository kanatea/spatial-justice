from pathlib import Path
import geopandas as gpd

# Project root directory
ROOT = Path(__file__).resolve().parents[3]

input_file = ROOT / "data" / "transformed" / "admin_boundaries_ORP.geojson"
output_file = ROOT / "data" / "transformed" / "admin_boundaries_ORP_variables.geojson"

gdf = gpd.read_file(input_file)

print(input_file)

# CREATE STANDARDIZED VARIABLES

# Area in km²
gdf["AREA_KM2"] = gdf["SHAPE_Area"] / 1_000_000

# Population density
gdf["POP_DENS"] = (
    gdf["POCET_OBYV"] /
    gdf["AREA_KM2"]
)

# Percentage women
gdf["PCT_WOMEN"] = (
    gdf["ZENY"] /
    gdf["POCET_OBYV"]
) * 100

# Percentage children
gdf["PCT_CHILD"] = (
    gdf["OBYV_0_14"] /
    gdf["POCET_OBYV"]
) * 100

# Percentage working-age
gdf["PCT_WORKING"] = (
    gdf["OBYV_15_64"] /
    gdf["POCET_OBYV"]
) * 100

# Percentage elderly
gdf["PCT_ELDERLY"] = (
    gdf["OBYV_65"] /
    gdf["POCET_OBYV"]
) * 100

# Ageing index
gdf["AGEING_INDEX"] = (
    gdf["OBYV_65"] /
    gdf["OBYV_0_14"]
) * 100

# Dependency ratio
gdf["DEPENDENCY"] = (
    (gdf["OBYV_0_14"] + gdf["OBYV_65"])
    /
    gdf["OBYV_15_64"]
) * 100

# Natural increase
gdf["NATURAL_INC"] = (
    gdf["NAROZENI"] -
    gdf["ZEMRELI"]
)

# Natural increase rate per 1000 inhabitants
gdf["NATURAL_INC_RATE"] = (
    gdf["NATURAL_INC"]
    /
    gdf["POCET_OBYV"]
) * 1000

# Migration balance
gdf["MIG_BAL"] = (
    gdf["PRISTEHOVALI"] -
    gdf["VYSTEHOVALI"]
)

# Migration balance rate per 1000 inhabitants
gdf["MIG_BAL_RATE"] = (
    gdf["MIG_BAL"]
    /
    gdf["POCET_OBYV"]
) * 1000

# SAVE THE STANDARDIZED DATA

gdf.to_file(
    output_file,
    driver="GeoJSON"
)

print(f"Saved to: {output_file}")