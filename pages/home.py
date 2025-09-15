import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

# Page d'accueil (TD3: register_page)
dash.register_page(__name__, path="/", name="Accueil")

layout = dbc.Container([
    dbc.Row([
        dbc.Col(dbc.Card([
            html.H3("Bienvenue 👋"),
            html.P("Application d’annotation d’images de voitures (boîtes englobantes)."),
            html.Ul([
                html.Li("Annoter des images (outil rectangle)"),
                html.Li("Saisir l’annotateur (stocké localement)"),
                html.Li("Relire et modifier les annotations"),
                html.Li("Statistiques descriptives + export COCO"),
            ]),
            dcc.Markdown("""
**Conseil** : commence par **Annoter** pour définir ton nom, puis navigue vers **Relecture** et **Stats & Export**.
            """, className="muted")
        ], className="card"), md=8)
    ])
], fluid=True)
