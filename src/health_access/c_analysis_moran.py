import logging
import esda
import pandas as pd
import libpysal
from typing import Dict, List

logger = logging.getLogger(__name__)

def create_weights_matrices(gdf) -> Dict:
    """
    Creates different spatial weights matrices to test sensitivity.
    """
    logger.info("Creating spatial weights matrices...")
    return {
        "Queen": libpysal.weights.Queen.from_dataframe(gdf, use_index=True),
        "Rook": libpysal.weights.Rook.from_dataframe(gdf, use_index=True),
        "KNN (k=5)": libpysal.weights.KNN.from_dataframe(gdf, k=5, use_index=True)
    }

def compute_global_morans(gdf, w, variable: str) -> esda.Moran:
    logger.info("Computing Global Moran's I - variable: %s", variable)
    y = gdf[variable].values
    # Ensure weights are row-standardized for correct interpretation
    w.transform = 'r' 
    return esda.Moran(y, w)

def compute_lisa(gdf, w, variable: str): # Remove -> pd.DataFrame hint
    logger.info("Computing LISA - variable: %s", variable)
    y = gdf[variable].values
    w.transform = 'r'
    
    lisa = esda.Moran_Local(y, w) # This is the object with .q
    
    mapping = {1: 'Hotspot (HH)', 2: 'Low-High (LH)', 3: 'Coldspot (LL)', 4: 'High-Low (HL)'}
    
    results_gdf = gdf.copy()
    results_gdf['lisa_cluster'] = [mapping[q] if p < 0.05 else 'Insignificant' 
                                   for q, p in zip(lisa.q, lisa.p_sim)]
    results_gdf['lisa_p_value'] = lisa.p_sim
    results_gdf['lisa_stat'] = lisa.Is
    
    # RETURN BOTH: the modified GDF and the raw LISA object
    return results_gdf, lisa

def build_morans_table(gdf, weights_dict: Dict, variable: str) -> pd.DataFrame:
    logger.info("Building Moran's I comparison table - variable: %s", variable)
    results = []

    for name, w in weights_dict.items():
        mi = compute_global_morans(gdf, w, variable)
        results.append({
            "W Type": name,
            "Moran's I": round(mi.I, 4),
            "p-value": round(mi.p_sim, 4),
            "z-score": round(mi.z_sim, 4),
            "Significant": "yes" if mi.p_sim < 0.05 else "no",
        })

    return pd.DataFrame(results)
