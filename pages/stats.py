import io
import json
import pandas as pd
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px

# ---- CONFIG ----
ANNOTATIONS_FILE = "./data/annotations.csv"
IMAGES_DIR = "./data/cars_detection"

# ---- PAGE DASH ----
dash.register_page(__name__, path="/stats", name="Stats & Export")

layout = dbc.Container([
    dcc.Download(id="dl-coco"),
    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("Progression du dataset"),
            dcc.Graph(id="progress-fig")
        ], className="card"), md=6),
        dbc.Col(dbc.Card([
            html.H5("Annotations par annotateur"),
            dcc.Graph(id="by-ann-fig")
        ], className="card"), md=6)
    ]),
    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("Accord inter-annotateurs (IoU moyen)"),
            dcc.Slider(id="iou-thr", min=0.3, max=0.9, step=0.05, value=0.5,
                       marks={i/10: str(i/10) for i in range(3,10)}),
            dcc.Graph(id="iaa-fig"),
            html.Div(id="conflict-list", className="mt-2")
        ], className="card"), md=8),
        dbc.Col(dbc.Card([
            html.H5("Export"),
            dbc.Button("⬇ Export COCO", id="export-coco", color="primary"),
            html.Div(id="export-msg", className="mt-2")
        ], className="card"), md=4)
    ])
], fluid=True)

def register_callbacks(app):
    from dash import ctx
    from services.export_coco import to_coco

    @app.callback(
        Output("dl-coco", "data"),
        Output("export-msg", "children"),
        Input("export-coco", "n_clicks"),
        prevent_initial_call=True
    )
    def export_coco(n_clicks):
        if not n_clicks:
            return dash.no_update, ""
        try:
            df = pd.read_csv(ANNOTATIONS_FILE)
            coco = to_coco(df, IMAGES_DIR)
            buffer = io.StringIO()
            json.dump(coco, buffer, ensure_ascii=False, indent=2)
            buffer.seek(0)
            return dcc.send_string(buffer.getvalue(), "annotations_coco.json"), "Export réussi."
        except Exception as e:
            return None, f"Erreur export: {e}"

