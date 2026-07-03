"""The single IB house style applied to every figure, server-side.

Navy primary, muted teal accent, a low-saturation categorical ramp, Inter
typography, generous margins, thin horizontal gridlines only, white plot
background, no chart borders, thousands separators, and a subtle provenance
footnote. Applied explicitly to `figure.layout` (not only via a template) so the
palette / typography / spacing are directly present on the serialized figure.
"""
from __future__ import annotations

import plotly.graph_objects as go

# Palette
NAVY = "#1B2A41"          # primary
ACCENT = "#2E6E8E"        # accent (muted teal)
INK = "#22303C"           # text
MUTED = "#5A6B7B"         # subtitles / secondary text
GRID = "#E6EAEE"          # thin horizontal gridlines
AXIS_LINE = "#C7D0D9"

# Low-saturation categorical ramp
COLORWAY = [
    NAVY, ACCENT, "#6C8CA6", "#9DB4C4",
    "#4A5F7A", "#8A9BA8", "#B08D57", "#7E6B8F",
]

FONT_FAMILY = "Inter, 'Helvetica Neue', Arial, sans-serif"
FOOTNOTE = "Computed locally · figures exact"

MARGIN = dict(l=90, r=48, t=104, b=76)


def _title_html(title: str, subtitle: str) -> str:
    if subtitle:
        return (
            f"{title}"
            f"<br><span style='font-size:13px;font-weight:400;color:{MUTED}'>{subtitle}</span>"
        )
    return title


def apply_house_style(
    fig: go.Figure,
    *,
    title: str,
    subtitle: str = "",
    x_title: str = "",
    y_title: str = "",
    value_axis: str = "y",
) -> go.Figure:
    """Apply the house style. `value_axis` ("y" default, "x" for horizontal bars)
    selects which axis carries the thin gridlines + thousands separators."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONT_FAMILY, size=13, color=INK),
        colorway=list(COLORWAY),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=MARGIN,
        title=dict(
            text=_title_html(title, subtitle),
            font=dict(family=FONT_FAMILY, size=20, color=NAVY),
            x=0.0,
            xanchor="left",
            y=0.94,
            yanchor="top",
        ),
        showlegend=False,
        bargap=0.18,
    )

    def grid_axis(axis_title: str) -> dict:
        return dict(
            title=dict(text=axis_title, font=dict(size=13, color=MUTED)),
            showgrid=True,
            gridcolor=GRID,
            gridwidth=1,
            zeroline=False,
            showline=False,
            separatethousands=True,
            tickformat=",",
            tickfont=dict(size=12, color=MUTED),
        )

    def cat_axis(axis_title: str) -> dict:
        return dict(
            title=dict(text=axis_title, font=dict(size=13, color=MUTED)),
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor=AXIS_LINE,
            linewidth=1,
            ticks="outside",
            tickcolor=AXIS_LINE,
            tickfont=dict(size=12, color=MUTED),
        )

    if value_axis == "x":
        fig.update_layout(xaxis=grid_axis(x_title), yaxis=cat_axis(y_title))
    else:
        fig.update_layout(xaxis=cat_axis(x_title), yaxis=grid_axis(y_title))

    fig.add_annotation(
        text=FOOTNOTE,
        xref="paper", yref="paper",
        x=1.0, y=-0.16,
        xanchor="right", yanchor="top",
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=10, color=MUTED),
    )
    return fig
