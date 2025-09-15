import json
import pandas as pd
from utils.geometry import greedy_match_iou
from .annotation_io import load_annotations, list_images

def dataset_progress():
    """Retourne (liste_images, nb_enregistrements_par_image)."""
    imgs = list_images()
    df = load_annotations()
    completed = df.groupby("image").size().reindex(imgs).fillna(0).astype(int)
    return imgs, completed

def by_annotator_counts():
    df = load_annotations()
    if df.empty:
        return pd.Series(dtype=int)
    return df.groupby("annotator").size().sort_values(ascending=False)

def iaa_summary(iou_threshold: float = 0.5):
    """Calcule IoU moyen par image entre annotateurs (greedy matching)."""
    df = load_annotations()
    if df.empty:
        return {"mean_iou": None, "per_image": {}}
    per_image = {}
    for img, group in df.groupby("image"):
        ann = {}
        for _, row in group.iterrows():
            data = json.loads(row["boxes_json"]) or {}
            boxes = []
            for s in data.get("objects", []):
                if s.get("type") == "rect":
                    x, y = s.get("x", 0), s.get("y", 0)
                    w, h = s.get("width", 0), s.get("height", 0)
                    boxes.append((x, y, x + w, y + h))
            ann[row["annotator"]] = boxes
        annotators = list(ann.keys())
        if len(annotators) < 2:
            per_image[img] = {"mean_iou": None, "flag": False}
            continue
        ious = []
        for i in range(len(annotators)):
            for j in range(i + 1, len(annotators)):
                iou = greedy_match_iou(ann[annotators[i]], ann[annotators[j]])
                if iou is not None:
                    ious.append(iou)
        mean_iou = sum(ious) / len(ious) if ious else None
        per_image[img] = {"mean_iou": mean_iou, "flag": (mean_iou is not None and mean_iou < iou_threshold)}
    values = [v["mean_iou"] for v in per_image.values() if v["mean_iou"] is not None]
    overall = sum(values)/len(values) if values else None
    return {"mean_iou": overall, "per_image": per_image}
