import json
import base64
import dash
from dash import html, dcc, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
from services.json_annotations import (
    get_all_annotations, 
    list_images,
    get_annotator_color,
    get_annotations_for_image,
    add_annotation,
    update_annotation,
    IMAGES_DIR
)
from dash_canvas import DashCanvas
from PIL import Image, ImageDraw
import io
import os

# Page de révision avec fonctionnalités complètes
dash.register_page(__name__, path="/review", name="Révision")

def create_image_with_rectangles(image_path, rectangles, annotator_color):
    """Crée une image composite avec les rectangles d'UNE annotation spécifique"""
    try:
        # Ouvrir l'image originale
        img = Image.open(image_path)
        img = img.convert("RGB")
        
        # Créer un objet de dessin
        draw = ImageDraw.Draw(img)
        
        # Dessiner seulement les rectangles de cette annotation
        for rect in rectangles:
            x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
            
            # Convertir la couleur hex en RGB si nécessaire
            if isinstance(annotator_color, str) and annotator_color.startswith('#'):
                rgb_color = tuple(int(annotator_color[i:i+2], 16) for i in (1, 3, 5))
            else:
                rgb_color = (255, 0, 0)  # Rouge par défaut
            
            # Dessiner le rectangle (contour)
            draw.rectangle([x, y, x + w, y + h], 
                         outline=rgb_color, 
                         width=3)
            
            # Dessiner un rectangle semi-transparent (remplissage)
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            fill_color = rgb_color + (50,)  # RGBA avec alpha=50
            overlay_draw.rectangle([x, y, x + w, y + h], fill=fill_color)
            
            # Compositer avec l'image principale
            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        
        # Convertir en base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        img_data = buffer.getvalue()
        encoded = base64.b64encode(img_data).decode()
        return f"data:image/jpeg;base64,{encoded}"
        
    except Exception as e:
        print(f"Erreur création image avec rectangles: {e}")
        return encode_image(image_path)  # Fallback vers image originale

def encode_image(image_path):
    """Encode une image en base64 pour l'affichage"""
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        print(f"Erreur encodage image {image_path}: {e}")
        return ""

# Layout de la page
layout = dbc.Container([
    html.H2("🔍 Révision des Annotations", className="mb-4"),
    
    # Section des filtres
    dbc.Row([
        dbc.Col([
            html.Label("Filtre par Annoteur:", className="form-label"),
            dcc.Dropdown(
                id="filter-annotator",
                placeholder="Tous les annoteurs",
                clearable=True
            )
        ], md=6),
        dbc.Col([
            html.Label("Filtre par Image:", className="form-label"),
            dcc.Dropdown(
                id="filter-image", 
                placeholder="Toutes les images",
                clearable=True
            )
        ], md=6)
    ], className="mb-4"),
    
    # Layout côte à côte : Tableau + Modification
    dbc.Row([
        # Colonne gauche - Tableau
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📋 Tableau des Annotations"),
                dbc.CardBody([
                    dash_table.DataTable(
                        id="annotations-table",
                        columns=[
                            {"name": "ID", "id": "id"},
                            {"name": "Image", "id": "image_name"},
                            {"name": "Annoteur", "id": "annotator"},
                            {"name": "Rectangles", "id": "rect_count"},
                            {"name": "Timestamp", "id": "timestamp"}
                        ],
                        style_table={"overflowX": "auto"},
                        style_cell={"textAlign": "left", "padding": "8px", "fontSize": "13px"},
                        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                        page_size=12,
                        row_selectable="single",
                        selected_rows=[],
                        data=[]  # Sera rempli par le callback
                    )
                ])
            ]),
            
            # Section Historique des modifications (sous le tableau)
            html.Div([
                dbc.Card([
                    dbc.CardHeader("📜 Historique des Modifications"),
                    dbc.CardBody([
                        html.Div(id="modification-history", 
                                children="Sélectionnez une annotation pour voir son historique",
                                className="text-muted text-center p-3")
                    ])
                ], className="mt-3")
            ], id="history-section", style={"display": "none"})
        ], md=6),
        
        # Colonne droite - Modification (initialement masquée)
        dbc.Col([
            html.Div([
                dbc.Card([
                    dbc.CardHeader("🔧 Ajouter des Rectangles"),
                    dbc.CardBody([
                        html.Div(id="modification-info", className="mb-3"),
                        
                        # Canvas pour modification - Outils simplifiés
                        DashCanvas(
                            id="modification-canvas",
                            width=500,
                            height=350,
                            tool="rectangle", 
                            hide_buttons=["zoom", "pan", "line", "pencil", "select", "download", "pen"],
                            lineWidth=3,
                            lineColor="#e17055",  # Orange pour nouveaux rectangles
                            json_data='{"version": "4.6.0", "objects": []}'
                        ),
                        
                        html.Hr(),
                        
                        html.Label("Votre nom:", className="form-label"),
                        dcc.Input(
                            id="modifier-name",
                            type="text",
                            placeholder="Votre nom",
                            className="form-control mb-3"
                        ),
                        
                        dbc.Button(
                            "✅ Valider les Annotations",
                            id="save-additions",
                            color="success",
                            className="w-100 mb-2"
                        ),
                        
                        html.Div(id="review-save-status", className="mt-3")
                    ])
                ])
            ], id="modification-section", style={"display": "none"})
        ], md=6)
    ], className="g-3"),  # Espacement entre colonnes
    
    # Store pour déclencher les actualisations du tableau
    dcc.Store(id="table-refresh-trigger")
], fluid=True)

def get_filtered_table_data(selected_annotator, selected_image):
    """Génère les données filtrées du tableau"""
    annotations = get_all_annotations()
    
    # Appliquer les filtres
    filtered_annotations = annotations
    if selected_annotator and selected_annotator != "Tous":
        filtered_annotations = [ann for ann in filtered_annotations 
                              if ann["annotator"] == selected_annotator]
    if selected_image and selected_image != "Toutes":
        filtered_annotations = [ann for ann in filtered_annotations 
                              if ann["image"] == selected_image]
    
    # Préparer les données pour le tableau
    table_data = []
    for ann in filtered_annotations:
        table_data.append({
            "id": ann["id"],
            "image_name": ann["image"],
            "annotator": ann["annotator"], 
            "rect_count": len(ann["rectangles"]),
            "timestamp": ann["timestamp"][:19].replace("T", " ")
        })
    
    return table_data

def register_callbacks(app):
    # Callback pour remplir les options des filtres
    @app.callback(
        Output("filter-annotator", "options"),
        Output("filter-image", "options"),
        Input("annotations-table", "id")  # Trigger au chargement
    )
    def update_filter_options(_):
        all_annotations = get_all_annotations()
        
        if not all_annotations:
            return [], []
        
        # Options pour annoteurs
        annotators = list(set(ann["annotator"] for ann in all_annotations))
        annotator_options = [{"label": ann, "value": ann} for ann in sorted(annotators)]
        
        # Options pour images
        images = list(set(ann["image"] for ann in all_annotations))
        image_options = [{"label": img, "value": img} for img in sorted(images)]
        
        return annotator_options, image_options
    
    # Callback pour mettre à jour le tableau selon les filtres
    @app.callback(
        Output("annotations-table", "data"),
        [Input("filter-annotator", "value"),
         Input("filter-image", "value"),
         Input("table-refresh-trigger", "data")]  # Écoute aussi les changements du store
    )
    def update_table(selected_annotator, selected_image, refresh_trigger):
        return get_filtered_table_data(selected_annotator, selected_image)
    
    # Callback pour afficher la modification quand on sélectionne une ligne
    @app.callback(
        [Output("modification-section", "style"),
         Output("modification-canvas", "image_content"),
         Output("modification-canvas", "json_data"),
         Output("modification-info", "children"),
         Output("history-section", "style"),
         Output("modification-history", "children")],
        Input("annotations-table", "selected_rows"),
        State("annotations-table", "data")
    )
    def handle_row_selection(selected_rows, table_data):
        if not selected_rows or not table_data:
            return {"display": "none"}, "", '{"version": "4.6.0", "objects": []}', "", {"display": "none"}, "Sélectionnez une annotation pour voir son historique"
        
        # Récupérer l'annotation sélectionnée
        selected_row = table_data[selected_rows[0]]
        annotation_id = selected_row["id"]
        
        # Récupérer l'annotation complète
        all_annotations = get_all_annotations()
        selected_annotation = next((ann for ann in all_annotations if ann["id"] == annotation_id), None)
        
        if not selected_annotation:
            return {"display": "none"}, "", '{"version": "4.6.0", "objects": []}', "", {"display": "none"}, "Annotation introuvable"
        
        image_name = selected_annotation["image"]
        image_path = os.path.join(IMAGES_DIR, image_name)
        existing_rectangles = selected_annotation["rectangles"]
        annotator_color = get_annotator_color(selected_annotation["annotator"])
        
        # Canvas pour modification avec image composite
        if os.path.exists(image_path):
            # Créer une image avec seulement les rectangles de l'annotation sélectionnée
            canvas_image_src = create_image_with_rectangles(
                image_path, 
                existing_rectangles, 
                annotator_color
            )
        else:
            canvas_image_src = ""
        
        # Plus besoin d'objets canvas pour les rectangles existants car ils sont dans l'image
        canvas_objects = []
        canvas_json = {"version": "4.6.0", "objects": canvas_objects}
        
        # Info sur la modification
        info = html.Div([
            html.H6(f"Ajout sur: {image_name}"),
            html.P(f"Annotation #{annotation_id} par {selected_annotation['annotator']}", 
                  className="text-muted small"),
            html.P("🎯 Les rectangles existants sont déjà dessinés sur l'image. Ajoutez vos nouveaux rectangles ORANGE par-dessus !", 
                  className="text-warning small")
        ])
        
        # Générer l'historique des modifications
        history_content = []
        if "modification_history" in selected_annotation and selected_annotation["modification_history"]:
            # Annotation initiale
            initial_rect_count = len(selected_annotation["rectangles"])
            for entry in selected_annotation["modification_history"]:
                initial_rect_count -= entry["rectangles_added"]
            
            history_content.append(
                html.Div([
                    html.Strong("📝 Annotation initiale", className="text-primary"),
                    html.Span(f" - {selected_annotation['annotator']}", className="ms-2"),
                    html.Br(),
                    html.Small(f"{initial_rect_count} rectangle(s) • {selected_annotation['timestamp'][:19].replace('T', ' ')}", 
                             className="text-muted")
                ], className="mb-2 p-2 border-start border-primary border-3")
            )
            
            # Modifications
            for i, entry in enumerate(selected_annotation["modification_history"]):
                history_content.append(
                    html.Div([
                        html.Strong(f"✏️ Modification {i+1}", className="text-success"),
                        html.Span(f" - {entry['modifier_name']}", className="ms-2"),
                        html.Br(),
                        html.Small(f"+{entry['rectangles_added']} rectangle(s) ajouté(s) • Total: {entry['total_rectangles_after']} • {entry['timestamp'][:19].replace('T', ' ')}", 
                                 className="text-muted")
                    ], className="mb-2 p-2 border-start border-success border-3")
                )
        else:
            history_content = [
                html.Div([
                    html.Strong("📝 Annotation initiale", className="text-primary"),
                    html.Span(f" - {selected_annotation['annotator']}", className="ms-2"),
                    html.Br(),
                    html.Small(f"{len(selected_annotation['rectangles'])} rectangle(s) • {selected_annotation['timestamp'][:19].replace('T', ' ')}", 
                             className="text-muted")
                ], className="mb-2 p-2 border-start border-primary border-3")
            ]
        
        return {"display": "block"}, canvas_image_src, json.dumps(canvas_json), info, {"display": "block"}, history_content
    
    # Combine the callbacks for save-status and table-refresh-trigger
    @app.callback(
        [Output("review-save-status", "children"),
         Output("table-refresh-trigger", "data")],
        Input("save-additions", "n_clicks"),
        [State("modification-canvas", "json_data"),
         State("annotations-table", "selected_rows"),
         State("annotations-table", "data"),
         State("modifier-name", "value")],
        prevent_initial_call=True
    )
    def save_additions_and_refresh_table(n_clicks, canvas_data, selected_rows, table_data, modifier_name):
        if not n_clicks or not selected_rows or not table_data:
            return "", 0

        if not modifier_name or not modifier_name.strip():
            return html.Span("❌ Veuillez saisir votre nom", className="text-danger"), 0

        # Récupérer l'annotation sélectionnée
        selected_row = table_data[selected_rows[0]]
        image_name = selected_row["image_name"]

        # Parser le JSON du canvas si c'est une string
        if isinstance(canvas_data, str):
            try:
                canvas_data = json.loads(canvas_data)
            except json.JSONDecodeError:
                return html.Span("❌ Erreur parsing canvas data", className="text-danger"), 0

        # Extraire les nouveaux rectangles du canvas
        new_rectangles = []
        if canvas_data and isinstance(canvas_data, dict) and "objects" in canvas_data:
            for obj in canvas_data["objects"]:
                if obj.get("type") == "rect":
                    rect = {
                        "x": int(float(obj.get("left", 0))),
                        "y": int(float(obj.get("top", 0))),
                        "width": int(float(obj.get("width", 0))),
                        "height": int(float(obj.get("height", 0))),
                        "color": get_annotator_color(modifier_name.strip())
                    }
                    new_rectangles.append(rect)

        if not new_rectangles:
            return html.Span("❌ Aucun nouveau rectangle à sauvegarder", className="text-warning"), 0

        try:
            # Récupérer l'annotation existante complète depuis le JSON
            selected_annotation_id = selected_row["id"]
            all_annotations = get_all_annotations()
            selected_annotation = next((ann for ann in all_annotations if ann["id"] == selected_annotation_id), None)

            if not selected_annotation:
                return html.Span("❌ Annotation introuvable", className="text-danger"), 0

            # Combiner les rectangles existants avec les nouveaux
            existing_rectangles = selected_annotation["rectangles"]
            all_rectangles = existing_rectangles + new_rectangles

            # Mettre à jour l'annotation existante avec l'historique
            success = update_annotation(selected_annotation_id, all_rectangles, modifier_name.strip(), len(new_rectangles))

            if success:
                import time
                return html.Span(f"✅ {len(new_rectangles)} rectangle(s) ajouté(s) ! Total: {len(all_rectangles)} rectangles",
                                 className="text-success"), time.time()
            else:
                return html.Span("❌ Erreur lors de la mise à jour", className="text-danger"), 0
        except Exception as e:
            return html.Span(f"❌ Erreur: {str(e)}", className="text-danger"), 0