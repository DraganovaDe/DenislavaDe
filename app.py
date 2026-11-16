"""
WebLog Observatory — a pastel Streamlit dashboard for Apache access logs.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_loader import SEGMENT_ORDER, STATUS_LABELS, load_data, segment, split_views

st.set_page_config(page_title="WebLog Observatory", page_icon="⭐", layout="wide")

# ── Palette ──────────────────────────────────────────────────────────────────
# Pastel surfaces for cards/backgrounds; mid-tone pastels for data marks
# (validated: lightness band, chroma floor, colour-blind separation).
INK, INK_SOFT, INK_MUTED = "#2E2A3B", "#5F5A70", "#8F8AA0"
GRID = "#ECE8F4"
# Chart colours are medium pastels from the same family as the KPI card tints,
# so every chart reads as part of the app. Values are always labelled on the
# marks or in a legend, so the soft colours never carry meaning alone.
BLUE, ROSE, AMBER, SAGE, LILAC = "#9FC0EE", "#F0A9C0", "#F2CF8A", "#9AD6BC", "#B3A8EC"
LINE_LAV, LINE_ROSE = "#8F83DA", "#E08AA8"  # slightly deeper so thin lines stay visible
TINTS = {  # card backgrounds
    "lavender": "#EEEBFB", "blush": "#FBEAF0", "mint": "#E4F5EE",
    "butter": "#FBF3E2", "sky": "#E6EEFB",
}
SEQ = ["#F5F2FC", "#E4DEF7", "#CFC6F1", "#B8ACE9", "#A194E0", "#8A7CD5"]
STATUS_COLORS = {
    "1xx Info": LILAC, "2xx Success": SAGE, "3xx Redirect": BLUE,
    "4xx Client Err": AMBER, "5xx Server Err": ROSE,
}
SEGMENT_COLORS = dict(zip(SEGMENT_ORDER, SEQ[2:]))  # ordinal → one hue, light to dark
DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ── Version compatibility ────────────────────────────────────────────────────
# Rounded bar ends need plotly >= 5.19; older installs simply get square bars.
try:
    go.bar.Marker(cornerradius=4)
    BAR_RADIUS = {"cornerradius": 4}
except ValueError:
    BAR_RADIUS = {}

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"], .stMarkdown, .stText, p, li, label {{ font-family: 'Inter', sans-serif; }}
    .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }}
    h1, h2, h3 {{ font-family: 'Fraunces', serif !important; color: {INK}; font-weight: 600 !important; letter-spacing: -0.01em; }}
    .hero {{
        background: linear-gradient(120deg, {TINTS['lavender']} 0%, {TINTS['blush']} 50%, {TINTS['mint']} 100%);
        border-radius: 22px; padding: 28px 32px; margin-bottom: 22px;
        border: 1px solid #EEE9F6;
    }}
    .hero h1 {{ margin: 0; font-size: 2.3rem; }}
    .hero p {{ margin: 6px 0 0; color: {INK_SOFT}; font-size: 0.98rem; }}
    .kpi {{
        border-radius: 18px; padding: 18px 20px; border: 1px solid rgba(46,42,59,0.05);
        height: 132px; box-sizing: border-box;
    }}
    .kpi .label {{ font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; color: {INK_SOFT}; font-weight: 600; }}
    .kpi .value {{ font-family: 'Fraunces', serif; font-size: 2.0rem; color: {INK}; line-height: 1.2; margin-top: 4px; }}
    .kpi .sub {{ font-size: 0.82rem; color: {INK_MUTED}; margin-top: 2px; }}
    .card-title {{ font-family: 'Fraunces', serif; font-size: 1.15rem; color: {INK}; margin: 0 0 2px; }}
    .card-sub {{ font-size: 0.85rem; color: {INK_MUTED}; margin: 0 0 6px; }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 18px !important; border-color: #EEE9F6 !important; background: #FFFFFF;
    }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 999px; padding: 6px 16px; background: #F3F0FA; color: {INK_SOFT}; height: auto;
    }}
    .stTabs [aria-selected="true"] {{ background: {TINTS['lavender']}; color: {INK}; font-weight: 600; }}
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}
    section[data-testid="stSidebar"] {{ background: #E9E3F7; border-right: 1px solid #D9D0F0; }}
    section[data-testid="stSidebar"] h3 {{ color: {INK}; }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
    section[data-testid="stSidebar"] div[data-baseweb="input"] {{ background: #FFFFFF; border-color: #D9D0F0; }}
    /* equal-height cards: columns in a row stretch, and the card fills its column */
    div[data-testid="stHorizontalBlock"] {{ align-items: stretch; }}
    div[data-testid="stColumn"] > div, div[data-testid="column"] > div {{ height: 100%; }}
    div[data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="column"] div[data-testid="stVerticalBlockBorderWrapper"] {{ height: 100%; }}
    footer, #MainMenu {{ visibility: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def style(fig: go.Figure, height: int = 340, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=INK_SOFT, size=12),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(color=INK, family="Inter")),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=INK_MUTED), title_font=dict(color=INK_MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=INK_MUTED), title_font=dict(color=INK_MUTED))
    return fig


def card(title: str, subtitle: str = ""):
    try:
        box = st.container(border=True)  # streamlit >= 1.29
    except TypeError:
        box = st.container()
    box.markdown(f'<p class="card-title">{title}</p>' + (f'<p class="card-sub">{subtitle}</p>' if subtitle else ""),
                 unsafe_allow_html=True)
    return box


def show(box, fig):
    box.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def kpi(col, label: str, value: str, sub: str, tint: str):
    col.markdown(
        f'<div class="kpi" style="background:{TINTS[tint]}"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def hbar(data: pd.DataFrame, y: str, x: str, color=BLUE, height=360, hover_label="Requests"):
    data = data.sort_values(x)
    fig = go.Figure(go.Bar(
        x=data[x], y=data[y], orientation="h",
        marker=dict(color=color, **BAR_RADIUS),
        text=data[x].map("{:,}".format), textposition="outside",
        textfont=dict(color=INK_SOFT, size=11), cliponaxis=False,
        hovertemplate=f"<b>%{{y}}</b><br>{hover_label}: %{{x:,}}<extra></extra>",
    ))
    style(fig, height).update_layout(margin=dict(l=8, r=48, t=8, b=8))
    fig.update_xaxes(showticklabels=False, showgrid=False)
    fig.update_yaxes(showgrid=False, type="category", tickfont=dict(color=INK, size=12))
    return fig


def donut(labels, values, colors, center: str):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62, sort=False,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="percent", textposition="outside", textfont=dict(color=INK_SOFT, size=12),
        hovertemplate="<b>%{label}</b><br>%{value:,} requests · %{percent}<extra></extra>",
    ))
    fig.add_annotation(text=center, showarrow=False, font=dict(family="Fraunces, serif", size=18, color=INK))
    style(fig, 320, legend=True)
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.12, yanchor="top"),
                      margin=dict(l=40, r=40, t=24, b=40))
    return fig


# ── Data ─────────────────────────────────────────────────────────────────────
df_all = load_data()

with st.sidebar:
    st.markdown("### ⭐ Filters")
    min_d, max_d = df_all["date"].min(), df_all["date"].max()
    picked = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    start, end = (picked if isinstance(picked, (tuple, list)) and len(picked) == 2 else (min_d, max_d))

    lens = st.radio(
        "Traffic lens for visitor charts",
        ["Human page views", "All content pages", "Every request"],
        help="Human page views = no static assets, no bots (the notebook's df_humans).",
    )
    statuses = st.multiselect("Status classes", STATUS_LABELS, default=[
        s for s in STATUS_LABELS if s in set(df_all["status_cat"].astype(str))
    ])
    st.markdown("---")
    st.caption(f"Source · `weblog.txt` · {len(df_all):,} parsed lines")

df = df_all[(df_all["date"] >= start) & (df_all["date"] <= end)]
if statuses:
    df = df[df["status_cat"].astype(str).isin(statuses)]
df_pages, df_humans = split_views(df)
focus = {"Human page views": df_humans, "All content pages": df_pages, "Every request": df}[lens]

if df.empty:
    st.warning("No requests match the current filters.")
    st.stop()

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    f"""<div class="hero"><h1>WebLog Observatory</h1>
    <p>Apache access-log insights · {start:%d %b %Y} → {end:%d %b %Y} · lens: <b>{lens.lower()}</b></p></div>""",
    unsafe_allow_html=True,
)

# ── KPIs ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
kpi(c1, "Total requests", f"{len(df):,}", f"{len(df_humans):,} human views", "lavender")
kpi(c2, "Unique visitors", f"{df['ip'].nunique():,}", "distinct IP addresses", "sky")
bw = df["size"].sum()
kpi(c3, "Bandwidth", f"{bw/1e9:.2f} GB" if bw >= 1e8 else f"{bw/1e6:.1f} MB", "bytes served", "mint")
kpi(c4, "Error rate", f"{(df['status'] >= 400).mean():.1%}", "status ≥ 400", "blush")
kpi(c5, "Bot traffic", f"{df['is_bot'].mean():.1%}", f"{df['is_static'].mean():.0%} static assets", "butter")
st.write("")

tab_over, tab_content, tab_rhythm, tab_aud, tab_err, tab_data = st.tabs(
    ["Overview", "Content", "Rhythm", "Audience", "Errors", "Data"]
)

# ── Overview ─────────────────────────────────────────────────────────────────
with tab_over:
    box = card("Daily traffic", f"{lens} per day, with a 7-day rolling average")
    log_y = (box.toggle if hasattr(box, "toggle") else box.checkbox)("Log scale", value=True, help="Keeps quiet days visible next to traffic spikes.")
    daily = focus.groupby("date").size().rename("requests").reset_index()
    if daily.empty:
        box.info("No data for this lens.")
    else:
        daily["date"] = pd.to_datetime(daily["date"])
        daily = daily.set_index("date").asfreq("D", fill_value=0).reset_index()
        daily["avg7"] = daily["requests"].rolling(7, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["requests"], name="Daily", mode="lines",
            line=dict(color="#B9B0EC", width=1.2), fill="tozeroy", fillcolor="rgba(185,176,236,0.25)",
            hovertemplate="%{x|%a %d %b %Y}<br>%{y:,} requests<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["avg7"], name="7-day average", mode="lines",
            line=dict(color=LINE_LAV, width=2), hovertemplate="7-day avg: %{y:,.0f}<extra></extra>",
        ))
        style(fig, 340, legend=True).update_layout(hovermode="x unified")
        if log_y:
            # log(0) is undefined: drop silent days so the lines break instead of plunging
            fig.update_yaxes(type="log", dtick=1)
            fig.update_traces(fill=None, connectgaps=False,
                              y=daily["requests"].where(daily["requests"] > 0), selector=dict(name="Daily"))
            fig.update_traces(connectgaps=False,
                              y=daily["avg7"].where(daily["avg7"] >= 1), selector=dict(name="7-day average"))
        show(box, fig)
        box.caption(f"{len(daily)} days · average {daily['requests'].mean():,.0f} per day · "
                    f"peak {daily['requests'].max():,} on {daily.loc[daily['requests'].idxmax(), 'date']:%d %b %Y}")

    a, b = st.columns(2)
    with a:
        box = card("HTTP status classes", "All requests")
        sc = df["status_cat"].astype(str).value_counts().reindex(STATUS_LABELS).dropna()
        show(box, donut(sc.index, sc.values, [STATUS_COLORS[s] for s in sc.index], f"{len(df):,}"))
    with b:
        box = card("Bots vs humans", "Content pages only")
        tt = df_pages["is_bot"].map({True: "Bot", False: "Human"}).value_counts().reindex(["Human", "Bot"]).dropna()
        show(box, donut(tt.index, tt.values, [SAGE if t == "Human" else ROSE for t in tt.index], f"{len(df_pages):,}"))

# ── Content ──────────────────────────────────────────────────────────────────
with tab_content:
    a, b = st.columns(2)
    with a:
        box = card("Top 10 pages", lens)
        top = focus["url"].value_counts().head(10).rename_axis("url").reset_index(name="hits")
        top["url"] = top["url"].map(lambda u: u if len(u) <= 36 else u[:35] + "…")
        show(box, hbar(top, "url", "hits", BLUE, 400))
    with b:
        box = card("Top sections", "First URL segment")
        sec = focus["section"].value_counts().head(10).rename_axis("section").reset_index(name="hits")
        show(box, hbar(sec, "section", "hits", LILAC, 400))

    box = card("Top referrers", "Where visitors came from (excluding direct and self-referrals)")
    ref = focus.loc[focus["referer"] != "-", "referer"].str.extract(r"https?://([^/]+)")[0].dropna()
    ref = ref[~ref.str.contains("huaxia", case=False)]
    if ref.empty:
        box.info("No external referrers in this selection.")
    else:
        rc = ref.value_counts().head(8).rename_axis("domain").reset_index(name="hits")
        show(box, hbar(rc, "domain", "hits", SAGE, 40 + 36 * len(rc)))

# ── Rhythm ───────────────────────────────────────────────────────────────────
with tab_rhythm:
    box = card("Weekly rhythm", f"{lens} by day of week and hour (UTC)")
    heat = (focus.groupby(["day_of_week", "hour"]).size().unstack(fill_value=0)
            .reindex(index=range(7), columns=range(24), fill_value=0))
    fig = go.Figure(go.Heatmap(
        z=heat.values, x=[f"{h:02d}" for h in range(24)], y=DAY_LABELS,
        colorscale=[[i / (len(SEQ) - 1), c] for i, c in enumerate(SEQ)],
        xgap=3, ygap=3, colorbar=dict(thickness=10, outlinewidth=0, tickfont=dict(color=INK_MUTED)),
        hovertemplate="%{y} %{x}:00<br>%{z:,} requests<extra></extra>",
    ))
    style(fig, 330)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(title="Hour of day")
    show(box, fig)

    a, b = st.columns(2)
    with a:
        box = card("Hourly profile", "Share of requests by hour")
        hourly = focus.groupby("hour").size().reindex(range(24), fill_value=0)
        fig = go.Figure(go.Bar(
            x=hourly.index, y=hourly.values, marker=dict(color=BLUE, **BAR_RADIUS),
            hovertemplate="%{x}:00 · %{y:,} requests<extra></extra>",
        ))
        style(fig, 300).update_xaxes(dtick=3, title="Hour (UTC)")
        show(box, fig)
    with b:
        box = card("Monthly bandwidth", "All requests, megabytes served")
        mbw = (df.groupby("month")["size"].sum() / 1e6).rename("mb").reset_index()
        fig = go.Figure(go.Bar(
            x=mbw["month"], y=mbw["mb"], marker=dict(color=LILAC, **BAR_RADIUS),
            hovertemplate="%{x}<br>%{y:,.1f} MB<extra></extra>",
        ))
        style(fig, 300).update_xaxes(type="category", tickangle=-45)
        show(box, fig)

# ── Audience ─────────────────────────────────────────────────────────────────
with tab_aud:
    a, b = st.columns(2)
    with a:
        box = card("Engagement segments", "Human visitors by requests per IP · 1 · 2–4 · 5–15 · 16+")
        counts = df_humans.groupby("ip").size()
        seg = counts.map(segment).value_counts().reindex(SEGMENT_ORDER, fill_value=0)
        fig = go.Figure(go.Bar(
            x=seg.index, y=seg.values, marker=dict(color=[SEGMENT_COLORS[s] for s in seg.index], **BAR_RADIUS),
            text=[f"{v:,}" for v in seg.values], textposition="outside", textfont=dict(color=INK_SOFT),
            cliponaxis=False, hovertemplate="<b>%{x}</b><br>%{y:,} visitors<extra></extra>",
        ))
        style(fig, 360).update_yaxes(title="Visitors")
        show(box, fig)
    with b:
        unknown = focus.loc[focus["country_iso"] == "", "ip"].nunique()
        box = card("Where visitors come from",
                   f"Unique IPs per country · {unknown:,} private IPs not located")
        geo = (focus[focus["country_iso"] != ""].groupby("country")["ip"].nunique()
               .rename("visitors").reset_index())
        if geo.empty:
            box.info("No geolocation data available (GeoLite2-City.mmdb missing or only private IPs).")
        else:
            fig = px.choropleth(geo, locations="country", locationmode="country names", color="visitors",
                                color_continuous_scale=SEQ, hover_name="country")
            fig.update_traces(marker_line_color="white", marker_line_width=0.5,
                              hovertemplate="<b>%{hovertext}</b><br>%{z:,} visitors<extra></extra>")
            fig.update_geos(showframe=False, showcoastlines=False, showland=True, landcolor="#F4F2F8",
                            bgcolor="rgba(0,0,0,0)", projection_type="natural earth")
            style(fig, 360).update_layout(coloraxis_colorbar=dict(thickness=10, title=None, outlinewidth=0))
            show(box, fig)

    c, d, e = st.columns(3)
    for col, field, title, color in [(c, "browser", "Browsers", BLUE), (d, "os", "Operating systems", LILAC),
                                     (e, "device", "Devices", SAGE)]:
        with col:
            box = card(title, lens)
            vc = focus[field].value_counts().head(6).rename_axis(field).reset_index(name="hits")
            show(box, hbar(vc, field, "hits", color, 280))

# ── Errors ───────────────────────────────────────────────────────────────────
with tab_err:
    errs = df[df["status"] >= 400]
    if errs.empty:
        st.success("No errors in this selection. 🌸")
    else:
        a, b = st.columns(2)
        with a:
            box = card("Top 10 error URLs", "Butter = 4xx client error · blush = 5xx server error")
            top_err = (errs.groupby(["url", "status"]).size().reset_index(name="count")
                       .sort_values("count", ascending=False).head(10).sort_values("count"))
            top_err["label"] = top_err["url"].str.slice(0, 30) + "  ·  " + top_err["status"].astype(str)
            fig = go.Figure(go.Bar(
                x=top_err["count"], y=top_err["label"], orientation="h",
                marker=dict(color=[ROSE if s >= 500 else AMBER for s in top_err["status"]], **BAR_RADIUS),
                text=top_err["count"].map("{:,}".format), textposition="outside",
                textfont=dict(color=INK_SOFT), cliponaxis=False,
                hovertemplate="<b>%{y}</b><br>%{x:,} occurrences<extra></extra>",
            ))
            style(fig, 400).update_layout(margin=dict(l=8, r=48, t=8, b=8)).update_xaxes(showticklabels=False)
            fig.update_yaxes(showgrid=False, tickfont=dict(color=INK))
            show(box, fig)
        with b:
            box = card("Error codes", "Breakdown of status ≥ 400")
            codes = errs["status"].value_counts().rename_axis("code").reset_index(name="hits")
            codes["code"] = codes["code"].astype(str)
            codes = codes.head(8)
            show(box, hbar(codes, "code", "hits", [ROSE if c.startswith("5") else AMBER for c in codes.sort_values("hits")["code"]], 400))

        box = card("Error rate over time", "Weekly share of requests with status ≥ 400")
        wk = df.set_index("timestamp")["status"].ge(400).resample("W").agg(["mean", "size"]).reset_index()
        wk.loc[wk["size"] == 0, "mean"] = None  # leave gaps where the site was silent
        fig = go.Figure(go.Scatter(
            x=wk["timestamp"], y=wk["mean"], mode="lines+markers", line=dict(color=LINE_ROSE, width=2),
            marker=dict(size=6, color=LINE_ROSE, line=dict(color="white", width=1.5)), connectgaps=False,
            customdata=wk["size"], hovertemplate="Week of %{x|%d %b %Y}<br>%{y:.1%} errors · %{customdata:,} requests<extra></extra>",
        ))
        style(fig, 280).update_yaxes(tickformat=".0%")
        show(box, fig)

# ── Data ─────────────────────────────────────────────────────────────────────
with tab_data:
    box = card("Explore the parsed log", f"{len(focus):,} rows · {lens.lower()}")
    cols = ["timestamp", "ip", "country", "method", "url", "status", "status_cat", "size",
            "section", "browser", "os", "device", "is_static", "is_bot", "referer"]
    query = box.text_input("Filter URLs containing", placeholder="e.g. /course")
    view = focus[focus["url"].str.contains(query, case=False, regex=False)] if query else focus
    box.dataframe(view[cols].sort_values("timestamp", ascending=False), use_container_width=True,
                  height=440, hide_index=True)
    box.download_button("Download CSV", view[cols].to_csv(index=False).encode(), "weblog_filtered.csv", "text/csv")

    with st.expander("Schema"):
        st.dataframe(df_all.dtypes.astype(str).to_frame("dtype").assign(non_null=df_all.count()),
                     use_container_width=True)
