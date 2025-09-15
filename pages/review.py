import json
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
from services.annotation_io import load_annotations

# Page de relecture
dash.register_page(__name__, path="/review", name="Relecture")

layout = dbc.Container([
    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("Filtrer"),
            dcc.Dropdown(id="rev-image", placeholder="Image"),
            dcc.Dropdown(id="rev-annotator", placeholder="Annotateur (optionnel)")
        ], className="card"), md=4),
        dbc.Col(dbc.Card([
            html.H5("Historique des annotations"),
            dcc.Graph(id="rev-table", config={"displayModeBar": False})
        ], className="card"), md=8)
    ])
], fluid=True)

def register_callbacks(app):
    # Alimente les options d'image et annotateur
    @app.callback(Output("rev-image", "options"), Output("rev-annotator", "options"),
                  Input("url", "pathname"), prevent_initial_call=False)
    def _fill_options(_=None):
        df = load_annotations()
        return sorted(df["image"].unique().tolist()), sorted(df["annotator"].dropna().unique().tolist())

    # Graphe "nombre de boîtes par enregistrement au fil du temps"
    @app.callback(Output("rev-table", "figure"), Input("rev-image", "value"), Input("rev-annotator", "value"))
    def _table(img, ann):
        df = load_annotations(image=img, annotator=ann)
        if df.empty:
            return px.scatter(title="Aucune annotation")
        out = df.assign(n_boxes=df["boxes_json"].apply(lambda s: len(json.loads(s or "{}").get("objects", []))))
        fig = px.scatter(out, x="timestamp", y="n_boxes", color="annotator", hover_data=["image"])
        fig.update_layout(title="Nombre de boîtes par enregistrement", xaxis_title="timestamp", yaxis_title="#boxes")
        return fig
