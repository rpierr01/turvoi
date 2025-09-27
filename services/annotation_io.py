import os, json
import pandas as pd
from datetime import datetime

# Dossiers (on respecte data/cars_detection/ existant)
DATA_DIR = "data"
IMAGES_DIR = os.path.join(DATA_DIR, "cars_detection")
ANN_PATH = os.path.join(DATA_DIR, "annotations.csv")

# ajout de la colonne id en première position
COLUMNS = ["id", "image", "annotator", "timestamp", "boxes_json"]

def ensure_dirs():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

def list_images():
    """Liste triée des fichiers image dans data/cars_detection/."""
    ensure_dirs()
    imgs = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    imgs.sort()
    return imgs

def init_csv():
    ensure_dirs()
    if not os.path.exists(ANN_PATH):
        # on initialise avec le bon en-tête
        pd.DataFrame(columns=COLUMNS).to_csv(ANN_PATH, index=False)

def _read_df():
    init_csv()
    df = pd.read_csv(ANN_PATH)
    # suppression propre d'une éventuelle colonne level_0
    return df.drop(columns=["level_0"], errors="ignore")

def save_annotation(image: str, annotator: str, boxes_json: dict):
    """Append une annotation (json dash-canvas) dans le CSV."""
    df = _read_df()
    # calcul de l'ID suivant
    next_id = int(df["id"].max()) + 1 if not df.empty else 1
    row = {
        "id": next_id,
        "image": image,
        "annotator": annotator,
        "timestamp": datetime.utcnow().isoformat(),
        "boxes_json": json.dumps(boxes_json or {})
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(ANN_PATH, index=False)

def load_annotations(image: str = None, annotator: str = None):
    """Charge les annotations (filtrables)."""
    df = _read_df()
    if image:
        df = df[df["image"] == image]
    if annotator:
        df = df[df["annotator"] == annotator]
    return df

# nouvelle fonction pour écraser le CSV avec un DataFrame complet (incluant 'id')
def save_annotations(df: pd.DataFrame):
    """Overwrite the CSV with the given DataFrame."""
    df.to_csv(ANN_PATH, index=False)
