import json
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
from dash import dash_table
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
            html.H5("Tableau des données"),
            dash_table.DataTable(
                id="rev-datatable",
                page_size=10,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left'},
            )
        ], className="card"), md=8)
    ])
], fluid=True)

def register_callbacks(app):
    # Options dynamiques pour image et annotateur (filtrage identique au tableau)
    @app.callback(
        Output("rev-image", "options"),
        Output("rev-annotator", "options"),
        Input("rev-image", "value"),
        Input("rev-annotator", "value"),
        prevent_initial_call=False
    )
    def _fill_options(selected_img, selected_ann):
        df = load_annotations()
        # Filtre selon les valeurs sélectionnées
        if selected_img:
            df = df[df["image"] == selected_img]
        if selected_ann:
            df = df[df["annotator"] == selected_ann]
        img_opts = [{"label": i, "value": i} for i in sorted(df["image"].unique())]
        ann_opts = [{"label": a, "value": a} for a in sorted(df["annotator"].dropna().unique())]
        return img_opts, ann_opts

    # Callback pour alimenter le tableau filtré
    @app.callback(
        Output("rev-datatable", "data"),
        Output("rev-datatable", "columns"),
        Input("rev-image", "value"),
        Input("rev-annotator", "value"),
    )
    def _fill_table(img, ann):
        df = load_annotations()
        if img:
            df = df[df["image"] == img]
        if ann:
            df = df[df["annotator"] == ann]
        if df.empty:
            return [], []
        columns = [{"name": col, "id": col} for col in df.columns]
        return df.to_dict("records"), columns
