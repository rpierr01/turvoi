import os, json, io, zipfile
import dash
from dash import html, dcc, Output, Input
from dash.dcc import send_bytes, send_string
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from flask import send_file
from services.annotation_io import load_annotations, IMAGES_DIR
from PIL import Image

# Page stats
dash.register_page(__name__, path="/stats", name="Stats")

# --- Helper robuste ---
def safe_load(s):
    """Décode récursivement une chaîne JSON jusqu’à obtenir un dict."""
    try:
        data = s
        while isinstance(data, str):
            data = data.strip().lstrip('"').rstrip('"')
            data = data.replace('\\"', '"')
            data = json.loads(data)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def count_objects(boxes_json):
    """Compte toutes les annotations.
       - rect/circle/image → 1
       - path (crayon) → chaque trait compte
    """
    data = safe_load(boxes_json)
    objs = data.get("objects", [])
    count = 0
    for o in objs:
        if o.get("type") == "path" and "path" in o:
            count += len(o["path"])  # plusieurs coups de crayon
        else:
            count += 1
    return count

# --- Graphique : nombre d’annotations par image ---
def fig_per_image():
    df = load_annotations()
    if df.empty:
        return px.bar(title="Aucune annotation disponible")

    df["n_boxes"] = df["boxes_json"].apply(count_objects)
    counts = df.groupby("image")["n_boxes"].sum().reset_index()

    if counts.empty:
        return px.bar(title="Aucune annotation détectée")

    fig = px.bar(counts, x="image", y="n_boxes", text="n_boxes")
    fig.update_layout(
        xaxis_title="Image",
        yaxis_title="Nombre total d’annotations",
        xaxis_tickangle=-45
    )
    return fig

# --- Graphique : nombre d’annotations par utilisateur ---
def fig_per_user():
    df = load_annotations()
    if df.empty:
        return px.bar(title="Aucune annotation disponible")

    df["n_boxes"] = df["boxes_json"].apply(count_objects)
    counts = df.groupby("annotator")["n_boxes"].sum().reset_index()

    if counts.empty:
        return px.bar(title="Aucune annotation détectée")

    fig = px.bar(counts, x="annotator", y="n_boxes", text="n_boxes", color="annotator")
    fig.update_layout(
        xaxis_title="Annotateur",
        yaxis_title="Nombre total d’annotations"
    )
    return fig

# --- Tableau HTML : images sans annotations ---
def table_unannotated():
    all_imgs = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    df = load_annotations()

    if df.empty:
        missing = all_imgs
    else:
        annotated = df.loc[df["boxes_json"].apply(count_objects) > 0, "image"].unique().tolist()
        missing = [img for img in all_imgs if img not in annotated]

    if not missing:
        return html.Div("🎉 Toutes les images ont été annotées !", className="text-success")

    rows = [html.Tr([html.Td(img)]) for img in missing]
    return html.Table(
        [html.Thead(html.Tr([html.Th("Images non annotées")]))] +
        [html.Tbody(rows)],
        style={"width": "100%", "border": "1px solid #ccc", "textAlign": "center"}
    )

# --- Exports ---
def generate_coco():
    df = load_annotations()
    images, annotations = [], []
    ann_id = 1

    for idx, row in df.iterrows():
        img_name = row["image"]
        path = os.path.join(IMAGES_DIR, img_name)
        if not os.path.exists(path):
            continue

        w, h = Image.open(path).size
        img_id = idx + 1
        images.append({"id": img_id, "file_name": img_name, "width": w, "height": h})

        data = safe_load(row["boxes_json"])
        for obj in data.get("objects", []):
            if obj.get("type") == "rect":
                x, y, bw, bh = obj.get("left", 0), obj.get("top", 0), obj.get("width", 0), obj.get("height", 0)
                annotations.append({
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": 1,
                    "bbox": [x, y, bw, bh],
                    "area": bw * bh,
                    "iscrowd": 0
                })
                ann_id += 1

    coco = {"images": images, "annotations": annotations, "categories": [{"id": 1, "name": "object"}]}
    return json.dumps(coco, indent=2)

def generate_yolo_zip():
    df = load_annotations()
    mem_zip = io.BytesIO()

    with zipfile.ZipFile(mem_zip, "w") as zf:
        for idx, row in df.iterrows():
            img_name = row["image"]
            path = os.path.join(IMAGES_DIR, img_name)
            if not os.path.exists(path):
                continue

            w, h = Image.open(path).size
            data = safe_load(row["boxes_json"])
            lines = []
            for obj in data.get("objects", []):
                if obj.get("type") == "rect":
                    x, y, bw, bh = obj.get("left", 0), obj.get("top", 0), obj.get("width", 0), obj.get("height", 0)
                    xc, yc = (x + bw / 2) / w, (y + bh / 2) / h
                    nw, nh = bw / w, bh / h
                    lines.append(f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")
            if lines:
                txt_name = os.path.splitext(img_name)[0] + ".txt"
                zf.writestr(txt_name, "\n".join(lines))

    mem_zip.seek(0)
    return mem_zip

# --- Layout ---
layout = dbc.Container([
    dcc.Interval(id="refresh-stats", interval=3000, n_intervals=0),

    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("📊 Nombre d’annotations par image"),
            dcc.Graph(id="graph-per-image")
        ], className="card p-3"), md=12),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("👤 Nombre d’annotations par utilisateur"),
            dcc.Graph(id="graph-per-user")
        ], className="card p-3"), md=6),

        dbc.Col(dbc.Card([
            html.H5("📋 Images non annotées"),
            html.Div(id="table-unannotated")
        ], className="card p-3"), md=6),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("📤 Export des annotations"),
            dbc.Button("Télécharger en COCO", id="btn-export-coco", color="primary", className="me-2"),
            dbc.Button("Télécharger en YOLO", id="btn-export-yolo", color="secondary"),
            dcc.Download(id="download-export")
        ], className="card p-3"), md=12),
    ]),
], fluid=True)

# --- Callback ---
def register_callbacks(app):
    @app.callback(
        Output("graph-per-image", "figure"),
        Output("graph-per-user", "figure"),
        Output("table-unannotated", "children"),
        Input("refresh-stats", "n_intervals")
    )
    def update_stats(_):
        return fig_per_image(), fig_per_user(), table_unannotated()

    @app.callback(
        Output("download-export", "data"),
        Input("btn-export-coco", "n_clicks"),
        Input("btn-export-yolo", "n_clicks"),
        prevent_initial_call=True
    )
    def export_files(n_coco, n_yolo):
        ctx = dash.callback_context
        if not ctx.triggered:
            return None
        btn = ctx.triggered[0]["prop_id"].split(".")[0]

        if btn == "btn-export-coco":
            coco_str = generate_coco()
            return send_string(lambda: coco_str, "annotations_coco.json")

        elif btn == "btn-export-yolo":
            zip_bytes = generate_yolo_zip()
            return send_bytes(lambda b: b.write(zip_bytes.getvalue()), "annotations_yolo.zip")
