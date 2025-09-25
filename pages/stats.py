import os, json, io, zipfile          # opérations fichiers, JSON, mémoire, zip
import dash                           # framework Dash
from dash import html, dcc, Output, Input
from dash.dcc import send_bytes, send_string
import dash_bootstrap_components as dbc
import plotly.express as px           # génération de graphiques
import pandas as pd
from flask import send_file
from services.annotation_io import load_annotations, IMAGES_DIR  # fonctions du projet
from PIL import Image                 # pour lire tailles d'images

# Page stats : enregistrement de la page dans Dash
dash.register_page(__name__, path="/stats", name="Stats")

# --- Helper robuste ---
def safe_load(s):
    """Décode récursivement une chaîne JSON jusqu’à obtenir un dict.
       Utilisé pour parser le contenu stocké dans la colonne boxes_json.
       Retourne {} en cas d'erreur ou si le résultat n'est pas un dict.
    """
    try:
        data = s
        # Tant que c'est une chaîne, tenter de la nettoyer et de la parser
        while isinstance(data, str):
            data = data.strip().lstrip('"').rstrip('"')   # suppression de guillemets superflus
            data = data.replace('\\"', '"')               # déséchappement des guillemets
            data = json.loads(data)                       # parse JSON
        return data if isinstance(data, dict) else {}    # s'assurer d'un dict en sortie
    except Exception:
        return {}                                        # en cas d'erreur, renvoyer dict vide

def count_objects(boxes_json):
    """Compte les annotations dans boxes_json.
       Règles :
         - rect/circle/image => compte pour 1
         - path (crayon) => chaque sous-chemin compte comme 1 (plusieurs coups)
    """
    data = safe_load(boxes_json)
    objs = data.get("objects", [])
    count = 0
    for o in objs:
        # Vérifier que l'objet est visible et a un type valide
        if not o.get("visible", True):
            continue
        obj_type = o.get("type")
        if obj_type in {"rect", "circle", "image"}:
            count += 1
        elif obj_type == "path" and "path" in o:
            count += len(o["path"])  # Compter chaque sous-chemin
    return count

# --- Graphique : nombre d’annotations par image ---
def fig_per_image():
    """Construit un bar chart (plotly) du nombre d'annotations par image."""
    df = load_annotations()
    if df.empty:
        return px.bar(title="Aucune annotation disponible")

    # ajout d'une colonne avec le nombre d'objets par ligne
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
    """Bar chart du nombre d'annotations total par annotateur."""
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
    """Retourne un composant HTML listant les images présentes dans IMAGES_DIR sans annotations."""
    # lister les images du dossier IMAGES_DIR (extensions courantes)
    all_imgs = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    df = load_annotations()

    if df.empty:
        # si aucune annotation enregistrée, toutes les images sont considérées manquantes
        missing = all_imgs
    else:
        # déterminer les images qui ont au moins une annotation
        annotated = df.loc[df["boxes_json"].apply(count_objects) > 0, "image"].unique().tolist()
        # images présentes physiquement mais non listées comme annotées
        missing = [img for img in all_imgs if img not in annotated]

    if not missing:
        # message de succès si aucune image manquante
        return html.Div("🎉 Toutes les images ont été annotées !", className="text-success")

    # construire un tableau HTML simple listant les fichiers manquants
    rows = [html.Tr([html.Td(img)]) for img in missing]
    return html.Table(
        [html.Thead(html.Tr([html.Th("Images non annotées")]))] +
        [html.Tbody(rows)],
        style={"width": "100%", "border": "1px solid #ccc", "textAlign": "center"}
    )

# --- Exports ---
def generate_coco():
    """Génère une chaîne JSON au format COCO (minimal) à partir des annotations.
       Ne gère ici que les rectangles (type 'rect') et crée une catégorie unique id=1.
    """
    df = load_annotations()
    images, annotations = [], []
    ann_id = 1

    for idx, row in df.iterrows():
        img_name = row["image"]
        path = os.path.join(IMAGES_DIR, img_name)
        if not os.path.exists(path):
            continue  # ignorer si l'image n'existe plus

        # récupérer largeur/hauteur à partir du fichier image
        w, h = Image.open(path).size
        img_id = idx + 1  # id d'image basé sur l'index du dataframe (simple et stable par session)
        images.append({"id": img_id, "file_name": img_name, "width": w, "height": h})

        data = safe_load(row["boxes_json"])
        for obj in data.get("objects", []):
            # ne prendre en compte que les rectangles ; extraire left/top/width/height
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
    return json.dumps(coco, indent=2)  # renvoyer la string JSON indentée

def generate_yolo_zip():
    """Génère un zip en mémoire contenant des fichiers .txt au format YOLO v5 (classe 0).
       Chaque image qui a des rects produit un fichier texte avec une ligne par bbox:
       <class> <x_center> <y_center> <w_rel> <h_rel>
    """
    df = load_annotations()
    mem_zip = io.BytesIO()

    with zipfile.ZipFile(mem_zip, "w") as zf:
        for idx, row in df.iterrows():
            img_name = row["image"]
            path = os.path.join(IMAGES_DIR, img_name)
            if not os.path.exists(path):
                continue

            # récupérer taille de l'image pour normaliser les coordonnées
            w, h = Image.open(path).size
            data = safe_load(row["boxes_json"])
            lines = []
            for obj in data.get("objects", []):
                if obj.get("type") == "rect":
                    x, y, bw, bh = obj.get("left", 0), obj.get("top", 0), obj.get("width", 0), obj.get("height", 0)
                    # conversion vers format YOLO (centres et tailles relatives)
                    xc, yc = (x + bw / 2) / w, (y + bh / 2) / h
                    nw, nh = bw / w, bh / h
                    lines.append(f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")
            if lines:
                txt_name = os.path.splitext(img_name)[0] + ".txt"
                zf.writestr(txt_name, "\n".join(lines))  # écrire le fichier texte dans le zip

    mem_zip.seek(0)
    return mem_zip  # BytesIO contenant le zip prêt à être téléchargé

# --- Layout --- : définition des composants Dash affichés dans la page
layout = dbc.Container([
    dcc.Interval(id="refresh-stats", interval=3000, n_intervals=0),  # rafraîchissement auto toutes les 3s

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
            dcc.Download(id="download-export")  # composant Dash pour gérer le téléchargement
        ], className="card p-3"), md=12),
    ]),
], fluid=True)

# --- Callback --- : enregistrement des callbacks utilisés par la page
def register_callbacks(app):
    @app.callback(
        Output("graph-per-image", "figure"),
        Output("graph-per-user", "figure"),
        Output("table-unannotated", "children"),
        Input("refresh-stats", "n_intervals")
    )
    def update_stats(_):
        # à chaque tick, reconstruire figures et tableau (fonction pure côté serveur)
        return fig_per_image(), fig_per_user(), table_unannotated()

    @app.callback(
        Output("download-export", "data"),
        Input("btn-export-coco", "n_clicks"),
        Input("btn-export-yolo", "n_clicks"),
        prevent_initial_call=True
    )
    def export_files(n_coco, n_yolo):
        """Gère les clics sur les boutons d'export et prépare le contenu à télécharger."""
        ctx = dash.callback_context
        if not ctx.triggered:
            return None
        btn = ctx.triggered[0]["prop_id"].split(".")[0]  # id du bouton qui a déclenché

        if btn == "btn-export-coco":
            coco_str = generate_coco()
            # send_string attend un callable retournant la string à envoyer
            return send_string(lambda: coco_str, "annotations_coco.json")

        elif btn == "btn-export-yolo":
            zip_bytes = generate_yolo_zip()
            # send_bytes attend un callable écrivant dans un buffer b ; on y écrit le zip en mémoire
            return send_bytes(lambda b: b.write(zip_bytes.getvalue()), "annotations_yolo.zip")