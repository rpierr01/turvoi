from dash import Dash, html
import dash
import dash_bootstrap_components as dbc
from flask_caching import Cache

# App multipages (conforme TD3: use_pages=True)
app = Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.FLATLY], title="Car Annotation App")
server = app.server

# Cache disque pour accélérer stats/IAA
cache = Cache(app.server, config={
    "CACHE_TYPE": "FileSystemCache",
    "CACHE_DIR": ".cache",
    "CACHE_THRESHOLD": 256,
})
app.server.config["APP_CACHE"] = cache

# Barre de navigation et container pages n
app.layout = html.Div([
    dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand("🚗 Car Annotation App", className="navbar-brand"),
            dbc.Nav(className="ms-auto", children=[
                html.Span("Raccourcis : "), html.Kbd("N"), html.Span(" / "),
                html.Kbd("P"), html.Span(" / "), html.Kbd("S"),
            ],)
        ]), color="primary", dark=True
    ),
    dbc.Container([dash.page_container], fluid=True)
])

# Raccorde les callbacks définis dans les pages
from pages import annotate as pg_annotate, review as pg_review, stats as pg_stats
pg_annotate.register_callbacks(app)
pg_review.register_callbacks(app)
pg_stats.register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=False)
