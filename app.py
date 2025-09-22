# app.py

from dash import Dash, html
import dash
import dash_bootstrap_components as dbc
from flask_caching import Cache

app = Dash(__name__, use_pages=True,
           external_stylesheets=[dbc.themes.FLATLY],
           title="Car Annotation App")
server = app.server

cache = Cache(app.server, config={
    "CACHE_TYPE": "FileSystemCache",
    "CACHE_DIR": ".cache",
    "CACHE_THRESHOLD": 256,
})
app.server.config["APP_CACHE"] = cache

# 🔽 Génération dynamique des liens vers toutes les pages
nav_links = [
    dbc.NavItem(dbc.NavLink(page["name"], href=page["path"]))
    for page in dash.page_registry.values()
]

app.layout = html.Div([
    dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand("🚗 Car Annotation App", className="navbar-brand"),
            dbc.Nav(nav_links, className="ms-auto"),
        ]), color="primary", dark=True
    ),
    dbc.Container([dash.page_container], fluid=True)
])

# Raccorde les callbacks
from pages import annotate as pg_annotate, review as pg_review, stats as pg_stats
pg_annotate.register_callbacks(app)
pg_review.register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=False)