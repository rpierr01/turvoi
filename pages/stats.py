import os
import json
import dash
from dash import html, dcc, Output, Input
from dash.dcc import send_string
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from services.annotation_io import load_annotations, IMAGES_DIR
from PIL import Image

# Page stats : enregistrement de la page dans Dash
dash.register_page(__name__, path="/stats", name="Stats")

# --- Helper robuste ---
def safe_load(s):
    """Décodage récursif d'une chaîne JSON (retourne un dict ou {})."""
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
    """Compte les objets dans boxes_json (rect/circle/image = 1, path = len(path))."""
    data = safe_load(boxes_json)
    objs = data.get("objects", [])
    count = 0
    for o in objs:
        if not o.get("visible", True):
            continue
        obj_type = o.get("type")
        if obj_type in {"rect", "circle", "image"}:
            count += 1
        elif obj_type == "path" and "path" in o:
            count += len(o["path"])
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

# --- Export COCO (avec toutes les colonnes du CSV, y compris boxes_json) ---
def generate_coco():
    """Génère un JSON COCO ; chaque entrée 'images' contient toutes les colonnes du CSV (boxes_json incluse)."""
    try:
        # Charge le CSV mis à jour avec la colonne 'id'
        df = load_annotations()
        images = []
        annotations = []
        ann_id = 1

        for idx, row in df.iterrows():
            img_name = row["image"]
            path = os.path.join(IMAGES_DIR, img_name)
            if not os.path.exists(path):
                # On ignore les lignes dont le fichier image est absent
                continue

            w, h = Image.open(path).size
            img_id = idx + 1

            # Construire l'entrée image en incluant toutes les colonnes CSV
            img_info = {
                "id": img_id,
                "file_name": img_name,
                "width": w,
                "height": h,
            }
            # Inclure explicitement toutes les colonnes du CSV (y compris boxes_json)
            for col in df.columns:
                # On récupère la valeur brute du CSV
                img_info[col] = row[col]

            images.append(img_info)

            # Construire les annotations (on accepte rect et image comme bbox)
            data = safe_load(row["boxes_json"])
            for obj in data.get("objects", []):
                if obj.get("type") in {"rect", "image", "circle"}:
                    x = obj.get("left", 0)
                    y = obj.get("top", 0)
                    bw = obj.get("width", 0)
                    bh = obj.get("height", 0)
                    annotations.append({
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": 1,
                        "bbox": [x, y, bw, bh],
                        "area": bw * bh,
                        "iscrowd": 0
                    })
                    ann_id += 1

        coco = {
            "images": images,
            "annotations": annotations,
            "categories": [{"id": 1, "name": "object"}]
        }
        # ensure_ascii=False pour conserver les caractères non-ASCII (ex: emoji dans chemins)
        return json.dumps(coco, indent=2, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"Erreur lors de la génération COCO: {e}")

# --- Layout (YOLO supprimé) ---
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
            dbc.Button("Télécharger en COCO", id="btn-export-coco", color="primary"),
            dcc.Download(id="download-export")
        ], className="card p-3"), md=12),
    ]),
], fluid=True)

# --- Callbacks ---
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
        prevent_initial_call=True
    )
    def export_coco(n_coco):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update
        btn = ctx.triggered[0]["prop_id"].split(".")[0]

        try:
            if btn == "btn-export-coco":
                coco_data = generate_coco()
                return send_string(coco_data, "annotations_coco.json")
        except Exception as e:
            return send_string(f"Erreur export : {e}", "erreur.txt")