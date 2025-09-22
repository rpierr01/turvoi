import os, json
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from PIL import Image

from services.annotation_io import load_annotations, IMAGES_DIR

# Page stats
dash.register_page(__name__, path="/stats", name="Stats")

# --- Helper robuste ---
def safe_load(s):
    """Charge une colonne boxes_json qui peut contenir du JSON mal échappé."""
    try:
        data = json.loads(s or "{}")
        if isinstance(data, str):  # si c'est encore une string JSON → recharger
            data = json.loads(data)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

# --- Graphique : nombre d’annotations par image ---
def fig_per_image():
    df = load_annotations()
    if df.empty:
        return px.bar(title="Aucune annotation disponible")

    # Compter le nombre de boîtes "rect" dans chaque annotation
    df = df.assign(
        n_boxes=df["boxes_json"].apply(
            lambda s: sum(1 for o in safe_load(s).get("objects", []) if o.get("type") == "rect")
        )
    )

    counts = df.groupby("image")["n_boxes"].sum().reset_index()
    fig = px.bar(counts, x="image", y="n_boxes", text="n_boxes")
    fig.update_layout(xaxis_title="Image", yaxis_title="Nombre total de boîtes", xaxis_tickangle=-45)
    return fig

# --- Graphique : nombre d’annotations par utilisateur ---
def fig_per_user():
    df = load_annotations()
    if df.empty:
        return px.bar(title="Aucune annotation disponible")

    df = df.assign(
        n_boxes=df["boxes_json"].apply(
            lambda s: sum(1 for o in safe_load(s).get("objects", []) if o.get("type") == "rect")
        )
    )

    counts = df.groupby("annotator")["n_boxes"].sum().reset_index()
    fig = px.bar(counts, x="annotator", y="n_boxes", text="n_boxes", color="annotator")
    fig.update_layout(xaxis_title="Annotateur", yaxis_title="Nombre total de boîtes")
    return fig

# --- Graphique : taille moyenne des images ---
def fig_avg_size():
    files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not files:
        return px.bar(title="Aucune image disponible")

    sizes = []
    for f in files:
        try:
            w, h = Image.open(os.path.join(IMAGES_DIR, f)).size
            sizes.append({"image": f, "width": w, "height": h, "area": w * h})
        except Exception:
            continue

    df_sizes = pd.DataFrame(sizes)
    avg_w, avg_h, avg_area = df_sizes["width"].mean(), df_sizes["height"].mean(), df_sizes["area"].mean()

    df_avg = pd.DataFrame([
        {"metric": "Largeur moyenne (px)", "value": avg_w},
        {"metric": "Hauteur moyenne (px)", "value": avg_h},
        {"metric": "Surface moyenne (px²)", "value": avg_area},
    ])
    fig = px.bar(df_avg, x="metric", y="value", text="value", color="metric")
    fig.update_layout(xaxis_title="Métrique", yaxis_title="Valeur")
    return fig

# --- Layout ---
layout = dbc.Container([
    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("📊 Nombre d’annotations par image"),
            dcc.Graph(figure=fig_per_image())
        ], className="card"), md=12),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("👤 Nombre d’annotations par utilisateur"),
            dcc.Graph(figure=fig_per_user())
        ], className="card"), md=6),

        dbc.Col(dbc.Card([
            html.H5("📐 Taille moyenne des images"),
            dcc.Graph(figure=fig_avg_size())
        ], className="card"), md=6),
    ])
], fluid=True)
