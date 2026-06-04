import logging
import geopandas as gpd

logger = logging.getLogger(__name__)

def load_database(filename="data.geojson") -> gpd.GeoDataFrame:
    logger.info("---- loading {} ----".format(filename))
    polygons = gpd.read_file("data/"+filename)
    logger.info("---- adjusting projection ----")
    polygons = polygons.to_crs(epsg=25832)
    return polygons

