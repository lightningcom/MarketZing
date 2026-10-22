from datetime import date
from html import escape

import numpy as np
import requests
import streamlit as st
import yfinance as yf

from navigation import render_page_header


render_page_header("Markets")
MARKET_INDICES = {
    "India": [
        ("NIFTY 50", "^NSEI"),
        ("NIFTY Bank", "^NSEBANK"),
        ("NIFTY Next 50", "^NSMIDCP"),
        ("NIFTY Midcap 50", "^NSEMDCP50"),
        ("BSE SENSEX", "^BSESN"),
        ("NIFTY IT", "^CNXIT"),
        ("NIFTY Auto", "^CNXAUTO"),
        ("NIFTY Pharma", "^CNXPHARMA"),
        ("NIFTY FMCG", "^CNXFMCG"),
        ("NIFTY Metal", "^CNXMETAL"),
    ],
    "United States": [
        ("S&P 500", "^GSPC"),
        ("Dow Jones Industrial Average", "^DJI"),
        ("Nasdaq Composite", "^IXIC"),
        ("Nasdaq 100", "^NDX"),
        ("Russell 2000", "^RUT"),
        ("NYSE Composite", "^NYA"),
        ("S&P 100", "^OEX"),
        ("S&P 400 MidCap", "^MID"),
        ("S&P 600 SmallCap", "^SML"),
        ("PHLX Semiconductor", "^SOX"),
    ],
    "Europe": [
        ("EURO STOXX 50", "^STOXX50E"),
        ("STOXX Europe 600", "^STOXX"),
        ("FTSE 100", "^FTSE"),
        ("DAX", "^GDAXI"),
        ("CAC 40", "^FCHI"),
        ("IBEX 35", "^IBEX"),
        ("Swiss Market Index", "^SSMI"),
        ("AEX", "^AEX"),
        ("FTSE MIB", "FTSEMIB.MI"),
        ("OMX Stockholm 30", "^OMX"),
    ],
    "Asia Pacific": [
        ("Nikkei 225", "^N225"),
        ("Hang Seng", "^HSI"),
        ("Shanghai Composite", "000001.SS"),
        ("Shenzhen Component", "399001.SZ"),
        ("KOSPI Composite", "^KS11"),
        ("Taiwan Weighted", "^TWII"),
        ("S&P/ASX 200", "^AXJO"),
        ("Straits Times Index", "^STI"),
        ("Jakarta Composite", "^JKSE"),
        ("NIFTY 50", "^NSEI"),
    ],
}

SNAPSHOT_ASSETS = [
    ("Nifty 50", "^NSEI", "index"),
    ("Nifty Bank", "^NSEBANK", "index"),
    ("Nifty Next 50", "^NSMIDCP", "index"),
    ("Nifty 500", "^CRSLDX", "index"),
    ("Midcap 150", "^NSEMDCP150", "index"),
    ("S&P 500", "^GSPC", "index"),
    ("Gold", "GC=F", "commodity"),
    ("Silver", "SI=F", "commodity"),
    ("Brent Crude", "BZ=F", "commodity"),
    ("Copper", "HG=F", "commodity"),
    ("Rupee", "USDINR=X", "currency"),
    ("Euro", "EURINR=X", "currency"),
]

selected_market = st.session_state.get("market_selector", "India")


@st.cache_data(ttl=300, show_spinner=False)
def download_snapshot_data():
    return yf.download(
        tickers=" ".join(symbol for _, symbol, _ in SNAPSHOT_ASSETS),
        period="1y",
        interval="1d",
        group_by="ticker",
        progress=False,
        threads=True,
        auto_adjust=False,
    )


@st.cache_data(ttl=120, show_spinner=False)
def download_nse_snapshot_data():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/market-data/live-equity-market",
        }
    )
    session.get("https://www.nseindia.com/", timeout=15)

    def get_json(path, params=None):
        try:
            response = session.get(
                f"https://www.nseindia.com/api/{path}",
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            return {"error": str(error)}

    return {
        "index": get_json("equity-stockIndices", {"index": "NIFTY 50"}),
        "sectors": get_json("heatmap-index", {"type": "Sectoral Indices"}),
        "flows": get_json("fiidiiTradeReact"),
        "gainers": get_json("live-analysis-variations", {"index": "gainers"}),
        "losers": get_json("live-analysis-variations", {"index": "loosers"}),
    }


def get_api_rows(payload):
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def get_api_number(row, *keys):
    for key in keys:
        value = row.get(key)
        if value in (None, "", "-", "--"):
            continue
        try:
            return float(str(value).replace(",", "").replace("%", "").strip())
        except ValueError:
            continue
    return None


def get_api_error(payload):
    return payload.get("error") if isinstance(payload, dict) else None


def render_nse_snapshot():
    st.subheader("NSE market snapshot")
    try:
        market_data = download_nse_snapshot_data()
    except Exception as error:
        st.warning(f"Unable to connect to NSE India market APIs: {error}")
        return

    index_payload = market_data["index"]
    if get_api_error(index_payload):
        st.warning(f"NSE index data unavailable: {get_api_error(index_payload)}")
        return
    index_info = index_payload if isinstance(index_payload, dict) else {}
    index_advances = index_info.get("advances")
    index_advances = index_advances if isinstance(index_advances, dict) else {}
    constituent_rows = [
        row for row in get_api_rows(index_payload)
        if row.get("symbol") != index_info.get("name")
    ]
    changes = [
        (row, get_api_number(row, "pChange", "perChange", "percentChange"))
        for row in constituent_rows
    ]
    changes = [(row, change) for row, change in changes if change is not None]
    advances = get_api_number(index_advances, "advances")
    declines = get_api_number(index_advances, "declines")
    unchanged = get_api_number(index_advances, "unchanged")
    advances = int(advances) if advances is not None else sum(change > 0 for _, change in changes)
    declines = int(declines) if declines is not None else sum(change < 0 for _, change in changes)
    unchanged = int(unchanged) if unchanged is not None else max(len(changes) - advances - declines, 0)
    label_date = str(index_info.get("timestamp") or "latest close")
    total = advances + declines + unchanged

    breadth_column, flows_column, movers_column = st.columns([1, 1.05, 1.5], gap="large")
    with breadth_column:
        st.markdown(f"**Breadth** · {label_date}")
        if total:
            advancing_width = advances / total * 100
            index_price = get_api_number(headline, "lastPrice")
            index_price_text = f"{index_price:,.2f}" if index_price is not None else "N/A"
            st.markdown(
                f'<div style="height:8px;display:flex;overflow:hidden;border-radius:2px;'
                f'background:#8e4741;margin:8px 0">'
                f'<span style="width:{advancing_width:.1f}%;background:#4b7eaa"></span></div>'
                f'<div style="display:flex;justify-content:space-between;font-size:13px">'
                f'<span><strong>{advances}</strong> rose</span>'
                f'<span><strong>{declines}</strong> fell'
                f'{f", {unchanged} unchanged" if unchanged else ""}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("NIFTY 50 breadth data unavailable")
        index_summary = get_api_rows(index_payload)
        headline = index_summary[0] if index_summary else {}
        year_highs = sum(
            get_api_number(row, "lastPrice") is not None
            and get_api_number(row, "yearHigh") is not None
            and get_api_number(row, "lastPrice") >= get_api_number(row, "yearHigh") * 0.995
            for row, _ in changes
        )
        year_lows = sum(
            get_api_number(row, "lastPrice") is not None
            and get_api_number(row, "yearLow") is not None
            and get_api_number(row, "lastPrice") <= get_api_number(row, "yearLow") * 1.005
            for row, _ in changes
        )
        st.markdown(
            f'<div style="margin-top:12px;padding:7px 0;border-bottom:1px solid '
            f'color-mix(in srgb,currentColor 15%,transparent);font-size:13px">'
            f'52-week highs <strong style="float:right">{year_highs}</strong></div>'
            f'<div style="padding:7px 0;border-bottom:1px solid '
            f'color-mix(in srgb,currentColor 15%,transparent);font-size:13px">'
            f'52-week lows <strong style="float:right">{year_lows}</strong></div>'
            f'<div style="padding:7px 0;font-size:13px">NIFTY 50 '
            f'<strong style="float:right">{index_price_text}</strong></div>',
            unsafe_allow_html=True,
        )

    with flows_column:
        st.markdown(f"**Flows** · {label_date}")
        flows = market_data["flows"]
        if get_api_error(flows):
            st.caption(f"NSE flows unavailable: {get_api_error(flows)}")
        else:
            flow_rows = get_api_rows(flows)
            flow_rows.sort(key=lambda row: str(row.get("date", "")), reverse=True)
            latest_date = flow_rows[0].get("date") if flow_rows else None
            latest_flows = [
                row for row in flow_rows if row.get("date") == latest_date
            ]
            for row in latest_flows:
                net_value = get_api_number(row, "netValue", "net")
                category = str(row.get("category", "Investor"))
                if net_value is None:
                    continue
                color = "#73adff" if net_value >= 0 else "#e87552"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;gap:8px;'
                    f'padding:8px 0;border-bottom:1px solid '
                    f'color-mix(in srgb,currentColor 15%,transparent);font-size:13px">'
                    f'<span>{escape(category)}</span><strong style="color:{color}">'
                    f'{"+" if net_value > 0 else ""}₹{net_value:,.0f} cr</strong></div>',
                    unsafe_allow_html=True,
                )
            if not latest_flows:
                st.caption("No recent FPI/DII flow data")
            elif latest_date:
                st.caption(f"Latest available session: {latest_date}")

    with movers_column:
        st.markdown(f"**Biggest moves** · {label_date}")
        gainers = get_api_rows(market_data["gainers"])
        losers = get_api_rows(market_data["losers"])
        if get_api_error(market_data["gainers"]) or get_api_error(market_data["losers"]):
            st.caption(
                "NSE mover data unavailable: "
                f"{get_api_error(market_data['gainers']) or get_api_error(market_data['losers'])}"
            )
        elif gainers or losers:
            positive_column, negative_column = st.columns(2, gap="small")
            with positive_column:
                for row in gainers[:5]:
                    change = get_api_number(row, "pChange", "perChange", "percentChange")
                    name = str(row.get("symbol") or row.get("companyName") or "—")
                    if change is None:
                        continue
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;gap:8px;'
                        f'padding:6px 0;border-bottom:1px solid '
                        f'color-mix(in srgb,currentColor 15%,transparent);font-size:13px">'
                        f'<span>{escape(name)}</span><strong style="color:#73adff">'
                        f'{change:+.1f}%</strong></div>',
                        unsafe_allow_html=True,
                    )
            with negative_column:
                for row in losers[:5]:
                    change = get_api_number(row, "pChange", "perChange", "percentChange")
                    name = str(row.get("symbol") or row.get("companyName") or "—")
                    if change is None:
                        continue
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;gap:8px;'
                        f'padding:6px 0;border-bottom:1px solid '
                        f'color-mix(in srgb,currentColor 15%,transparent);font-size:13px">'
                        f'<span>{escape(name)}</span><strong style="color:#e87552">'
                        f'{change:+.1f}%</strong></div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("No recent NSE mover data")

    st.markdown("**Sectors today**")
    sectors = market_data["sectors"]
    if get_api_error(sectors):
        st.caption(f"NSE sector data unavailable: {get_api_error(sectors)}")
        sector_changes = []
    else:
        sector_changes = []
        for row in get_api_rows(sectors):
            name = str(row.get("index") or row.get("indexName") or "")
            change = get_api_number(row, "percentChange", "pChange", "perChange")
            if name and change is not None:
                sector_changes.append((name, change))
    if sector_changes:
        sector_changes.sort(key=lambda item: item[1], reverse=True)
        best_change = max(abs(change) for _, change in sector_changes) or 1
        left_sectors, right_sectors = st.columns(2, gap="large")
        sector_columns = (left_sectors, right_sectors)
        sector_changes = sector_changes[:20]
        split_at = (len(sector_changes) + 1) // 2
        for column, sector_group in zip(
            sector_columns,
            (sector_changes[:split_at], sector_changes[split_at:]),
        ):
            with column:
                for name, change in sector_group:
                    bar_width = abs(change) / best_change * 100
                    color = "#4b7eaa" if change >= 0 else "#b65d57"
                    st.markdown(
                        f'<div style="display:grid;grid-template-columns:1fr 1fr 54px;'
                        f'align-items:center;gap:12px;padding:5px 0;font-size:13px">'
                        f'<span>{escape(name)}</span>'
                        f'<span style="height:8px;display:flex;justify-content:'
                        f'{"flex-start" if change >= 0 else "flex-end"}">'
                        f'<span style="width:{bar_width:.1f}%;background:{color};'
                        f'border-radius:2px"></span></span>'
                        f'<strong style="text-align:right;color:{color}">{change:+.1f}%</strong>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.caption("Sector index data unavailable")
    st.caption("Source: NSE India public market-data endpoints")


def make_snapshot_sparkline(series, label, color):
    values = [float(value) for value in series.tolist() if np.isfinite(value)]
    if not values:
        return ""

    width = 180
    height = 36
    inset = 2
    low, high = min(values), max(values)
    spread = high - low or 1.0
    low -= spread * 0.1
    high += spread * 0.1
    points = [
        (
            inset + position * (width - inset * 2) / max(len(values) - 1, 1),
            height - inset - (value - low) / (high - low) * (height - inset * 2),
        )
        for position, value in enumerate(values)
    ]
    path = " ".join(
        f"{'M' if position == 0 else 'L'} {x:.2f} {y:.2f}"
        for position, (x, y) in enumerate(points)
    )
    end_x, end_y = points[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(label)} three-month trend" '
        'preserveAspectRatio="none" style="display:block;width:100%;height:36px">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-opacity=".65" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />'
        f'<circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="2.5" fill="{color}" />'
        '</svg>'
    )


def render_market_snapshot():
    try:
        market_data = download_snapshot_data()
    except Exception as error:
        st.warning(f"Market snapshot unavailable: {error}")
        return

    cards = []
    for name, symbol, asset_type in SNAPSHOT_ASSETS:
        try:
            close = market_data[symbol]["Close"].dropna().astype(float)
        except (KeyError, TypeError, IndexError):
            close = None

        if close is None or close.empty:
            daily_move = None
            ytd_move = None
            trend_svg = ""
        else:
            inverse_quote = asset_type == "currency" and name == "Rupee"
            latest = float(close.iloc[-1])
            previous = float(close.iloc[-2]) if len(close) > 1 else None
            ytd_close = close[close.index.year == date.today().year]
            year_start = float(ytd_close.iloc[0]) if not ytd_close.empty else None

            if inverse_quote:
                daily_move = (
                    (previous / latest - 1) * 100
                    if previous is not None and latest
                    else None
                )
                ytd_move = (
                    (year_start / latest - 1) * 100
                    if year_start is not None and latest
                    else None
                )
                trend = (1 / close).iloc[-63:]
            else:
                daily_move = (
                    (latest / previous - 1) * 100
                    if previous is not None and previous
                    else None
                )
                ytd_move = (
                    (latest / year_start - 1) * 100
                    if year_start is not None and year_start
                    else None
                )
                trend = close.iloc[-63:]

            color = "#73adff" if daily_move is not None and daily_move >= 0 else "#e87552"
            trend_svg = make_snapshot_sparkline(trend, name, color)

        change_class = "positive" if daily_move is not None and daily_move >= 0 else "negative"
        change_text = f"{daily_move:+.2f}%" if daily_move is not None else "N/A"
        ytd_text = f"YTD {ytd_move:+.1f}%" if ytd_move is not None else "YTD N/A"
        cards.append(
            f'<article class="market-snapshot-card" aria-label="{escape(name)}">'
            f'<div class="market-snapshot-name">{escape(name)}</div>'
            f'<div class="market-snapshot-change {change_class}">{change_text}</div>'
            f'<div class="market-snapshot-chart">{trend_svg}</div>'
            f'<div class="market-snapshot-ytd">{ytd_text}</div>'
            '</article>'
        )

    card_html = "".join(cards)
    st.markdown(
        f"""
        <style>
        .market-snapshot {{
            overflow: hidden;
            border-top: 1px solid color-mix(in srgb, currentColor 20%, transparent);
            border-bottom: 1px solid color-mix(in srgb, currentColor 20%, transparent);
        }}
        .market-snapshot-track {{
            display: flex;
            width: max-content;
            animation: market-snapshot-scroll 48s linear infinite;
        }}
        .market-snapshot-set {{
            display: flex;
            flex: 0 0 auto;
        }}
        .market-snapshot:hover .market-snapshot-track,
        .market-snapshot:focus-within .market-snapshot-track {{
            animation-play-state: paused;
        }}
        .market-snapshot-card {{
            box-sizing: border-box;
            display: flex;
            flex: 0 0 186px;
            flex-direction: column;
            justify-content: space-between;
            height: 146px;
            padding: 16px;
            border-right: 1px solid color-mix(in srgb, currentColor 16%, transparent);
        }}
        .market-snapshot-name,
        .market-snapshot-ytd {{
            overflow: hidden;
            color: color-mix(in srgb, currentColor 72%, transparent);
            font-size: 13px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .market-snapshot-change {{
            font-family: 'Newsreader', Georgia, serif;
            font-size: 38px;
            font-weight: 300;
            line-height: 1;
            white-space: nowrap;
        }}
        .market-snapshot-change.positive {{ color: #73adff; }}
        .market-snapshot-change.negative {{ color: #e87552; }}
        .market-snapshot-chart {{ height: 36px; }}
        .market-snapshot-note {{
            margin: 4px 4px 0;
            color: color-mix(in srgb, currentColor 65%, transparent);
            font-size:4px;
        }}
        @keyframes market-snapshot-scroll {{
            from {{ transform: translateX(0); }}
            to {{ transform: translateX(-50%); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .market-snapshot-track {{ animation: none; }}
            .market-snapshot {{ overflow-x: auto; }}
        }}
        </style>
        <section class="market-snapshot" role="region" aria-label="Global market snapshot">
            <div class="market-snapshot-track">
                <div class="market-snapshot-set">{card_html}</div>
                <div class="market-snapshot-set" aria-hidden="true">{card_html}</div>
            </div>
        </section>
        <p class="market-snapshot-note">
            Daily move · three-month trend · YTD change.
        </p>
        """,
        unsafe_allow_html=True,
    )


def make_sparkline_svg(series, ticker):
    chart_width = 280
    plot_left = 8
    plot_right = 272
    plot_top = 8
    plot_bottom = 82
    values = [float(value) for value in series.tolist() if np.isfinite(value)]
    if not values:
        return ""

    value_min = min(values)
    value_max = max(values)
    value_range = value_max - value_min
    if value_range == 0:
        value_range = 1
    padding = value_range * 0.12
    y_min = value_min - padding
    y_max = value_max + padding

    def chart_y(value):
        return plot_bottom - (value - y_min) / (y_max - y_min) * (plot_bottom - plot_top)

    coordinates = [
        (
            plot_left + position * (plot_right - plot_left) / max(len(values) - 1, 1),
            chart_y(value),
        )
        for position, value in enumerate(values)
    ]
    line_path = " ".join(
        f"{'M' if position == 0 else 'L'} {x:.2f} {y:.2f}"
        for position, (x, y) in enumerate(coordinates)
    )
    hover_points = []
    for position, ((x, y), value) in enumerate(zip(coordinates, values)):
        timestamp = series.index[position]
        time_label = timestamp.strftime("%H:%M") if hasattr(timestamp, "strftime") else str(timestamp)
        tooltip_x = min(max(x - 38, plot_left), plot_right - 76)
        hover_points.append(
            f'<g class="hover-point" tabindex="0" role="img" '
            f'aria-label="{time_label}, {value:+.2f}%">'
            f'<line class="crosshair" x1="{x:.2f}" y1="{plot_top}" '
            f'x2="{x:.2f}" y2="{plot_bottom}" />'
            f'<circle class="hover-marker" cx="{x:.2f}" cy="{y:.2f}" r="3.5" />'
            f'<g class="hover-detail">'
            f'<rect x="{tooltip_x:.2f}" y="{plot_top + 1}" width="76" height="16" rx="2" />'
            f'<text x="{tooltip_x + 38:.2f}" y="{plot_top + 12}" '
            f'text-anchor="middle">{time_label} · {value:+.2f}%</text>'
            f'</g>'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="transparent" '
            'pointer-events="all" />'
            '</g>'
        )
    grid_lines = "".join(
        f'<line x1="{plot_left}" y1="{y}" x2="{plot_right}" y2="{y}" '
        'stroke="currentColor" stroke-opacity="0.12" stroke-width="1" />'
        for y in (plot_top, (plot_top + plot_bottom) / 2, plot_bottom)
    )
    if y_min <= 0 <= y_max:
        zero_y = chart_y(0)
        grid_lines += (
            f'<line x1="{plot_left}" y1="{zero_y:.2f}" x2="{plot_right}" '
            f'y2="{zero_y:.2f}" stroke="currentColor" stroke-opacity="0.28" '
            'stroke-width="1" />'
        )

    label_positions = (0, len(series) // 2, len(series) - 1)
    time_labels = []
    for position, anchor in zip(label_positions, ("start", "middle", "end")):
        timestamp = series.index[position]
        label = timestamp.strftime("%H:%M") if hasattr(timestamp, "strftime") else str(timestamp)
        x = plot_left + position * (plot_right - plot_left) / max(len(series) - 1, 1)
        time_labels.append(
            f'<text x="{x:.2f}" y="108" text-anchor="{anchor}" '
            f'fill="currentColor" fill-opacity="0.65" font-size="10">{label}</text>'
        )

    last_x, last_y = coordinates[-1]
    return (
        f'<svg viewBox="0 0 {chart_width} 120" role="img" '
        f'aria-label="{ticker} intraday percentage change" '
        'preserveAspectRatio="none" style="display:block;width:100%;height:145px;overflow:visible">'
        '<style>'
        '.hover-point{cursor:crosshair;outline:none}'
        '.hover-point .crosshair,.hover-point .hover-marker,.hover-point .hover-detail{opacity:0}'
        '.hover-point:hover .crosshair,.hover-point:focus .crosshair{opacity:.55}'
        '.hover-point:hover .hover-marker,.hover-point:focus .hover-marker{opacity:1}'
        '.hover-point:hover .hover-detail,.hover-point:focus .hover-detail{opacity:1}'
        '.crosshair{stroke:currentColor;stroke-width:1;stroke-dasharray:2 2}'
        '.hover-marker{fill:currentColor;stroke:Canvas;stroke-width:1.5}'
        '.hover-detail rect{fill:Canvas;stroke:currentColor;stroke-opacity:.35}'
        '.hover-detail text{fill:CanvasText;font:9px "DM Sans",sans-serif}'
        '</style>'
        f'{grid_lines}'
        f'<path d="{line_path}" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />'
        f'{"".join(hover_points)}'
        f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" r="2.5" fill="currentColor" />'
        f'{"".join(time_labels)}'
        '</svg>'
    )


@st.fragment(run_every="60s")
def render_live_charts(selected_market):
    selected_market = st.session_state.get("market_selector", selected_market)
    indices = MARKET_INDICES[selected_market]
    symbols = [symbol for _, symbol in indices]

    try:
        market_data = yf.download(
            tickers=" ".join(symbols),
            period="1d",
            interval="1m",
            group_by="ticker",
            progress=False,
            threads=True,
        )
    except Exception as error:
        st.error(f"Unable to load live market data: {error}")
        return

    index_moves = []
    for row_start in (0, 5):
        columns = st.columns(5, gap="small")
        for (index_name, symbol), column in zip(indices[row_start:row_start + 5], columns):
            with column:
                try:
                    ticker_data = market_data[symbol]
                    close = ticker_data["Close"].dropna()
                except (KeyError, TypeError):
                    st.markdown(f"**{index_name}**")
                    st.caption("No recent data")
                    continue

                if close.empty:
                    st.markdown(f"**{index_name}**")
                    st.caption("No recent data")
                    continue

                session_change = (close / close.iloc[0] - 1) * 100
                latest_change = float(session_change.iloc[-1])
                index_moves.append((index_name, latest_change))
                column.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"align-items:center;gap:4px;white-space:nowrap;font-size:13px;"
                    f"padding:8px 0 2px'>"
                    f"<span style='flex:1;min-width:0;overflow:hidden;"
                    f"text-overflow:ellipsis'>{index_name}</span><strong style='flex:none'>"
                    f"{latest_change:+.2f}%</strong></div>",
                    unsafe_allow_html=True,
                )
                column.markdown(
                    make_sparkline_svg(session_change, index_name),
                    unsafe_allow_html=True,
                )

    if index_moves:
        advancing = sum(change > 0 for _, change in index_moves)
        average_change = np.mean([change for _, change in index_moves])
        leader_name, leader_change = max(index_moves, key=lambda item: item[1])
        laggard_name, laggard_change = min(index_moves, key=lambda item: item[1])
    else:
        advancing = 0
        average_change = None
        leader_name, leader_change = "No data", None
        laggard_name, laggard_change = "No data", None

    summary_column, market_column = st.columns([8, 1])
    with summary_column:
        pulse_items = [
            ("ADVANCING", f"{advancing} / {len(indices)}"),
            (
                "AVERAGE MOVE",
                f"{average_change:+.2f}%" if average_change is not None else "N/A",
            ),
            (
                "LEADING",
                f"{leader_name} {leader_change:+.2f}%" if leader_change is not None else leader_name,
            ),
            (
                "LAGGING",
                f"{laggard_name} {laggard_change:+.2f}%" if laggard_change is not None else laggard_name,
            ),
        ]
        pulse_items_html = "".join(
            f'<div style="display:flex;align-items:center;justify-content:flex-start;'
            f'gap:14px;min-width:0;white-space:nowrap">'
            f'<span style="font-size:12px;opacity:.65;flex:none">{label}</span>'
            f'<strong style="min-width:0;overflow:hidden;text-overflow:ellipsis">{value}</strong></div>'
            for label, value in pulse_items
        )
        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));'
            f'align-items:center;gap:14px;width:100%;min-width:0;min-height:40px">'
            f'{pulse_items_html}</div>',
            unsafe_allow_html=True,
        )

    with market_column:
        st.selectbox(
            "Market",
            list(MARKET_INDICES),
            key="market_selector",
            label_visibility="collapsed",
        )


render_live_charts(selected_market)
render_market_snapshot()
render_nse_snapshot()

st.divider()
