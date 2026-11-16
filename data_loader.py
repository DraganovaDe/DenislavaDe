"""
data_loader.py — turns a raw Apache Combined Log into a clean pandas DataFrame.

Mirrors the steps in weblog.ipynb:
  1. regex-parse every line
  2. derive timestamp / date / hour / day_of_week / month
  3. flag static assets and bots, bucket status codes, extract URL section
  4. (extras) browser / OS / device from the user agent, country from GeoLite2
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.environ.get("WEBLOG_PATH", os.path.join(BASE_DIR, "weblog.txt"))
GEO_DB_PATH = os.environ.get("GEOIP_PATH", os.path.join(BASE_DIR, "GeoLite2-City.mmdb"))

LOG_PATTERN = re.compile(
    r'(?P<ip>\S+) \S+ \S+ '
    r'\[(?P<datetime>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<url>\S+) \S+" '
    r'(?P<status>\d{3}) (?P<size>\S+) '
    r'"(?P<referer>[^"]*)" '
    r'"(?P<user_agent>[^"]*)"'
)

STATIC_EXTENSIONS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".svg", ".woff", ".woff2", ".ttf", ".eot", ".map",
}
STATIC_PREFIXES = ("/css/", "/js/", "/fonts/", "/images/", "/static/", "/socket.io/")

BOT_PATTERNS = re.compile(
    r"bot|crawler|spider|crawl|slurp|bingbot|googlebot|feedcrawler|"
    r"yandex|baidu|semrush|ahref|mj12|dotbot|petalbot",
    re.I,
)

STATUS_LABELS = ["1xx Info", "2xx Success", "3xx Redirect", "4xx Client Err", "5xx Server Err"]
SEGMENT_ORDER = ["Bounced", "Casual", "Engaged", "Power User"]


# ── Helpers ──────────────────────────────────────────────────────────────────
def is_static(url: str) -> bool:
    lower = url.lower()
    if os.path.splitext(lower.split("?")[0])[1] in STATIC_EXTENSIONS:
        return True
    if lower.startswith(STATIC_PREFIXES):
        return True
    return "favicon" in lower


def section_of(url: str) -> str:
    path = url.split("?")[0]
    if path in ("", "/"):
        return "/"
    return "/" + path.strip("/").split("/")[0]


def segment(n: int) -> str:
    if n == 1:
        return "Bounced"
    if n <= 4:
        return "Casual"
    if n <= 15:
        return "Engaged"
    return "Power User"


@lru_cache(maxsize=None)
def _parse_ua(ua: str) -> tuple[str, str, str]:
    try:
        from user_agents import parse
    except ImportError:
        return ("Unknown", "Unknown", "Unknown")
    u = parse(ua)
    if u.is_bot:
        device = "Bot"
    elif u.is_mobile:
        device = "Mobile"
    elif u.is_tablet:
        device = "Tablet"
    elif u.is_pc:
        device = "Desktop"
    else:
        device = "Other"
    return (u.browser.family or "Other", u.os.family or "Other", device)


def _countries(ips: pd.Series) -> pd.Series:
    """Map each unique IP to a country name using GeoLite2 (if available)."""
    try:
        import geoip2.database
        import geoip2.errors
    except ImportError:
        return pd.Series("Unknown", index=ips.index)
    if not os.path.exists(GEO_DB_PATH):
        return pd.Series("Unknown", index=ips.index)

    lookup: dict[str, tuple[str, str]] = {}
    with geoip2.database.Reader(GEO_DB_PATH) as reader:
        for ip in ips.unique():
            try:
                c = reader.city(ip).country
                lookup[ip] = (c.name or "Unknown", c.iso_code or "")
            except (geoip2.errors.AddressNotFoundError, ValueError):
                lookup[ip] = ("Unknown", "")
    return ips.map(lookup)


# ── Main loader ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Parsing access log…")
def load_data(path: str = LOG_PATH) -> pd.DataFrame:
    records = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = LOG_PATTERN.match(line)
            if not m:
                continue
            d = m.groupdict()
            try:
                size = int(d["size"]) if d["size"] != "-" else 0
            except ValueError:
                size = 0
            records.append({
                "ip": d["ip"],
                "datetime_str": d["datetime"],
                "method": d["method"],
                "url": d["url"],
                "status": int(d["status"]),
                "size": size,
                "referer": d["referer"],
                "user_agent": d["user_agent"],
            })

    df = pd.DataFrame(records)

    # Timestamps
    df["timestamp"] = pd.to_datetime(
        df["datetime_str"], format="%d/%b/%Y:%H:%M:%S %z", errors="coerce", utc=True
    )
    df = df.dropna(subset=["timestamp"]).reset_index(drop=True)
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.strftime("%Y-%m")

    # Flags & buckets
    df["is_static"] = df["url"].map(is_static)
    df["is_bot"] = df["user_agent"].map(lambda ua: bool(BOT_PATTERNS.search(ua)))
    df["status_cat"] = pd.cut(
        df["status"], bins=[0, 199, 299, 399, 499, 599], labels=STATUS_LABELS
    )
    df["section"] = df["url"].map(section_of)

    # Extras: user agent breakdown + geography
    ua = df["user_agent"].map(_parse_ua)
    df["browser"] = ua.str[0]
    df["os"] = ua.str[1]
    df["device"] = ua.str[2]
    geo = _countries(df["ip"])
    df["country"] = geo.str[0]
    df["country_iso"] = geo.str[1]

    return df


def split_views(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (df_pages, df_humans) as defined in the notebook."""
    df_pages = df[~df["is_static"]]
    df_humans = df_pages[~df_pages["is_bot"]]
    return df_pages, df_humans
