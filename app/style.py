"""Visuellt tema: LED-inspirerat galleri på svart, samma designspråk som React-sidan (web/).

Svart bas, dämpad grå text, en mättad accentfärg per vy, pixellogotyp och diagram som lyser mot svart.
"""

import altair as alt
import streamlit as st

BG = "#000000"
PANEL = "#0c0c0c"
LINE = "#262626"
FG = "#e8e8e8"
MUTED = "#aaaaaa"

# En LED-färg per flik, i samma ordning som flikarna. Samma färger som rutorna på React-sidan.
ACCENT_MAP = "#ff2a45"
ACCENT_SIGNIFICANT = "#19ff3c"
ACCENT_TRENDS = "#2f7bff"
ACCENT_PLATFORM = "#c13cff"
TAB_ACCENTS = (ACCENT_MAP, ACCENT_SIGNIFICANT, ACCENT_TRENDS, ACCENT_PLATFORM)

# 5x5-bitmap per bokstav, samma som i web/src/components/Wordmark.tsx.
_GLYPHS = {
    "S": ("01111", "10000", "01110", "00001", "11110"),
    "E": ("11111", "10000", "11110", "10000", "11111"),
    "I": ("11111", "00100", "00100", "00100", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "01110"),
}


def wordmark_svg(word: str = "SEISMO", pixel: int = 2, gap: int = 3, height: int = 18) -> str:
    rects = []
    for i, ch in enumerate(word):
        for y, row in enumerate(_GLYPHS[ch]):
            for x, bit in enumerate(row):
                if bit == "1":
                    rects.append(
                        f'<rect x="{(i * (5 + gap) + x) * pixel}" y="{y * pixel}" width="{pixel - 0.25}" height="{pixel - 0.25}"/>'
                    )
    width = (len(word) * (5 + gap) - gap) * pixel
    return (
        f'<svg viewBox="0 0 {width} {5 * pixel}" height="{height}" width="{round(width / (5 * pixel) * height)}" '
        f'role="img" aria-label="Seismo" fill="#fff" shape-rendering="crispEdges">{"".join(rects)}</svg>'
    )


def _tab_accent_css() -> str:
    return "\n".join(
        f'[data-baseweb="tab-list"] button[data-baseweb="tab"]:nth-of-type({i}) {{ --accent: {color}; }}'
        for i, color in enumerate(TAB_ACCENTS, start=1)
    )


_CSS = f"""
<style>
html, body, .stApp, button, input, textarea {{ font-family: 'IBM Plex Mono', ui-monospace, Menlo, Consolas, monospace !important; }}
.stApp {{ background: {BG}; color: {FG}; }}
.block-container {{ padding-top: 1.5rem; max-width: 1400px; }}
header[data-testid="stHeader"] {{ background: transparent; }}
footer, #MainMenu {{ visibility: hidden; }}
a {{ color: {FG}; }}

h1, h2, h3 {{ color: {FG}; font-weight: 500; letter-spacing: -0.01em; }}
h3 {{ font-size: 1.1rem; }}

.top {{ display: flex; align-items: center; justify-content: space-between; padding: 8px 0 24px; }}
.top .live {{ color: {MUTED}; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 8px; }}
.top .dot {{ width: 8px; height: 8px; background: {ACCENT_SIGNIFICANT}; box-shadow: 0 0 10px {ACCENT_SIGNIFICANT};
            animation: led 2.4s ease-in-out infinite; }}
.lede {{ color: {MUTED}; max-width: 75ch; margin: 0 0 24px; line-height: 1.55; }}
@keyframes led {{ 50% {{ opacity: .3; }} }}
@media (prefers-reduced-motion: reduce) {{ .top .dot {{ animation: none; }} }}

[data-testid="stMetric"], [class*="st-key-card_"] {{
    background: {PANEL} !important; border: 1px solid {LINE} !important; border-radius: 0; box-shadow: none; }}
[class*="st-key-card_"] {{ padding: 8px 12px; }}
[data-testid="stMetric"] {{ padding: 14px 16px; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-weight: 400; font-size: 13px; white-space: normal !important;
                                   overflow: visible !important; text-overflow: clip !important; line-height: 1.3; }}
[data-testid="stMetricLabel"] {{ min-height: 2.6em; align-items: flex-start; }}
[data-testid="stMetricValue"] {{ color: {FG}; font-weight: 600; font-size: clamp(1.1rem, 2vw, 1.5rem); }}
[data-testid="stMetricValue"] > div {{ text-overflow: clip; overflow: visible; white-space: normal; overflow-wrap: anywhere; }}

button[data-baseweb="tab"] {{ font-weight: 500; color: {MUTED}; --accent: #fff; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--accent); text-shadow: 0 0 12px var(--accent); }}
[data-baseweb="tab-highlight"] {{ background-color: {FG} !important; }}
[data-baseweb="tab-border"] {{ background-color: {LINE} !important; }}
{_tab_accent_css()}

.stButton > button {{ border-radius: 0; font-weight: 500; border: none; background: #fff; color: #000; }}
.stButton > button:hover {{ background: {MUTED}; color: #000; }}
:focus-visible {{ outline: 2px solid #5fd0e8; outline-offset: 3px; }}

[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
</style>
"""


def inject_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def header(lede: str, badge: str) -> None:
    st.markdown(
        f'<div class="top">{wordmark_svg()}<span class="live"><span class="dot"></span>{badge}</span></div>'
        f'<p class="lede">{lede}</p>',
        unsafe_allow_html=True,
    )


def dark_chart(chart: alt.Chart) -> alt.Chart:
    """Diagram utan egen bakgrund och med dämpade axlar, så att färgerna lyser mot svart."""
    return (
        chart.configure(background="transparent")
        .configure_view(stroke=None)
        .configure_axis(labelColor=MUTED, titleColor=MUTED, gridColor="#1c1c1c", domainColor=LINE, tickColor=LINE)
        .configure_legend(labelColor=MUTED, titleColor=MUTED)
    )
