"""
NRPZS Hospital Pipeline - Czech Republic
==========================================
Produces two clean GeoJSON files for spatial analysis:
-----------------
  1. emergency_care.geojson - all facilities that receive ambulances / provide emergency care
  2. maternity_care.geojson - all facilities where you go to give birth

Each feature has a "level" field (1 / 2 / 3) that lets you filter by
how comprehensive the care is. See the LEVELS section below for details.

Source: nrpzs.uzis.cz  →  Open data  (UZIS CR, CC BY 4.0)
Data:   place nrpzs_raw.csv in the same folder as this script
Run:    uv run --with pandas --with geopandas getOpenData.py
"""

import re # for parsing/analazying GPS from WKT format
from pathlib import Path # for file paths
import pandas as pd # for CSV loading and DataFrame manipulation
import geopandas as gpd # for GeoDataFrame and spatial data handling
from shapely.geometry import Point # for creating Point geometries from lat/lon


# --- Configuration ---

CSV_PATH   = Path(__file__).parent / "nrpzs_raw.csv"
OUTPUT_DIR = Path(__file__).parent


# ======================
#  LEVELS EXPLAINED
# ======================
#  EMERGENCY CARE = where you go if you need an ambulance or urgent care
#  ─────────────────────────────────────────────────────
#  Level 1 – FULL EMERGENCY DEPARTMENT (urgentní příjem)
#             Facility type: Nemocnice or Fakultní nemocnice
#             Has "urgentní medicína" listed as a specialty
#             These are the ~35 hospitals with a proper 24/7 emergency dept.
#             This is where the ambulance takes you by default.
#
#  Level 2 – ACUTE INPATIENT HOSPITAL (akutní nemocnice bez urgentního příjmu)
#             Facility type: Nemocnice or Fakultní nemocnice
#             Has "akutní lůžková péče intenzivní" (ICU-level acute care)
#             but NOT urgentní medicína.
#             These hospitals take ambulances too, but may triage via
#             a general admission ward rather than a dedicated emergency dept.
#             Roughly 100+ facilities.
#
#  Level 3 – AMBULANCE DISPATCH STATIONS (zdravotnická záchranná služba)
#             Facility type: Zdravotnická zachranná služba
#             These are the ZZS stations – the ambulances themselves.
#             Useful for access/response-time analysis.
#             ~296 stations + 24 výjezdové skupiny (sub-stations).
#
#
#  MATERNITY CARE = where you go to give birth
#  ─────────────────────────────────────────────
#  Level 1 – HOSPITAL-BASED MATERNITY WARD (porodnice)
#             Facility type: Nemocnice or Fakultní nemocnice
#             Has "gynekologie a porodnictví" as a specialty.
#             These are actual hospitals where you give birth.
#             ~86 facilities. This is what we need want for spatial justice analysis.
#
#  Level 2 – HOSPITAL WITH NEONATOLOGY (neonatologie)
#             Same as Level 1 but also has neonatology.
#             Subset of Level 1 – higher-level centres for at-risk births.
#             Use to identify regional perinatal centres.
#
#  Level 3 – STANDALONE GYNAECOLOGY PRACTICES (samostatná ordinace gynekologa)
#             These are outpatient clinics – NOT for giving birth.
#             Useful for antenatal care / access analysis.
#             ~1627 practices.
#
# ======================================


# Step 1: Load CSV with robust encoding handling and print messages about progress

def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}\n"
            "Download from nrpzs.uzis.cz → Otevřená data (open data) and save as nrpzs_raw.csv"
        )
    for enc in ["utf-8-sig", "utf-8", "cp1250"]: # try common encodings for Czech data, starting with UTF-8 with BOM
        try:
            df = pd.read_csv(path, sep=",", encoding=enc, low_memory=False)
            print(f"Loaded {len(df):,} rows  (encoding: {enc})") # print number of rows and encoding used
            return df
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Could not decode CSV.") # if all encodings fail, raise an error


# Step 2: Parse GPS

def parse_gps(df: pd.DataFrame) -> pd.DataFrame:
    """
    ZZ_GPS column format: POINT(latitude longitude)
    ---> NRPZS stores lat first, lon second - opposite of GeoJSON convention.
    We need to convert to standard lon/lat for the Point geometry.
    """
    def extract(val):
        if pd.isna(val):
            return None, None
        m = re.search(r"POINT\(([0-9.\-]+)\s+([0-9.\-]+)\)", str(val))
        return (float(m.group(1)), float(m.group(2))) if m else (None, None)

    coords = df["ZZ_GPS"].apply(extract)
    df = df.copy()
    df["latitude"]  = coords.apply(lambda x: x[0])
    df["longitude"] = coords.apply(lambda x: x[1])
    return df


# Step 3: Build GeoDataFrame with clean columns

def make_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Drop rows with no GPS, select readable columns, build Point geometry."""
    df = df.dropna(subset=["latitude", "longitude"]).copy()

    keep = {
        "ZZ_nazev":              "name",
        "ZZ_druh_nazev":         "facility_type",
        "ZZ_obec":               "city",
        "ZZ_kraj_nazev":         "region",
        "ZZ_okres_nazev":        "district",
        "ZZ_PSC":                "postcode",
        "ZZ_ulice":              "street",
        "ZZ_cislo_domovni_orientacni": "street_number",
        "ZZ_obor_pece":          "specialties",
        "ZZ_forma_pece":         "care_form",
        "poskytovatel_ICO":      "provider_ico",
        "poskytovatel_web":      "website",
        "poskytovatel_telefon":  "phone",
        "latitude":              "latitude",
        "longitude":             "longitude",
    }
    available = {k: v for k, v in keep.items() if k in df.columns} # only keep columns that are actually in the CSV, in case of changes to the source data
    df = df[list(available.keys())].rename(columns=available) # select and rename columns

# Build geometry column from longitude and latitude (the order: Point(lon, lat))
    geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


# Step 4: Emergency care filters

def build_emergency(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Returns a GeoDataFrame with all emergency-relevant facilities.
    Column 'level' values:
      1 = hospital with formal emergency department (urgentní medicína)
      2 = hospital with acute/ICU inpatient care but no dedicated ED
      3 = ambulance dispatch station (ZZS)
    """
    hosp_types  = {"Nemocnice", "Fakultní nemocnice"}
    zzs_types   = {"Zdravotnická zachranná služba", "Výjezdová skupina záchranné služby"}
    obor        = gdf["specialties"].fillna("")
    forma       = gdf["care_form"].fillna("")
    ftype       = gdf["facility_type"].fillna("")

    # Level 1: hospitals with urgent medicine specialty
    mask_l1 = ftype.isin(hosp_types) & obor.str.contains("urgentní medicína", case=False, na=False)

    # Level 2: hospitals with ICU-level acute inpatient care, but NOT level 1
    mask_l2 = (
        ftype.isin(hosp_types) &
        forma.str.contains("akutní lůžková péče intenzivní", case=False, na=False) &
        ~mask_l1
    )

    # Level 3: ambulance stations
    mask_l3 = ftype.isin(zzs_types)

    combined = gdf[mask_l1 | mask_l2 | mask_l3].copy()
    combined["level"] = 0
    combined.loc[mask_l1[combined.index], "level"] = 1
    combined.loc[mask_l2[combined.index], "level"] = 2
    combined.loc[mask_l3[combined.index], "level"] = 3

    combined["level_label"] = combined["level"].map({
        1: "Emergency department (urgentní medicína)",
        2: "Acute hospital - ICU-level, no dedicated ED",
        3: "Ambulance dispatch station (ZZS)",
    })

    print(f"\nEmergency care:") # print summary of how many facilities at each level, with labels
    for lvl in [1, 2, 3]:
        n = (combined["level"] == lvl).sum()
        print(f"  Level {lvl}: {n:>4}  {combined[combined['level']==lvl]['level_label'].iloc[0]}")
    print(f"  TOTAL:  {len(combined)}")

    return combined.sort_values("level").reset_index(drop=True)


# --- Step 5: Maternity care filters ---

def build_maternity(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Returns a GeoDataFrame with all maternity-relevant facilities.
    Column 'level' values:
      1 = hospital with maternity ward and neonatology  (perinatal centre / level III)
      2 = hospital with maternity ward, no neonatology  (standard porodnice / level I-II)
      3 = standalone gynaecology outpatient practice    (antenatal care only, no births)
    """
    hosp_types  = {"Nemocnice", "Fakultní nemocnice"}
    obor        = gdf["specialties"].fillna("")
    ftype       = gdf["facility_type"].fillna("")

    # Level 1: hospital with both obstetrics AND neonatology → regional perinatal centre
    mask_l1 = (
        ftype.isin(hosp_types) &
        obor.str.contains("gynekologie a porodnictví", case=False, na=False) &
        obor.str.contains("neonatologie", case=False, na=False)
    )

    # Level 2: hospital with obstetrics but no neonatology → standard maternity ward
    mask_l2 = (
        ftype.isin(hosp_types) &
        obor.str.contains("gynekologie a porodnictví", case=False, na=False) &
        ~obor.str.contains("neonatologie", case=False, na=False)
    )

    # Level 3: standalone gynaecology outpatient practice (prenatal care, not births)
    mask_l3 = ftype == "Samostatná ordinace PL - gynekologa"

# Combine and assign levels
    combined = gdf[mask_l1 | mask_l2 | mask_l3].copy()
    combined["level"] = 0
    combined.loc[mask_l1[combined.index], "level"] = 1
    combined.loc[mask_l2[combined.index], "level"] = 2
    combined.loc[mask_l3[combined.index], "level"] = 3

# Map level to human-readable labels for summary printing
    combined["level_label"] = combined["level"].map({
        1: "Hospital maternity ward + neonatology (perinatal centre)",
        2: "Hospital maternity ward only (standard porodnice)",
        3: "Outpatient gynaecology practice (no births)",
    })

    print(f"\nMaternity care:")
    for lvl in [1, 2, 3]:
        n = (combined["level"] == lvl).sum()
        print(f"  Level {lvl}: {n:>4}  {combined[combined['level']==lvl]['level_label'].iloc[0]}")
    print(f"  TOTAL:  {len(combined)}")

    return combined.sort_values("level").reset_index(drop=True)


# --- Step 6: Save ---

def save(gdf: gpd.GeoDataFrame, name: str, output_dir: Path) -> None: # save GeoDataFrame to GeoJSON with a given name in the output directory
    path = output_dir / f"{name}.geojson" # build the output path by combining the output directory and the name with .geojson extension
    gdf.to_file(path, driver="GeoJSON")
    print(f"  Saved → {path.name}  ({len(gdf)} features)")


# --- Main ---
if __name__ == "__main__":
    print("=== NRPZS Pipeline ===\n")

    df  = load_csv(CSV_PATH)
    df  = parse_gps(df)
    gdf = make_gdf(df)

    emergency = build_emergency(gdf)
    maternity = build_maternity(gdf)

    print("\nSaving:")
    save(emergency, "emergency_care", OUTPUT_DIR)
    save(maternity, "maternity_care", OUTPUT_DIR)

    print("\nDone. Load in Python with:")
    print("  import geopandas as gpd")
    print("  em = gpd.read_file('emergency_care.geojson')")
    print("  ma = gpd.read_file('maternity_care.geojson')")
    print("  # filter to just hospitals (level 1+2):")
    print("  em_hospitals = em[em['level'] <= 2]")
    print("  # filter to just birth facilities (level 1+2):")
    print("  ma_births    = ma[ma['level'] <= 2]")