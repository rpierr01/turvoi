import io
import base64
import re
import torch
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from dash import html, dcc, Output, Input, State, register_page
import dash_bootstrap_components as dbc
from huggingface_hub import hf_hub_download
from ultralytics import YOLO
import torchvision.transforms as T
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from transformers import TrOCRProcessor, VisionEncoderDecoderModel, AutoFeatureExtractor, AutoModelForImageClassification

# Register this file as a Dash page
register_page(__name__, path="/le-futur", name="Le Futur")

# --- Configuration ---
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- Modèle Faster R-CNN pour la détection de voitures ---
model_car = fasterrcnn_resnet50_fpn(pretrained=True).to(device)
model_car.eval()
COCO_CATEGORY_NAMES = ['__background__','person','bicycle','car','motorcycle','airplane',
                       'bus','train','truck','boat']
CAR_CLASS_IDS = {3}  # ID pour "car" dans COCO
transform = T.Compose([T.ToTensor()])

# --- YOLOv8 pour détection de plaques ---
model_path_plate = hf_hub_download(repo_id="MKgoud/License-Plate-Recognizer", filename="LP-detection.pt")
model_plate = YOLO(model_path_plate)

# --- TrOCR pour lecture de plaques ---
processor_trocr = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten").to(device)
trocr_model.eval()

# --- Classification marque : modèle CarViT uniquement ---
feature_extractor_brand = AutoFeatureExtractor.from_pretrained("abdusah/CarViT")
model_brand = AutoModelForImageClassification.from_pretrained("abdusah/CarViT").to(device)
model_brand.eval()

# --- Regex multi‐pays pour plaques ---
PLATE_REGEXES = {
    "FR": r"[A-Z]{2}-\d{3}-[A-Z]{2}",
    "DE": r"[A-Z]{1,3}-[A-Z]{1,2}\d{1,4}",
    "US": r"[A-Z0-9]{1,7}"
}

def detect_country_from_text(text):
    text = text.replace(" ", "").replace("-", "")
    if len(text) == 7:
        return "US"
    elif len(text) == 6:
        return "FR"
    elif len(text) <= 8:
        return "DE"
    return "US"

# --- Fonctions de détection et lecture ---
def run_inference_car(pil_image, score_threshold=0.5):
    img = transform(pil_image).to(device)
    with torch.no_grad():
        preds = model_car([img])[0]
    results = []
    for box, label, score in zip(preds['boxes'].cpu(), preds['labels'].cpu(), preds['scores'].cpu()):
        if score < score_threshold or int(label) not in CAR_CLASS_IDS:
            continue
        results.append({'box': box.numpy().tolist(), 'label': COCO_CATEGORY_NAMES[int(label)], 'score': float(score)})
    return results

def deskew_plate(plate_pil):
    plate_np = np.array(plate_pil.convert("L"))
    coords = np.column_stack(np.where(plate_np > 0))
    if coords.shape[0] == 0:
        return plate_np
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    (h, w) = plate_np.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(plate_np, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def read_plate_trocr_adaptive(plate_pil):
    if plate_pil.mode != "RGB": plate_pil = plate_pil.convert("RGB")
    pixel_values = processor_trocr(images=plate_pil, return_tensors="pt").pixel_values.to(device)
    with torch.no_grad():
        generated_ids = trocr_model.generate(pixel_values)
    plate_text = processor_trocr.batch_decode(generated_ids, skip_special_tokens=True)[0]
    plate_text = re.sub(r"[^A-Z0-9]", "", plate_text.upper())
    country = detect_country_from_text(plate_text)
    regex = PLATE_REGEXES.get(country, PLATE_REGEXES["US"])
    return plate_text if re.match(regex, plate_text) else None

def detect_plate_yolo(car_pil):
    img_np = np.array(car_pil)
    results = model_plate.predict(source=img_np, verbose=False)[0]
    if len(results.boxes) == 0:
        return None
    x1, y1, x2, y2 = map(int, results.boxes.xyxy[0].cpu().numpy())
    plate_crop = car_pil.crop((x1, y1, x2, y2))
    gray = cv2.cvtColor(np.array(plate_crop), cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    plate_pil_thresh = Image.fromarray(thresh).convert("RGB")
    plate_text = read_plate_trocr_adaptive(plate_pil_thresh)
    return {'plate_box':[x1, y1, x2, y2], 'plate_text':plate_text}

def identify_car_brand(car_pil):
    if car_pil.mode != "RGB":
        car_pil = car_pil.convert("RGB")
    inputs = feature_extractor_brand(images=car_pil, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model_brand(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
    pred_id = int(probs.argmax(-1)[0].cpu().numpy())
    conf = float(probs[0, pred_id].cpu().numpy())
    label = model_brand.config.id2label[pred_id]
    brand = label.split()[0] if label else "Unknown"
    return {"brand": brand, "confidence": conf, "source": "CarViT"}

def draw_boxes(pil_image, detections, plate_infos=None, brand_infos=None):
    draw = ImageDraw.Draw(pil_image)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font = ImageFont.load_default()
    for i, d in enumerate(detections):
        x1, y1, x2, y2 = d['box']
        draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=3)
        draw.text((x1, max(0, y1-12)), f"{d['label']} {d['score']:.2f}", fill="red", font=font)
        if plate_infos and plate_infos[i]:
            pi = plate_infos[i]
            if pi.get('plate_box'):
                px1, py1, px2, py2 = pi['plate_box']
                abs_px1, abs_py1 = int(x1 + px1), int(y1 + py1)
                abs_px2, abs_py2 = int(x1 + px2), int(y1 + py2)
                draw.rectangle([(abs_px1, abs_py1), (abs_px2, abs_py2)], outline="yellow", width=2)
                txt = pi.get('plate_text') or "?"
                draw.text((abs_px1, max(0, abs_py1-14)), f"Plaque: {txt}", fill="yellow", font=font)
        if brand_infos and brand_infos[i]:
            bi = brand_infos[i]
            brand = bi.get("brand")
            conf = bi.get("confidence")
            source = bi.get("source", "")
            if brand:
                draw.text((x1, y2+4), f"Marque: {brand} ({conf:.2f}) [{source}]", fill="blue", font=font)
    return pil_image

# --- Page layout (no Dash app instantiation here) ---
layout = dbc.Container([
    html.H1("Détecteur de Voitures, Plaques & Marques (CarViT) — Le Futur"),
    dcc.Upload(id='lefutur-upload-image',
               children=html.Div(['Glissez-déposez ou cliquez pour sélectionner une image']),
               style={'width':'100%','height':'80px','lineHeight':'80px','borderWidth':'1px','borderStyle':'dashed',
                      'borderRadius':'5px','textAlign':'center','margin':'10px'}, multiple=False),
    dbc.Row(dbc.Col(html.Div(id='lefutur-output-image'), width=12)),
], fluid=True)

def parse_contents(contents):
    header, encoded = contents.split(",", 1)
    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")

# Callback function (will be registered by register_callbacks)
def update_output(contents, filename):
    if contents is None:
        return html.Div("Aucune image téléchargée.")
    pil = parse_contents(contents)
    detections = run_inference_car(pil, score_threshold=0.6)
    if detections:
        detections = [max(detections, key=lambda d: d['score'])]
    plate_infos, brand_infos = [], []
    for d in detections:
        x1, y1, x2, y2 = map(int, d['box'])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(pil.width, x2), min(pil.height, y2)
        car_crop = pil.crop((x1, y1, x2, y2))
        plate_info = detect_plate_yolo(car_crop)
        brand_info = identify_car_brand(car_crop)
        plate_infos.append(plate_info)
        brand_infos.append(brand_info)
    pil_out = draw_boxes(pil.copy(), detections, plate_infos, brand_infos)
    buffer = io.BytesIO()
    pil_out.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    img_src = f"data:image/png;base64,{img_b64}"

    lines = []
    for i, d in enumerate(detections):
        line = f"{d['label']} {d['score']:.2f}"
        pt = plate_infos[i].get('plate_text') if plate_infos[i] else None
        if pt:
            line += f" — plaque: {pt}"
        br = brand_infos[i].get("brand") if brand_infos[i] else None
        confb = brand_infos[i].get("confidence") if brand_infos[i] else None
        srcb = brand_infos[i].get("source") if brand_infos[i] else ""
        if br:
            line += f" — marque: {br} ({confb:.2f}) [{srcb}]"
        lines.append(html.Li(line))

    return [
        html.H5(f"Fichier: {filename}"),
        html.Img(src=img_src, style={'maxWidth':'100%'}),
        html.Ul(lines) if lines else html.P("Aucune voiture détectée.")
    ]

# Function to attach callbacks to the parent app
def register_callbacks(app):
    app.callback(
        Output('lefutur-output-image','children'),
        Input('lefutur-upload-image','contents'),
        State('lefutur-upload-image','filename')
    )(update_output)