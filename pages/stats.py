import io, json
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
from services.stats import dataset_progress, by_annotator_counts, iaa_summary
from services.annotation_io import load_annotations, IMAGES_DIR
from services.export_coco import to_coco

# Page stats + export
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
    @app.callback(Output("progress-fig", "figure"), Input("url", "pathname"))
    def _progress(_):
        imgs, completed = dataset_progress()
        fig = px.bar(x=imgs, y=completed, labels={"x": "image", "y": "#enregistrements"})
        fig.update_layout(xaxis_tickangle=-45)
        return fig

    @app.callback(Output("by-ann-fig", "figure"), Input("url", "pathname"))
    def _by_ann(_):
        counts = by_annotator_counts()
        fig = px.bar(x=counts.index, y=counts.values, labels={"x": "annotateur", "y": "#enregistrements"})
        return fig

    @app.callback(Output("iaa-fig", "figure"), Output("conflict-list", "children"), Input("iou-thr", "value"))
    def _iaa(thr):
        summary = iaa_summary(iou_threshold=float(thr))
        per = summary["per_image"]
        items = [html.Li(f"{img} — IoU={v['mean_iou']:.2f}") for img, v in per.items()
                 if v["mean_iou"] is not None and v["flag"]]
        txt = html.Div([
            html.Strong("Images à conflit (< seuil) :"),
            html.Ul(items or [html.Li("Aucun conflit")])
        ])
        xs, ys = [], []
        for img, v in per.items():
            if v["mean_iou"] is not None:
                xs.append(img); ys.append(v["mean_iou"])
        fig = px.scatter(x=xs, y=ys, labels={"x":"image","y":"IoU moyen"})
        fig.update_layout(title="IoU moyen par image (paires d’annotateurs)")
        return fig, txt

    @app.callback(Output("dl-coco", "data"), Output("export-msg", "children"),
                  Input("export-coco", "n_clicks"), prevent_initial_call=True)
    def _export(_):
        df = load_annotations()
        if df.empty:
            return None, "Aucune annotation à exporter"
        coco = to_coco(df, IMAGES_DIR)
        buf = io.StringIO()
        json.dump(coco, buf)
        data = dict(content=buf.getvalue(), filename="annotations_cars_coco.json")
        return data, "✅ Export généré"
