#!/usr/bin/env python3
"""Render the Market Pulse card used on the profile README.

Data comes from Sina Finance's public K-line endpoint, with Yahoo Finance as a
fallback. The script writes a light and a dark SVG so the README can switch
with prefers-color-scheme. It only uses the Python standard library.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

INDICES = [
    {"name": "SSE Composite", "code": "000001 · SH", "sina": "sh000001", "yahoo": "000001.SS"},
    {"name": "CSI 300", "code": "000300 · SH", "sina": "sh000300", "yahoo": "000300.SS"},
    {"name": "ChiNext", "code": "399006 · SZ", "sina": "sz399006", "yahoo": "399006.SZ"},
    {"name": "STAR 50", "code": "000688 · SH", "sina": "sh000688", "yahoo": "000688.SS"},
]

SANS = "-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',Helvetica,Arial,sans-serif"
MONO = "'SF Mono',ui-monospace,'Cascadia Mono',Consolas,monospace"


def get_json(url: str, referer: str = "https://finance.sina.com.cn/") -> object:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": referer,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_sina(item: dict) -> list[tuple[str, float]]:
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "CN_MarketData.getKLineData"
        f"?symbol={item['sina']}&scale=240&ma=5&datalen=40"
    )
    payload = get_json(url)
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("Sina returned too few rows")

    rows: list[tuple[str, float]] = []
    for entry in payload:
        try:
            rows.append((entry["day"], float(entry["close"])))
        except (KeyError, TypeError, ValueError):
            continue
    if len(rows) < 2:
        raise RuntimeError("Sina returned too few usable rows")
    return rows[-40:]


def fetch_yahoo(item: dict) -> list[tuple[str, float]]:
    symbol = urllib.parse.quote(item["yahoo"], safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        "?range=2mo&interval=1d"
    )
    payload = get_json(url, referer="https://finance.yahoo.com/")
    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]

    rows: list[tuple[str, float]] = []
    for stamp, close in zip(timestamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(stamp, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append((day, float(close)))
    if len(rows) < 2:
        raise RuntimeError("Yahoo Finance returned too few rows")
    return rows[-40:]


def load(item: dict) -> dict:
    try:
        rows = fetch_sina(item)
        source = "sina"
    except Exception as exc:  # noqa: BLE001 - fall back to a second public source
        print(f"Sina failed for {item['name']}: {exc}; trying Yahoo", flush=True)
        rows = fetch_yahoo(item)
        source = "yahoo"
    return {**item, "rows": rows, "source": source}


def palette(dark: bool) -> dict[str, str]:
    if dark:
        return {
            "bg1": "#0A101C",
            "bg2": "#101C2E",
            "ink": "#F3F0E7",
            "muted": "#98A9BE",
            "line": "#F3F0E7",
            "teal": "#5EEAD4",
            "red": "#F08A7A",
            "gold": "#E7BC80",
        }
    return {
        "bg1": "#FCFAF4",
        "bg2": "#F4EDDF",
        "ink": "#12212E",
        "muted": "#5C6B78",
        "line": "#12212E",
        "teal": "#0D7C8C",
        "red": "#C4574A",
        "gold": "#B07B3C",
    }


def fmt(value: float) -> str:
    return f"{value:,.2f}"


def build_svg(items: list[dict], dark: bool) -> str:
    p = palette(dark)
    width, height = 846, 210
    margin = 28
    panel_w = (width - margin * 2) / 4
    spark_w, spark_h = 170, 26
    spark_bottom = 194
    date = max(item["rows"][-1][0] for item in items)

    defs = [
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{p["bg1"]}"/>'
        f'<stop offset="1" stop-color="{p["bg2"]}"/></linearGradient>'
    ]
    body = [
        f'<rect width="{width}" height="{height}" rx="18" fill="url(#bg)"/>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="17.5" '
        f'fill="none" stroke="{p["line"]}" stroke-opacity="0.10"/>',
        f'<circle cx="{margin}" cy="28" r="3" fill="{p["gold"]}"/>',
        f'<text x="{margin + 14}" y="33" font-family="{MONO}" font-size="12" '
        f'letter-spacing="3.1" fill="{p["teal"]}">MARKET PULSE</text>',
        f'<text x="{margin}" y="54" font-family="{MONO}" font-size="9.5" '
        f'letter-spacing="1.5" fill="{p["muted"]}" opacity="0.8">CN · LAST CLOSE</text>',
        f'<text x="{width - margin}" y="33" text-anchor="end" font-family="{MONO}" '
        f'font-size="11" fill="{p["muted"]}">{date}</text>',
        f'<text x="{width - margin}" y="54" text-anchor="end" font-family="{MONO}" '
        f'font-size="9.5" letter-spacing="1.5" fill="{p["muted"]}" opacity="0.65">'
        f'30 SESSIONS</text>',
        f'<line x1="{margin}" y1="68" x2="{width - margin}" y2="68" '
        f'stroke="{p["line"]}" stroke-opacity="0.08"/>',
    ]

    for index, item in enumerate(items):
        rows = item["rows"][-30:]
        closes = [close for _, close in rows]
        last, previous = closes[-1], closes[-2]
        change = (last - previous) / previous * 100 if previous else 0.0
        positive = change >= 0
        color = p["teal"] if positive else p["red"]
        arrow = "▲" if positive else "▼"
        change_text = f"{arrow} {abs(change):.2f}%"

        x0 = margin + index * panel_w + 14
        body.extend(
            [
                f'<text x="{x0}" y="94" font-family="{SANS}" font-size="11" '
                f'letter-spacing="1.1" fill="{p["ink"]}" opacity="0.78">'
                f'{item["name"].upper()}</text>',
                f'<text x="{x0}" y="109" font-family="{MONO}" font-size="9" '
                f'letter-spacing="0.8" fill="{p["muted"]}" opacity="0.7">{item["code"]}</text>',
                f'<text x="{x0}" y="138" font-family="{MONO}" font-size="24" '
                f'fill="{p["ink"]}">{fmt(last)}</text>',
                f'<text x="{x0}" y="156" font-family="{MONO}" font-size="10.5" '
                f'letter-spacing="0.6" fill="{color}">{change_text}  ·  1D</text>',
            ]
        )

        # Sparkline: normalise the 30 closes into the panel's chart area.
        low, high = min(closes), max(closes)
        span = high - low or 1.0
        points = []
        for i, close in enumerate(closes):
            x = x0 + (i / (len(closes) - 1)) * spark_w
            y = spark_bottom - ((close - low) / span) * spark_h
            points.append((x, y))
        line = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
        area = (
            f"{line} L {x0 + spark_w:.1f} {spark_bottom:.1f} "
            f"L {x0:.1f} {spark_bottom:.1f} Z"
        )
        defs.append(
            f'<linearGradient id="f{index}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity="0.16"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/>'
            "</linearGradient>"
        )
        body.extend(
            [
                f'<path d="{area}" fill="url(#f{index})"/>',
                f'<path d="{line}" fill="none" stroke="{color}" stroke-width="1.4" '
                f'stroke-linejoin="round" stroke-linecap="round"/>',
                f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="2.2" fill="{color}"/>',
            ]
        )

        if index < len(items) - 1:
            divider_x = margin + (index + 1) * panel_w
            body.append(
                f'<line x1="{divider_x:.1f}" y1="78" x2="{divider_x:.1f}" y2="196" '
                f'stroke="{p["line"]}" stroke-opacity="0.08"/>'
            )

    title = "Market Pulse"
    desc = (
        f"Last close and 30-session trend for {', '.join(item['name'] for item in items)} "
        f"as of {date}."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="mp-title mp-desc">'
        f'<title id="mp-title">{title}</title><desc id="mp-desc">{desc}</desc>'
        f'<defs>{"".join(defs)}</defs>{"".join(body)}</svg>'
    )


def main() -> int:
    items = [load(item) for item in INDICES]
    sources = ", ".join(f"{item['name']}: {item['source']}" for item in items)
    print(f"Loaded {len(items)} indices ({sources})", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    light = OUT / "market-pulse-light.svg"
    dark = OUT / "market-pulse-dark.svg"
    light.write_text(build_svg(items, dark=False), encoding="utf-8")
    dark.write_text(build_svg(items, dark=True), encoding="utf-8")
    print(f"Wrote {light.name} and {dark.name}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - the workflow should keep the last good SVGs
        print(f"Market pulse failed: {exc}", flush=True)
        raise SystemExit(1)
