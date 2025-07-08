"""Dash app to visualize POI performance."""

from __future__ import annotations

import dash
from dash import Dash, dcc, html, dash_table, Input, Output
import plotly.express as px

from poi_analyzer_core import POIManagementAnalyzer

CSV_PATH = "poi_logs_all_872025.csv"

analyzer = POIManagementAnalyzer(CSV_PATH)
summary_df = analyzer.get_summary()

app: Dash = dash.Dash(__name__)
app.title = "POI Performance Dashboard"

metrics = {
    "Submissions per Hour": "submissions_per_hour",
    "Average Quality Score": "avg_quality_score",
    "Quality Std Dev": "quality_std_dev",
}

def layout() -> html.Div:
    return html.Div(
        [
            html.H1("POI Surveyor Performance"),
            dash_table.DataTable(
                id="summary-table",
                columns=[{"name": c, "id": c} for c in summary_df.columns],
                data=summary_df.to_dict("records"),
            ),
            html.Hr(),
            html.Label("Select Metric:"),
            dcc.Dropdown(
                id="metric-dropdown",
                options=[{"label": k, "value": v} for k, v in metrics.items()],
                value="submissions_per_hour",
            ),
            dcc.Graph(id="metric-graph"),
        ]
    )

app.layout = layout()


@app.callback(Output("metric-graph", "figure"), Input("metric-dropdown", "value"))
def update_graph(metric: str):
    fig = px.bar(summary_df, x="created_by", y=metric, color="tier")
    fig.update_layout(xaxis_title="Surveyor", yaxis_title=metric.replace("_", " ").title())
    return fig


if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050)

