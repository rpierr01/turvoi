import os, json
import pandas as pd
from typing import Dict

# Export COCO minimal : une catégorie "car", bboxes (x,y,w,h)
def to_coco(df: pd.DataFrame, images_dir: str) -> Dict:
    images, annotations = [], []
    categories = [{"id": 1, "name": "car"}]
    image_id_map, ann_id = {}, 1

    files = sorted(df["image"].dropna().unique().tolist())
    for i, fname in enumerate(files, start=1):
        image_id_map[fname] = i
        try:
            from PIL import Image
            w, h = Image.open(os.path.join(images_dir, fname)).size
        except Exception:
            w, h = None, None
        images.append({"id": i, "file_name": fname, "width": w, "height": h})

    for _, row in df.iterrows():
        img = row["image"]
        data = json.loads(row["boxes_json"]) or {}
        for s in data.get("objects", []):
            if s.get("type") != "rect":
                continue
            x, y, w, h = s.get("x", 0), s.get("y", 0), s.get("width", 0), s.get("height", 0)
            annotations.append({
                "id": ann_id,
                "image_id": image_id_map[img],
                "category_id": 1,
                "bbox": [x, y, w, h],
                "area": w * h,
                "iscrowd": 0
            })
            ann_id += 1

    return {"images": images, "annotations": annotations, "categories": categories}
