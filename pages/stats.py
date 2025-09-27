import os
import json
import dash
from dash import html, dcc, Output, Input
from dash.dcc import send_string
import dash_bootstrap_components as dbc
import plotly.express as px
from services.json_annotations import get_all_annotations, IMAGES_DIR
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

def count_objects(rectangles):
    """Compte les rectangles dans une liste."""
    return len(rectangles)

# --- Graphique : nombre d’annotations par image ---
def fig_per_image():
    annotations = get_all_annotations()
    if not annotations:
        print("DEBUG: Aucune annotation trouvée dans get_all_annotations()")  # Ajout d'un log
        return px.bar(title="Aucune annotation disponible")

    # Compter les rectangles par image
    counts = {}
    for ann in annotations:
        image = ann["image"]
        counts[image] = counts.get(image, 0) + len(ann["rectangles"])

    counts_df = [{"image": img, "n_boxes": count} for img, count in counts.items()]
    counts_df = sorted(counts_df, key=lambda x: x["image"])

    print(f"DEBUG: Données pour fig_per_image: {counts_df}")  # Ajout d'un log
    fig = px.bar(counts_df, x="image", y="n_boxes", text="n_boxes")
    fig.update_layout(
        xaxis_title="Image",
        yaxis_title="Nombre total d’annotations",
        xaxis_tickangle=-45
    )
    return fig

# --- Graphique : nombre d’annotations par utilisateur ---
def fig_per_user():
    annotations = get_all_annotations()
    if not annotations:
        print("DEBUG: Aucune annotation trouvée dans get_all_annotations()")  # Ajout d'un log
        return px.bar(title="Aucune annotation disponible")

    # Compter les rectangles par annotateur
    counts = {}
    for ann in annotations:
        annotator = ann["annotator"]
        counts[annotator] = counts.get(annotator, 0) + len(ann["rectangles"])

    counts_df = [{"annotator": user, "n_boxes": count} for user, count in counts.items()]
    counts_df = sorted(counts_df, key=lambda x: x["annotator"])

    print(f"DEBUG: Données pour fig_per_user: {counts_df}")  # Ajout d'un log
    fig = px.bar(counts_df, x="annotator", y="n_boxes", text="n_boxes", color="annotator")
    fig.update_layout(
        xaxis_title="Annotateur",
        yaxis_title="Nombre total d’annotations"
    )
    return fig

# --- Tableau HTML : images sans annotations ---
def table_unannotated():
    all_imgs = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    annotations = get_all_annotations()

    annotated_images = {ann["image"] for ann in annotations}
    missing = [img for img in all_imgs if img not in annotated_images]

    print(f"DEBUG: Images non annotées: {missing}")  # Ajout d'un log
    if not missing:
        return html.Div("🎉 Toutes les images ont été annotées !", className="text-success")

    rows = [html.Tr([html.Td(img)]) for img in missing]
    return html.Table(
        [html.Thead(html.Tr([html.Th("Images non annotées")]))] +
        [html.Tbody(rows)],
        style={"width": "100%", "border": "1px solid #ccc", "textAlign": "center"}
    )

# --- Export COCO (avec toutes les annotations JSON) ---
def generate_coco():
    """Génère un JSON COCO à partir des annotations JSON."""
    try:
        annotations = get_all_annotations()
        images = []
        coco_annotations = []
        ann_id = 1

        # Regrouper les annotations par image
        grouped_annotations = {}
        for ann in annotations:
            if ann["image"] not in grouped_annotations:
                grouped_annotations[ann["image"]] = []
            grouped_annotations[ann["image"]].append(ann)

        # Construire les données COCO
        for img_id, (image_name, anns) in enumerate(grouped_annotations.items(), start=1):
            # Ajouter les métadonnées de l'image
            path = os.path.join(IMAGES_DIR, image_name)
            if not os.path.exists(path):
                continue
            w, h = Image.open(path).size
            images.append({
                "id": img_id,
                "file_name": image_name,
                "width": w,
                "height": h
            })

            # Ajouter les annotations pour cette image
            for ann in anns:
                for rect in ann["rectangles"]:
                    coco_annotations.append({
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": 1,  # Une seule catégorie pour les rectangles
                        "bbox": [rect["x"], rect["y"], rect["width"], rect["height"]],
                        "area": rect["width"] * rect["height"],
                        "iscrowd": 0
                    })
                    ann_id += 1

        coco = {
            "images": images,
            "annotations": coco_annotations,
            "categories": [{"id": 1, "name": "object"}]
        }
        return json.dumps(coco, indent=2, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"Erreur lors de la génération COCO: {e}")

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
            dbc.Button("Télécharger en COCO JSON", id="btn-export-coco", color="primary"),
            dcc.Download(id="download-coco-json")
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
        print("DEBUG: Mise à jour des statistiques")  # Ajout d'un log
        return fig_per_image(), fig_per_user(), table_unannotated()

    @app.callback(
        Output("download-coco-json", "data"),
        Input("btn-export-coco", "n_clicks"),
        prevent_initial_call=True
    )
    def export_coco(n_clicks):
        try:
            coco_data = generate_coco()
            return send_string(coco_data, "annotations_coco.json")
        except Exception as e:
            return send_string(f"Erreur export : {e}", "erreur.txt")