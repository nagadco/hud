import os
from datetime import datetime
from functools import lru_cache

import pandas as pd
import numpy as np
from geopy.distance import geodesic
from rapidfuzz import fuzz

import dash
from dash import Dash, html, dcc, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import plotly.express as px


# ----------------------------------------------------------------------------
# Data loading helpers
# ----------------------------------------------------------------------------

def sample_data():
    """Return a small random dataset if no CSV is found."""
    rng = np.random.default_rng(0)
    n = 30
    names = [f"POI {i}" for i in range(n)]
    lats = 24 + rng.random(n) * 0.5
    lons = 54 + rng.random(n) * 0.5
    updated = [datetime.now().strftime("%Y-%m-%d")] * n
    brand = rng.choice(["HudHud", "Other"], n)
    territory = rng.choice(["A", "B", "C"], n)
    return pd.DataFrame(
        {
            "name": names,
            "latitude": lats,
            "longitude": lons,
            "updated_date": updated,
            "brand": brand,
            "territory": territory,
        }
    )


@lru_cache(maxsize=1)
def load_data(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        df = pd.read_csv(path)
    else:
        df = sample_data()
    if "updated_date" in df.columns:
        df["updated_date"] = pd.to_datetime(df["updated_date"], errors="coerce")
    else:
        df["updated_date"] = pd.Timestamp.now()
    df.dropna(subset=["latitude", "longitude"], inplace=True)
    df["age_days"] = (pd.Timestamp.now() - df["updated_date"]).dt.days
    df["age_group"] = pd.cut(
        df["age_days"],
        bins=[-1, 29, 365, 10_000],
        labels=["new", "old", "very_old"],
    )
    return df


# ----------------------------------------------------------------------------
# Duplicate detection
# ----------------------------------------------------------------------------

def find_duplicates(df: pd.DataFrame, threshold: int = 85, max_meters: float = 100) -> pd.DataFrame:
    rows = []
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            name1, name2 = df.iloc[i]["name"], df.iloc[j]["name"]
            sim = fuzz.token_set_ratio(str(name1), str(name2))
            if sim < threshold:
                continue
            loc1 = (df.iloc[i]["latitude"], df.iloc[i]["longitude"])
            loc2 = (df.iloc[j]["latitude"], df.iloc[j]["longitude"])
            dist = geodesic(loc1, loc2).meters
            if dist <= max_meters:
                rows.append({
                    "poi_1": name1,
                    "poi_2": name2,
                    "similarity": sim,
                    "distance_m": int(dist),
                })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Translations
# ----------------------------------------------------------------------------

translations = {
    "en": {
        "tagline": "Local Insider",
        "coverage": "Coverage Dashboard",
        "temporal": "Temporal Analysis",
        "duplicate": "Duplicate Finder",
        "heatmap": "Brand Heatmap",
    },
    "ar": {
        "tagline": "أدرى بشعابها",
        "coverage": "تغطية المناطق",
        "temporal": "تحليل زمني",
        "duplicate": "البحث عن التكرار",
        "heatmap": "خريطة العلامات",
    },
}


# ----------------------------------------------------------------------------
# Dash App
# ----------------------------------------------------------------------------

external_stylesheets = [dbc.themes.BOOTSTRAP]
app = Dash(__name__, external_stylesheets=external_stylesheets)

DATA_PATH = os.getenv("POI_CSV", "poi_logs_with_territories.csv")

df = load_data(DATA_PATH)

# Sidebar
sidebar = html.Div(
    [
        html.H2("HudHud", className="sidebar-title"),
        html.P(id="tagline"),
        dbc.Nav(
            [
                dbc.NavLink(id="nav-coverage", href="/", active="exact"),
                dbc.NavLink(id="nav-temporal", href="/temporal", active="exact"),
                dbc.NavLink(id="nav-duplicate", href="/duplicates", active="exact"),
                dbc.NavLink(id="nav-heatmap", href="/heatmap", active="exact"),
            ],
            vertical=True,
            pills=True,
        ),
        html.Hr(),
        dbc.RadioItems(
            id="language-toggle",
            options=[{"label": "EN", "value": "en"}, {"label": "العربية", "value": "ar"}],
            value="en",
            inline=True,
        ),
    ],
    className="sidebar",
)

content = html.Div(id="page-content", className="content")

app.layout = dbc.Container([
    dcc.Location(id="url"),
    sidebar,
    content
], fluid=True)


# ----------------------------------------------------------------------------
# Page layouts
# ----------------------------------------------------------------------------

def coverage_layout(data: pd.DataFrame, lang: str):
    bar = px.bar(
        data.groupby("territory").size().reset_index(name="count"),
        x="territory",
        y="count",
        labels={"territory": "Territory", "count": "POIs"},
        title=translations[lang]["coverage"],
    )
    rows = [
        dl.Marker(position=[r.latitude, r.longitude])
        for r in data.itertuples()
    ]
    map_component = dl.Map(
        [dl.TileLayer(), dl.MarkerClusterGroup(children=rows)],
        center=[data.latitude.mean(), data.longitude.mean()],
        zoom=10,
        style={"height": "500px"},
    )
    return html.Div([
        dcc.Graph(figure=bar),
        map_component,
    ])


def temporal_layout(data: pd.DataFrame, lang: str):
    cats = data["age_group"].value_counts().to_dict()
    counters = html.Ul([
        html.Li(f"new: {cats.get('new',0)}"),
        html.Li(f"old: {cats.get('old',0)}"),
        html.Li(f"very old: {cats.get('very_old',0)}"),
    ])
    slider = dcc.Slider(
        id="date-slider",
        min=data["age_days"].min(),
        max=data["age_days"].max(),
        step=1,
        value=data["age_days"].max(),
        marks=None,
    )
    return html.Div([
        counters,
        slider,
    ])


def duplicate_layout(data: pd.DataFrame, lang: str):
    duplicates = find_duplicates(data)
    table = dash_table.DataTable(
        duplicates.to_dict("records"),
        columns=[{"name": c, "id": c} for c in duplicates.columns],
        page_size=10,
    )
    return html.Div([table])


def heatmap_layout(data: pd.DataFrame, lang: str):
    brands = sorted(data["brand"].dropna().unique())
    dropdown = dcc.Dropdown(brands, value=brands[0] if brands else None, id="brand-select")
    heatmap = dl.Map([
        dl.TileLayer(),
        dl.LayerGroup(id="heat-layer"),
    ], center=[data.latitude.mean(), data.longitude.mean()], zoom=10, style={"height": "500px"})
    return html.Div([dropdown, heatmap])


# ----------------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------------

@app.callback(
    Output("tagline", "children"),
    Output("nav-coverage", "children"),
    Output("nav-temporal", "children"),
    Output("nav-duplicate", "children"),
    Output("nav-heatmap", "children"),
    Output("page-content", "dir"),
    Input("language-toggle", "value"),
)
def update_language(lang):
    t = translations[lang]
    direction = "rtl" if lang == "ar" else "ltr"
    return (
        t["tagline"],
        t["coverage"],
        t["temporal"],
        t["duplicate"],
        t["heatmap"],
        direction,
    )


@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("language-toggle", "value"),
)
def display_page(pathname, lang):
    if pathname == "/temporal":
        return temporal_layout(df, lang)
    elif pathname == "/duplicates":
        return duplicate_layout(df, lang)
    elif pathname == "/heatmap":
        return heatmap_layout(df, lang)
    return coverage_layout(df, lang)


if __name__ == "__main__":
    app.run_server(debug=False, host="0.0.0.0", port=8050)

