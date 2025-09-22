import os, base64
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from dash_canvas import DashCanvas
from services.annotation_io import list_images, IMAGES_DIR, save_annotation

# Page d'annotation
dash.register_page(__name__, path="/annotate", name="Annoter")

# Layout : canvas + panneau de contrôle
layout = dbc.Container([
    dcc.Store(id="image-list"),
    dcc.Store(id="current-index", data=0),
    dcc.Store(id="annotator-store", storage_type="local"),

    dbc.Row([
        dbc.Col(dbc.Card([
            html.Div(id="image-title", className="muted"),
            DashCanvas(
                id="canvas",
                width=960,
                tool="rectangle",
                hide_buttons=["zoom", "pan"],
                lineWidth=3,
                lineColor="#00b894",
                json_data={},
            ),
            html.Img(id="bg-image", style={"display": "none"})
        ], className="card"), md=8),

        dbc.Col(dbc.Card([
            html.H5("Annotateur"),
            dcc.Input(
                id="annotator-name",
                placeholder="Votre nom",
                type="text",
                debounce=True,
                className="mb-2"
            ),
            html.Div(id="whoami", className="muted"),
            html.Hr(),
            html.Div(id="image-info", className="muted"),
            html.Div([
                dbc.Button("◀ Précédent", id="prev-image", color="secondary", className="me-2"),
                dbc.Button("Suivant ▶", id="next-image", color="secondary"),
            ], className="mt-2"),
            dbc.Button("💾 Sauvegarder", id="save-annotation", color="success", className="mt-3"),
            html.Div(id="save-status", className="mt-2")
        ], className="card"), md=4)
    ])
], fluid=True)

def register_callbacks(app):
    # Persiste le nom de l'annotateur (localStorage)
    @app.callback(Output("annotator-store", "data"), Input("annotator-name", "value"))
    def _persist_annotator(name):
        name = (name or "").strip()
        return {"name": name} if name else {}

    @app.callback(Output("whoami", "children"), Input("annotator-store", "data"))
    def _show_whoami(data):
        return f"Connecté en tant que : {data.get('name','(inconnu)')}" if data else ""

    # Charge la liste d'images depuis data/cars_detection/
    @app.callback(Output("image-list", "data"), Input("annotator-store", "data"))
    def _load_images(_):
        return list_images()

    # Met l'image de fond du canvas (base64)
    @app.callback(
        Output("bg-image", "src"),
        Output("image-title", "children"),
        Output("image-info", "children"),
        Input("image-list", "data"),
        Input("current-index", "data"),
        prevent_initial_call=True
    )
    def _set_image(imgs, idx):
        if not imgs:
            return None, "Aucune image trouvée dans data/cars_detection/", ""
        idx = max(0, min(idx or 0, len(imgs) - 1))
        img_name = imgs[idx]
        path = os.path.join(IMAGES_DIR, img_name)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        info = f"Image {idx+1}/{len(imgs)} — {img_name}"
        return f"data:image/jpeg;base64,{b64}", img_name, info

    # Injecte l'image dans le DashCanvas
    @app.callback(Output("canvas", "image_content"), Input("bg-image", "src"))
    def _bg_to_canvas(src):
        return src

    # Navigation précédente/suivante
    @app.callback(Output("current-index", "data"),
                  Input("next-image", "n_clicks"), Input("prev-image", "n_clicks"),
                  State("current-index", "data"), State("image-list", "data"))
    def _nav(next_n, prev_n, idx, imgs):
        trigger = dash.callback_context.triggered[0]["prop_id"].split(".")[0] if dash.callback_context.triggered else None
        idx = idx or 0
        if not imgs:
            return 0
        if trigger == "next-image":
            idx = min(idx + 1, len(imgs) - 1)
        elif trigger == "prev-image":
            idx = max(idx - 1, 0)
        return idx

    # Sauvegarde l'annotation (JSON du canvas)
    @app.callback(Output("save-status", "children"),
                  Input("save-annotation", "n_clicks"),
                  State("canvas", "json_data"),
                  State("image-list", "data"),
                  State("current-index", "data"),
                  State("annotator-store", "data"),
                  prevent_initial_call=True)
    def _save(_, json_data, imgs, idx, who):
        if not imgs:
            return html.Span("Pas d'image à enregistrer", className="danger")
        annotator = (who or {}).get("name")
        if not annotator:
            return html.Span("Veuillez saisir votre nom d’annotateur", className="danger")
        img = imgs[idx or 0]
        save_annotation(img, annotator, json_data or {})
        return html.Span("✅ Annotations sauvegardées")
