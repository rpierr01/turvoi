import os
import base64
import json
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from dash_canvas import DashCanvas
from services.json_annotations import (
    list_images, 
    IMAGES_DIR, 
    add_annotation, 
    get_annotator_color,
    get_annotations_for_image
)

# Page d'annotation
dash.register_page(__name__, path="/annotate", name="Annoter")

# Layout : canvas + panneau de contrôle
layout = dbc.Container([
    dcc.Store(id="image-list"),
    dcc.Store(id="current-index", data=0),
    dcc.Store(id="annotator-store", storage_type="local"),
    dcc.Store(id="global-store"),  # Ajout du composant manquant

    dbc.Row([
        dbc.Col(dbc.Card([
            html.Div(id="image-title", className="muted"),
            DashCanvas(
                id="canvas",
                width=800,
                height=600,
                tool="rectangle",
                hide_buttons=["zoom", "pan", "line", "pencil", "select"],
                lineWidth=3,
                lineColor="#FF0000",
                goButtonTitle="Valider rectangles",
                image_content="",
                json_data='{"objects": []}',
                scale=1.0,
                zoom=1.0,
            ),
            html.Hr(),
            html.Div([
                html.H6("Contrôles:"),
                dbc.ButtonGroup([
                    dbc.Button("🗑️ Effacer tout", id="clear-canvas", color="warning", size="sm"),
                    dbc.Button("👁️ Voir rectangles", id="show-rectangles", color="info", size="sm"),
                ], className="me-2"),
                html.Br(), 
                html.Br(),
                html.Span("Mode: Rectangle activé • Dessinez directement sur l'image", className="text-success small")
            ], className="mb-2"),
            html.Div(id="canvas-debug", className="small text-muted")
        ], className="card"), md=8),

        dbc.Col(dbc.Card([
            html.H5("Annotateur"),
            dcc.Input(
                id="annotator-name",
                placeholder="Votre nom (ex: leslie)",
                type="text",
                debounce=True,
                className="mb-2",
                autoComplete="off",
                spellCheck=False
            ),
            html.Div(id="whoami", className="muted"),
            html.Hr(),
            html.Div(id="image-info", className="muted"),
            html.Div([
                dbc.Button("◀ Précédent", id="prev-image", color="secondary", className="me-2"),
                dbc.Button("Suivant ▶", id="next-image", color="secondary"),
            ], className="mt-2"),
            dbc.Button("💾 Sauvegarder", id="save-annotation", color="success", className="mt-3"),
            html.Div(id="annotate-save-status", className="mt-2")  # Renommé ici
        ], className="card"), md=4)
    ])
], fluid=True)

def register_callbacks(app):
    @app.callback(Output("annotator-store", "data"), Input("annotator-name", "value"))
    def _persist_annotator(name):
        name = (name or "").strip()
        return {"name": name} if name else {}

    @app.callback(Output("whoami", "children"), Input("annotator-store", "data"))
    def _show_whoami(data):
        if data and data.get('name'):
            color = get_annotator_color(data['name'])
            return html.Span([
                f"Connecté en tant que : {data['name']} ",
                html.Span("●", style={"color": color, "font-size": "20px"})
            ])
        return "Veuillez entrer votre nom"

    @app.callback(Output("image-list", "data"), Input("annotator-store", "data"))
    def _load_images(_):
        return list_images()

    # Callback pour pré-sélectionner une image depuis le Store global
    @app.callback(
        Output("current-index", "data", allow_duplicate=True),
        Output("global-store", "data", allow_duplicate=True),
        Input("global-store", "data"),
        Input("image-list", "data"),
        prevent_initial_call=True
    )
    def _preselect_image_from_store(store_data, images):
        print(f"DEBUG: Store data received: {store_data}")
        print(f"DEBUG: Images available: {images}")
        
        if not store_data or not images:
            return 0, store_data
        
        preselected_image = store_data.get("preselected_image")
        if preselected_image and preselected_image in images:
            index = images.index(preselected_image)
            print(f"DEBUG: Pre-selecting image {preselected_image} at index {index}")
            # Nettoyer le store après usage
            cleaned_store = {k: v for k, v in store_data.items() if k != "preselected_image"}
            return index, cleaned_store
        
        return 0, store_data

    @app.callback(
        Output("canvas", "image_content"),
        Output("canvas", "json_data"),
        Output("canvas", "tool"),  # Force le retour en mode rectangle
        Output("image-title", "children"),
        Output("image-info", "children"),
        Input("image-list", "data"),
        Input("current-index", "data"),
        prevent_initial_call=True
    )
    def _set_image(imgs, idx):
        if not imgs:
            return None, '{"objects": []}', "rectangle", "Aucune image trouvée dans data/cars_detection/", ""
        
        idx = max(0, min(idx or 0, len(imgs) - 1))
        img_name = imgs[idx]
        path = os.path.join(IMAGES_DIR, img_name)
        
        # Charger l'image
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        img_data_url = f"data:image/jpeg;base64,{b64}"
        info = f"Image {idx+1}/{len(imgs)} — {img_name}"
        
        # Charger les annotations existantes pour cette image
        existing_annotations = get_annotations_for_image(img_name)
        
        # Convertir les rectangles en format DashCanvas
        canvas_objects = []
        for ann in existing_annotations:
            for rect in ann["rectangles"]:
                # Format DashCanvas pour les rectangles
                canvas_objects.append({
                    "type": "rect",
                    "left": rect["x"],
                    "top": rect["y"], 
                    "width": rect["width"],
                    "height": rect["height"],
                    "fill": rect["color"] + "80",  # Semi-transparent
                    "stroke": rect["color"],
                    "strokeWidth": 2,
                    "selectable": True
                })
        
        # Créer le JSON pour DashCanvas
        canvas_json = {
            "version": "4.6.0",
            "objects": canvas_objects
        }
        
        print(f"DEBUG: Loaded {len(canvas_objects)} existing rectangles for {img_name}")
        
        return img_data_url, json.dumps(canvas_json), "rectangle", img_name, info

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

    @app.callback(Output("annotate-save-status", "children"),  # Renommé ici
                  Input("save-annotation", "n_clicks"),
                  State("canvas", "json_data"),
                  State("image-list", "data"),
                  State("current-index", "data"),
                  State("annotator-store", "data"),
                  prevent_initial_call=True)
    def _save(_, json_data, imgs, idx, who):
        if not imgs:
            return html.Span("Pas d'image à enregistrer", className="text-danger")
        annotator = (who or {}).get("name")
        if not annotator:
            return html.Span("Veuillez saisir votre nom d'annotateur", className="text-danger")
        img = imgs[idx or 0]
        
        if isinstance(json_data, str):
            try:
                json_data = json.loads(json_data)
            except:
                return html.Span("Erreur lors de la lecture du canvas", className="text-danger")
        
        rectangles = []
        if json_data and isinstance(json_data, dict) and "objects" in json_data:
            for obj in json_data["objects"]:
                obj_type = str(obj.get("type", "")).lower()
                if "rect" in obj_type or obj.get("tool") == "rectangle" or obj.get("shape") == "rectangle":
                    rect = {
                        "x": obj.get("left", 0),
                        "y": obj.get("top", 0),
                        "width": obj.get("width", 0),
                        "height": obj.get("height", 0)
                    }
                    rectangles.append(rect)
        
        if rectangles:
            annotation_id = add_annotation(img, annotator, rectangles)
            color = get_annotator_color(annotator)
            return html.Span(
                f"✅ Annotation #{annotation_id} sauvegardée: {len(rectangles)} rectangles (couleur: {color})", 
                className="text-success"
            )
        else:
            return html.Span("⚠️ Aucun rectangle à sauvegarder", className="text-warning")
    
    @app.callback(
        Output("canvas", "json_data", allow_duplicate=True),
        Input("clear-canvas", "n_clicks"),
        State("canvas", "image_content"),
        prevent_initial_call=True,
        allow_duplicate_outputs=True
    )
    def _clear_canvas(_, current_image):
        if current_image:
            # Réinitialiser avec l'image actuelle mais sans objets
            return '{"objects": []}'
        return '{"objects": []}'
    
    @app.callback(
        Output("canvas", "json_data", allow_duplicate=True),
        Input("show-rectangles", "n_clicks"),
        State("canvas", "json_data"),
        prevent_initial_call=True,
        allow_duplicate_outputs=True
    )
    def _show_rectangles(_, json_data):
        if isinstance(json_data, str):
            return json_data
        return json.dumps(json_data) if json_data else '{"objects": []}'
    
    @app.callback(
        Output("canvas-debug", "children"),
        Input("canvas", "json_data"),
        prevent_initial_call=True
    )
    def _debug_canvas(json_data):
        if not json_data:
            return "Canvas vide"
        
        if isinstance(json_data, str):
            try:
                json_data = json.loads(json_data)
            except:
                return f"Erreur parsing JSON: {json_data[:50]}..."
        
        objects = json_data.get("objects", [])
        if not objects:
            return "Aucun objet sur le canvas • Dessinez un rectangle sur l'image"
        
        debug_info = []
        rectangles = []
        
        for i, obj in enumerate(objects, 1):
            obj_type = obj.get("type", "unknown")
            obj_tool = obj.get("tool", "unknown")
            debug_info.append(f"Objet {i}: type='{obj_type}', tool='{obj_tool}'")
            
            if "rect" in str(obj_type).lower() or obj.get("tool") == "rectangle" or obj.get("shape") == "rectangle":
                rectangles.append(obj)
        
        result = [
            html.Strong(f"{len(objects)} objet(s) total, {len(rectangles)} rectangle(s)"),
        ]
        
        if rectangles:
            result.append(html.Div("✅ Rectangles détectés:", className="mt-2 text-success"))
            rect_info = []
            for i, rect in enumerate(rectangles, 1):
                coords = []
                for coord in ["left", "top", "width", "height"]:
                    if coord in rect:
                        coords.append(f"{coord}={rect[coord]:.0f}")
                rect_info.append(f"Rectangle {i}: {', '.join(coords)}")
            result.append(html.Ul([html.Li(info) for info in rect_info]))
        else:
            result.append(html.Div("ℹ️ Objets détectés mais aucun rectangle reconnu", className="text-info"))
            result.append(html.Details([
                html.Summary("Voir détails objets"),
                html.Ul([html.Li(html.Code(info)) for info in debug_info])
            ]))
        
        return html.Div(result)
    
    @app.callback(
        Output("canvas", "lineColor"),
        Input("annotator-store", "data"),
        prevent_initial_call=True
    )
    def _update_canvas_color(annotator_data):
        if annotator_data and annotator_data.get("name"):
            return get_annotator_color(annotator_data["name"])
        return "#FF0000"