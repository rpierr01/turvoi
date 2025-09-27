import json
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
from dash import dash_table
from services.annotation_io import load_annotations
import csv
import os

# Tentative d'import de la fonction de sauvegarde (à implémenter si absente)
try:
    from services.annotation_io import save_annotations
except ImportError:
    save_annotations = None  # Fallback: aucune persistance

# Page de relecture
dash.register_page(__name__, path="/review", name="Relecture")

layout = dbc.Container([
    dbc.Row([
        dbc.Col(dbc.Card([
            html.H5("Filtrer"),
            dcc.Dropdown(id="rev-image", placeholder="Image"),
            dcc.Dropdown(id="rev-annotator", placeholder="Annotateur (optionnel)"),
            html.Hr(),
            dbc.Button("Supprimer sélection", id="rev-delete", color="danger", size="sm", disabled=True),
            # dcc.Store(id="rev-store-delete")  # supprimé
        ], className="card"), md=4),
        dbc.Col(dbc.Card([
            html.H5("Tableau des données"),
            dash_table.DataTable(
                id="rev-datatable",
                page_size=10,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left'},
                row_selectable="single",
                hidden_columns=["_row_id"],
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

    # Activation / désactivation du bouton de suppression
    @app.callback(
        Output("rev-delete", "disabled"),
        Input("rev-datatable", "selected_rows"),
        Input("rev-datatable", "data"),
        prevent_initial_call=False
    )
    def _toggle_delete(selected_rows, data):
        if not data or not selected_rows:
            return True
        return False

    # Nouveau callback unique: remplissage + suppression
    @app.callback(
        Output("rev-datatable", "data"),
        Output("rev-datatable", "columns"),
        Input("rev-image", "value"),
        Input("rev-annotator", "value"),
        Input("rev-delete", "n_clicks"),
        State("rev-datatable", "selected_rows"),
        State("rev-datatable", "data"),
        prevent_initial_call=False
    )
    def _fill_table(img, ann, delete_clicks, selected_rows, current_rows):
        df = load_annotations()
        ctx = dash.callback_context
        triggered = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        # Suppression uniquement si bouton cliqué ET une ligne sélectionnée
        if triggered == "rev-delete" and delete_clicks and selected_rows and current_rows:
            row_pos = selected_rows[0]
            try:
                target_row_id = current_rows[row_pos]["_row_id"]
            except Exception:
                target_row_id = None
            if target_row_id is not None:
                df_work = df.reset_index().rename(columns={"index": "_row_id"})
                before = len(df_work)
                df_work = df_work[df_work["_row_id"] != target_row_id]
                if len(df_work) != before:
                    if save_annotations:
                        save_annotations(df_work.drop(columns=["_row_id"]))
                        df = df_work.drop(columns=["_row_id"])
                    else:
                        df = df_work.drop(columns=["_row_id"])

        # Filtrage
        if img:
            df = df[df["image"] == img]
        if ann:
            df = df[df["annotator"] == ann]

        if df.empty:
            return [], []

        df_show = df.reset_index().rename(columns={"index": "_row_id"})
        columns = [{"name": c, "id": c} for c in df_show.columns]
        return df_show.to_dict("records"), columns

def delete_csv_row(image_name, csv_filepath):
    """
    Supprime une ligne du fichier CSV correspondant à l'image spécifiée.
    
    :param image_name: Nom de l'image à supprimer.
    :param csv_filepath: Chemin du fichier CSV.
    """
    rows = []
    with open(csv_filepath, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = [row for row in reader if row['image'] != image_name]

    with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['image', 'annotator', 'timestamp', 'boxes_json'])
        writer.writeheader()
        writer.writerows(rows)

    # Exemple d'utilisation dans une vue ou un gestionnaire d'événements
    # delete_csv_row('car425.jpg', '/Users/remipierron/Desktop/InterMac/work/dash8/turvoi/data/annotations.csv')
        reader = csv.DictReader(csvfile)
        rows = [row for row in reader if row['image'] != image_name]

    with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['image', 'annotator', 'timestamp', 'boxes_json'])
        writer.writeheader()
        writer.writerows(rows)

    # Exemple d'utilisation dans une vue ou un gestionnaire d'événements
    # delete_csv_row('car425.jpg', '/Users/remipierron/Desktop/InterMac/work/dash8/turvoi/data/annotations.csv')
