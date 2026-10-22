import csv
import re
from datetime import date, datetime, timedelta
from html import escape
from io import StringIO

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
    ("Midcap 150", "NIFTYMIDCAP150.NS", "index"),
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
    try:
        homepage = session.get(
            "https://www.nseindia.com/market-data/live-equity-market",
            timeout=15,
        )
        homepage.raise_for_status()
    except requests.RequestException as error:
        return {"breadth": {"error": f"NSE website request failed: {error}"}}

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
        "breadth": get_json("live-analysis-advance", {"index": "ALL"}),
        "week52_high": get_json("live-analysis-52Week", {"index": "high"}),
        "week52_low": get_json("live-analysis-52Week", {"index": "low"}),
        "indices": get_json("allIndices"),
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


def render_section_rule():
    st.markdown(
        '<hr style="border:0;border-top:1px solid '
        'color-mix(in srgb,currentColor 18%,transparent);margin:18px 0">',
        unsafe_allow_html=True,
    )


def get_nse_movers(payload, direction):
    mover_groups = ("allSec", "FOSec", "NIFTY", "BANKNIFTY", "NIFTYNEXT50")
    rows_by_symbol = {}
    for group in mover_groups:
        for row in get_api_rows(payload.get(group, {})):
            symbol = row.get("symbol")
            change = get_api_number(
                row, "pchange", "pChange", "perChange", "percentChange"
            )
            if symbol and change is not None and change * direction > 0:
                rows_by_symbol[symbol] = (row, change)

    return sorted(
        rows_by_symbol.values(),
        key=lambda item: item[1],
        reverse=direction > 0,
    )[:30]


def normalize_nse_index_name(value):
    normalized = "".join(character for character in str(value or "").upper() if character.isalnum())
    return normalized.replace("NIFTYSMLCAP", "NIFTYSMALLCAP")


@st.cache_data(ttl=86400, show_spinner=False)
def download_nse_index_archive(date_key):
    archive_date = datetime.strptime(date_key, "%Y-%m-%d").date()
    url = (
        "https://nsearchives.nseindia.com/content/indices/ind_close_all_"
        f"{archive_date:%d%m%Y}.csv"
    )
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.nseindia.com/",
            },
            timeout=12,
        )
        if response.status_code == 404:
            return {}, None
        response.raise_for_status()
        reader = csv.DictReader(StringIO(response.text))
        if not reader.fieldnames or not {
            "Index Name",
            "Closing Index Value",
        }.issubset(reader.fieldnames):
            return {}, f"Unexpected NSE archive format for {date_key}."

        closes = {}
        for row in reader:
            name = normalize_nse_index_name(row.get("Index Name"))
            close = get_api_number(row, "Closing Index Value")
            if name and close is not None:
                closes[name] = close
        return closes, None
    except requests.RequestException as error:
        return {}, f"NSE historical data request failed for {date_key}: {error}"


def parse_nse_as_of(as_of):
    if isinstance(as_of, datetime):
        return as_of.date()
    if isinstance(as_of, date):
        return as_of
    if as_of:
        for date_format in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
            try:
                return datetime.strptime(str(as_of), date_format).date()
            except ValueError:
                continue
    return date.today()


def get_nse_historical_close(index, target_date):
    names = (
        index.get("index"),
        index.get("indexSymbol"),
        index.get("indexName"),
        index.get("name"),
    )
    normalized_names = {
        normalize_nse_index_name(name) for name in names if name
    }
    request_errors = []
    for days_back in range(8):
        archive_date = target_date - timedelta(days=days_back)
        closes, error = download_nse_index_archive(archive_date.isoformat())
        if error:
            request_errors.append(error)
        if closes:
            for name in normalized_names:
                if name in closes:
                    return closes[name], None
    return None, request_errors[0] if request_errors else None


@st.cache_data(ttl=86400, show_spinner=False)
def download_nse_index_sparkline(chart_url):
    try:
        response = requests.get(
            chart_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.nseindia.com/",
            },
            timeout=12,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""

    source_path = re.search(
        r'<path d="([^"]+)" fill="#[0-9a-fA-F]{6}"',
        response.text,
    )
    if not source_path:
        return ""

    area_path = source_path.group(1)
    coordinates = list(re.finditer(r"(-?[\d.]+),(-?[\d.]+)", area_path))
    if len(coordinates) < 2:
        return ""
    previous_x = float(coordinates[0].group(1))
    line_end = None
    endpoint_x, endpoint_y = coordinates[0].groups()
    for coordinate in coordinates[1:]:
        current_x = float(coordinate.group(1))
        if current_x < previous_x:
            line_end = coordinate.start()
            break
        previous_x = current_x
        endpoint_x, endpoint_y = coordinate.groups()
    if line_end is None:
        return ""

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 36" '
        'preserveAspectRatio="none" role="img" '
        'style="display:block;width:100%;height:100%">'
        f'<path d="{area_path[:line_end]}" fill="none" stroke="#9a9a9a" '
        'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{endpoint_x}" cy="{endpoint_y}" r="1.7" fill="#d9534f"/>'
        '</svg>'
    )


def get_nse_historical_series(index, end_date, weeks=52):
    values = []
    errors = []
    for week in range(weeks, -1, -1):
        target_date = end_date - timedelta(days=week * 7)
        close, error = get_nse_historical_close(index, target_date)
        if close is not None:
            values.append(close)
        elif error:
            errors.append(error)
    return values, errors[0] if errors else None


def make_nse_sparkline_svg(values):
    if len(values) < 2:
        return ""

    width, height, inset = 80, 36, 3
    low, high = min(values), max(values)
    spread = high - low or 1
    padding = spread * 0.08
    low -= padding
    high += padding
    points = [
        (
            inset + position * (width - inset * 2) / (len(values) - 1),
            height - inset - (value - low) / (high - low) * (height - inset * 2),
        )
        for position, value in enumerate(values)
    ]
    line_path = " ".join(
        f"{'M' if position == 0 else 'L'} {x:.2f} {y:.2f}"
        for position, (x, y) in enumerate(points)
    )
    endpoint_x, endpoint_y = points[-1]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="none" role="img" '
        'style="display:block;width:100%;height:100%">'
        f'<path d="{line_path}" fill="none" stroke="#9a9a9a" '
        'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{endpoint_x:.2f}" cy="{endpoint_y:.2f}" '
        'r="1.7" fill="#d9534f"/>'
        '</svg>'
    )


def render_index_performance_table(index_rows, title, as_of=None):
    if not index_rows:
        st.caption(f"No NSE index data available for {title.lower()}.")
        return

    latest_date = parse_nse_as_of(as_of)
    st.markdown(f"### {escape(title)}")
    st.markdown(
        f'<p class="nse-index-description">NSE index performance'
        f' through {escape(str(as_of or latest_date))}. '
        'Missing periods are calculated from NSE historical closing values.</p>',
        unsafe_allow_html=True,
    )

    column_template = (
        "minmax(0,1.65fr) minmax(0,.8fr) repeat(8,minmax(0,.72fr)) "
        "minmax(0,.8fr) minmax(0,.8fr) minmax(0,.9fr)"
    )
    headers = (
        "Index", "52W", "1D", "1W", "1M", "3M", "YTD", "1Y",
        "3Y", "5Y", "Off high", "Trend", "Mom.",
    )
    header = (
        f'<div class="nse-index-row nse-index-header" '
        f'style="grid-template-columns:{column_template}">'
        f'{"".join(f"<span>{label}</span>" for label in headers)}</div>'
    )
    rows = []
    periods = (
        ("1D", ("percentChange", "pChange", "perChange"), (), None),
        ("1W", ("perChange7d",), ("oneWeekAgoVal",), timedelta(days=7)),
        ("1M", ("perChange30d",), ("oneMonthAgoVal",), timedelta(days=30)),
        ("3M", ("perChange90d", "perChange3m", "threeMonthChange"), (), timedelta(days=90)),
        (
            "YTD",
            ("perChangeYtd", "perChangeYTD", "ytdChange", "ytdPercentChange"),
            (),
            None,
        ),
        ("1Y", ("perChange365d", "perChange1y"), ("oneYearAgoVal",), timedelta(days=365)),
        ("3Y", ("perChange3y", "perChange1095d"), (), timedelta(days=365 * 3)),
        ("5Y", ("perChange5y", "perChange1825d"), (), timedelta(days=365 * 5)),
    )

    performance_by_index = []
    historical_errors = set()
    for index in index_rows:
        last = get_api_number(index, "last", "current", "lastPrice", "indexValue")
        changes = []
        for label, direct_fields, baseline_fields, date_offset in periods:
            change = get_api_number(index, *direct_fields)
            if change is None and baseline_fields and last not in (None, 0):
                baseline = get_api_number(index, *baseline_fields)
                if baseline not in (None, 0):
                    change = (last / baseline - 1) * 100
            target_date = (
                date(latest_date.year, 1, 1)
                if label == "YTD"
                else latest_date - date_offset
                if date_offset is not None
                else None
            )
            if change is None and target_date is not None and last not in (None, 0):
                historical_close, error = get_nse_historical_close(index, target_date)
                if error:
                    historical_errors.add(error)
                if historical_close not in (None, 0):
                    change = (last / historical_close - 1) * 100
            changes.append(change)
        one_year_change = changes[5]
        performance_by_index.append((index, last, changes, one_year_change))

    valid_one_year_returns = sorted(
        (item[3] for item in performance_by_index if item[3] is not None),
        reverse=True,
    )
    rows = []
    for index, last, changes, one_year_change in performance_by_index:
        period_cells = []
        for change in changes:
            if change is None:
                period_cells.append('<span class="nse-index-na">—</span>')
                continue
            change_class = "positive" if change >= 0 else "negative"
            intensity = min(abs(change), 8) / 8
            period_cells.append(
                f'<span class="nse-index-tile {change_class}" '
                f'style="--move-alpha:{intensity * 16:.1f}%">'
                f'{change:+.1f}%</span>'
            )

        year_high = get_api_number(index, "yearHigh", "yrHigh")
        off_high = (
            (last / year_high - 1) * 100
            if last is not None and year_high not in (None, 0)
            else None
        )
        if off_high is None:
            off_high_cell = '<span class="nse-index-na">—</span>'
        else:
            off_high_class = "positive" if off_high >= 0 else "negative"
            off_high_cell = (
                f'<span class="nse-index-tile {off_high_class}">'
                f'{off_high:+.1f}%</span>'
            )
        chart_url = index.get("chart365dPath")
        sparkline_svg = (
            download_nse_index_sparkline(chart_url) if chart_url else ""
        )
        if not sparkline_svg:
            sparkline_values, sparkline_error = get_nse_historical_series(
                index,
                latest_date,
            )
            if sparkline_error:
                historical_errors.add(sparkline_error)
            sparkline_svg = make_nse_sparkline_svg(sparkline_values)
        if sparkline_svg:
            sparkline = (
                f'<span class="nse-index-sparkline" '
                f'aria-label="{escape(str(index.get("index", "Index")))} 52-week sparkline">'
                f'{sparkline_svg}</span>'
            )
        else:
            sparkline = '<span class="nse-index-na">—</span>'
        trend_label = index.get("trend") or index.get("trendStatus")
        trend = (
            f'<span>{escape(str(trend_label))}</span>'
            if trend_label
            else (
                f'<span class="nse-index-trend {"positive" if one_year_change >= 0 else "negative"}">'
                f'{"Up" if one_year_change >= 0 else "Down"} 1Y</span>'
                if one_year_change is not None
                else '<span class="nse-index-na">—</span>'
            )
        )
        momentum_value = get_api_number(index, "momentum", "momentum12m")
        momentum_rank = get_api_number(index, "momentumRank")
        if momentum_value is not None:
            momentum = f'<span>{momentum_value:+.1f}%</span>'
        elif momentum_rank is not None:
            momentum = f'<span>Rank {momentum_rank:g}</span>'
        elif one_year_change is not None:
            momentum_rank = valid_one_year_returns.index(one_year_change) + 1
            momentum = (
                f'<span title="1Y return: {one_year_change:+.1f}%">'
                f'{momentum_rank}/{len(valid_one_year_returns)}</span>'
            )
        else:
            momentum = '<span class="nse-index-na">—</span>'
        name = escape(
            str(index.get("index", index.get("indexSymbol", index.get("name", "Index"))))
        )
        rows.append(
            f'<div class="nse-index-row" role="row" '
            f'style="grid-template-columns:{column_template}">'
            f'<span class="nse-index-name">{name}</span>{sparkline}'
            f'{"".join(period_cells)}{off_high_cell}{trend}{momentum}</div>'
        )
    if historical_errors:
        st.caption(
            "Some NSE historical archives could not be retrieved; affected "
            f"periods remain unavailable. {escape(next(iter(historical_errors)))}"
        )

    st.markdown(
        f"""
        <style>
        .nse-index-table {{ width:100%; }}
        .nse-index-row {{
            display:grid;
            align-items:center;
            gap:0;
            width:100%;
            min-height:35px;
            padding:0;
            margin:0;
            box-sizing:border-box;
            border-bottom:1px solid color-mix(in srgb,currentColor 13%,transparent);
            font-size:10px;
        }}
        .nse-index-header {{
            color:color-mix(in srgb,currentColor 65%,transparent);
            border-bottom-color:color-mix(in srgb,currentColor 25%,transparent);
            font-size:9px;
            font-weight:600;
        }}
        .nse-index-row > * {{
            min-width:0;
            height:100%;
            box-sizing:border-box;
            border-right:1px solid color-mix(in srgb,currentColor 12%,transparent);
        }}
        .nse-index-row > *:last-child {{ border-right:0; }}
        .nse-index-header > * {{ text-align:center; }}
        .nse-index-row > :not(.nse-index-name):not(.nse-index-sparkline) {{
            display:flex;
            align-items:center;
            justify-content:center;
            text-align:center;
        }}
        .nse-index-sparkline {{
            display:flex;
            align-items:center;
            justify-content:center;
            padding:0;
        }}
        .nse-index-sparkline svg {{
            display:block;
            width:100%;
            max-width:72px;
            height:23px;
            object-fit:fill;
        }}
        .nse-index-name {{
            overflow:hidden;
            text-overflow:ellipsis;
            white-space:nowrap;
            font-weight:600;
            padding:0;
            display:flex;
            align-items:center;
        }}
        .nse-index-tile {{
            box-sizing:border-box;
            display:flex;
            align-items:center;
            justify-content:center;
            overflow:hidden;
            padding:0;
            margin:0;
            border:0;
            border-radius:0;
            text-align:center;
            white-space:nowrap;
        }}
        .nse-index-tile.positive {{
            color:#52b879;
            background:color-mix(in srgb,#52b879 var(--move-alpha),transparent);
        }}
        .nse-index-tile.negative {{
            color:#e87552;
            background:color-mix(in srgb,#e87552 var(--move-alpha),transparent);
        }}
        .nse-index-na {{
            opacity:.55;
            text-align:center;
            display:flex;
            align-items:center;
            justify-content:center;
        }}
        .nse-index-trend {{
            overflow:hidden;
            text-overflow:ellipsis;
            white-space:nowrap;
        }}
        .nse-index-trend.positive {{ color:#52b879; }}
        .nse-index-trend.negative {{ color:#e87552;         }}
        @media (max-width:1100px) {{
            .nse-index-row {{ gap:0;font-size:9px; }}
            .nse-index-header {{ font-size:8px; }}
        }}
        </style>
        <div class="nse-index-table" role="table" aria-label="{escape(title, quote=True)}">
            {header}{"".join(rows)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_broad_market_snapshot(indices_payload):
    indices = get_api_rows(indices_payload)
    if get_api_error(indices_payload):
        st.warning(f"NSE index performance unavailable: {get_api_error(indices_payload)}")
        return

    broad_indices = [
        row for row in indices
        if row.get("key") == "BROAD MARKET INDICES"
    ]
    nifty_50 = next(
        (
            row for row in indices
            if row.get("index") == "NIFTY 50"
            or row.get("indexSymbol") == "NIFTY 50"
        ),
        None,
    )
    if nifty_50 is not None and all(
        row.get("index") != nifty_50.get("index") for row in broad_indices
    ):
        broad_indices.insert(0, nifty_50)

    render_index_performance_table(
        broad_indices,
        "How did the broad market do?",
        as_of=indices_payload.get("timestamp") if isinstance(indices_payload, dict) else None,
    )


def render_nse_snapshot():
    st.subheader("NSE market snapshot")
    market_data = download_nse_snapshot_data()

    breadth_payload = market_data["breadth"]
    if get_api_error(breadth_payload):
        st.warning(f"NSE breadth data unavailable: {get_api_error(breadth_payload)}")
        return

    advance_data = breadth_payload.get("advance", {})
    advance_data = advance_data if isinstance(advance_data, dict) else {}
    breadth_counts = advance_data.get("count", {})
    breadth_counts = breadth_counts if isinstance(breadth_counts, dict) else {}
    advances = get_api_number(breadth_counts, "Advances", "advances")
    declines = get_api_number(breadth_counts, "Declines", "declines")
    unchanged = get_api_number(breadth_counts, "Unchange", "Unchanged", "unchanged")
    breadth_available = advances is not None and declines is not None and unchanged is not None
    advances = int(advances) if advances is not None else 0
    declines = int(declines) if declines is not None else 0
    unchanged = int(unchanged) if unchanged is not None else 0
    breadth_date = str(breadth_payload.get("timestamp") or "latest available")
    total = advances + declines + unchanged

    breadth_column, flows_column = st.columns([1, 1.05], gap="large")
    with breadth_column:
        st.markdown(f"**Breadth** · {escape(breadth_date)}")
        if breadth_available and total:
            advancing_width = advances / total * 100
            st.markdown(
                f'<div style="height:8px;display:flex;overflow:hidden;border-radius:2px;'
                f'background:#8e4741;margin:8px 0">'
                f'<span style="width:{advancing_width:.1f}%;background:#52b879"></span></div>'
                f'<div style="display:flex;justify-content:space-between;font-size:13px">'
                f'<span><strong>{advances}</strong> rose</span>'
                f'<span><strong>{declines}</strong> fell'
                f'{f", {unchanged} unchanged" if unchanged else ""}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("NSE breadth data unavailable")

        high_data = market_data["week52_high"]
        low_data = market_data["week52_low"]
        high_rows = (
            high_data.get("dataLtpGreater20", []) + high_data.get("dataLtpLess20", [])
            if not get_api_error(high_data)
            else None
        )
        low_rows = (
            low_data.get("dataLtpGreater20", []) + low_data.get("dataLtpLess20", [])
            if not get_api_error(low_data)
            else None
        )
        year_highs = str(len(high_rows)) if isinstance(high_rows, list) else "N/A"
        year_lows = str(len(low_rows)) if isinstance(low_rows, list) else "N/A"

        indices_payload = market_data["indices"]
        all_indices = get_api_rows(indices_payload)
        nifty = next(
            (
                row for row in all_indices
                if row.get("index") == "NIFTY 50" or row.get("indexSymbol") == "NIFTY 50"
            ),
            {},
        )
        index_price = get_api_number(nifty, "last", "lastPrice", "indexValue")
        index_price_text = f"{index_price:,.2f}" if index_price is not None else "N/A"

        st.markdown(
            f'<div style="margin-top:12px;padding:7px 0;font-size:13px">'
            f'New 52-week highs <strong style="float:right">{year_highs}</strong></div>'
            f'<div style="padding:7px 0;font-size:13px">'
            f'New 52-week lows <strong style="float:right">{year_lows}</strong></div>'
            f'<div style="padding:7px 0;font-size:13px">NIFTY 50 '
            f'<strong style="float:right">{index_price_text}</strong></div>',
            unsafe_allow_html=True,
        )
        if get_api_error(high_data) or get_api_error(low_data):
            st.caption(
                "NSE 52-week data unavailable: "
                f"{get_api_error(high_data) or get_api_error(low_data)}"
            )
        if get_api_error(indices_payload):
            st.caption(f"NSE index level unavailable: {get_api_error(indices_payload)}")

    with flows_column:
        flows = market_data["flows"]
        if get_api_error(flows):
            st.markdown("**Flows**")
            st.caption(f"NSE flows unavailable: {get_api_error(flows)}")
        else:
            flow_rows = get_api_rows(flows)
            dated_flows = []
            for row in flow_rows:
                raw_date = str(row.get("date", ""))
                try:
                    parsed_date = datetime.strptime(raw_date, "%d-%b-%Y")
                except ValueError:
                    continue
                dated_flows.append((parsed_date, raw_date, row))
            latest_date = max(
                dated_flows,
                key=lambda item: item[0],
                default=(None, None, None),
            )[1]
            latest_flows = [
                row for _, row_date, row in dated_flows if row_date == latest_date
            ]
            st.markdown(f"**Flows** · {escape(latest_date or 'latest available')}")
            for row in latest_flows:
                net_value = get_api_number(row, "netValue", "net")
                category = escape(str(row.get("category", "Investor")))
                if net_value is None:
                    continue
                color = "#52b879" if net_value >= 0 else "#e87552"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;gap:8px;'
                    f'padding:8px 0;font-size:13px">'
                    f'<span>{escape(category)}</span><strong style="color:{color}">'
                    f'{"+" if net_value > 0 else ""}₹{net_value:,.0f} cr</strong></div>',
                    unsafe_allow_html=True,
                )
            if not latest_flows:
                st.caption("No recent FPI/DII flow data")

    render_section_rule()
    st.markdown("### Sectors today")
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
        split_at = (len(sector_changes) + 1) // 2
        for column, sector_group in zip(
            sector_columns,
            (sector_changes[:split_at], sector_changes[split_at:]),
        ):
            with column:
                for name, change in sector_group:
                    bar_width = abs(change) / best_change * 100
                    color = "#52b879" if change >= 0 else "#b65d57"
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

    render_section_rule()
    st.markdown("### Biggest moves")
    gainers_payload = market_data["gainers"]
    losers_payload = market_data["losers"]
    mover_error = get_api_error(gainers_payload) or get_api_error(losers_payload)
    gainers = get_nse_movers(gainers_payload, 1)
    losers = get_nse_movers(losers_payload, -1)
    if mover_error:
        st.caption(f"NSE mover data unavailable: {mover_error}")
    elif gainers or losers:
        positive_column, negative_column = st.columns(2, gap="large")
        with positive_column:
            st.markdown("**Positive moves**")
            positive_rows = []
            positive_rows = gainers
            for row, change in positive_rows:
                name = escape(str(row.get("symbol") or row.get("companyName") or "—"))
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;gap:8px;'
                    f'padding:6px 0;font-size:13px">'
                    f'<span>{name}</span><strong style="color:#52b879">'
                    f'{change:+.1f}%</strong></div>',
                    unsafe_allow_html=True,
                )
            if not positive_rows:
                st.caption("No positive NSE movers")
        with negative_column:
            st.markdown("**Negative moves**")
            negative_rows = []
            negative_rows = losers
            for row, change in negative_rows:
                name = escape(str(row.get("symbol") or row.get("companyName") or "—"))
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;gap:8px;'
                    f'padding:6px 0;font-size:13px">'
                    f'<span>{name}</span><strong style="color:#e87552">'
                    f'{change:+.1f}%</strong></div>',
                    unsafe_allow_html=True,
                )
            if not negative_rows:
                st.caption("No negative NSE movers")
    else:
        st.caption("No recent NSE mover data")

    render_section_rule()
    render_broad_market_snapshot(market_data["indices"])
    render_section_rule()
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
    area_path = (
        f"M {points[0][0]:.2f} {height - inset} "
        f"{path[2:]} L {points[-1][0]:.2f} {height - inset} Z"
    )
    end_x, end_y = points[-1]
    positive = color == "#52b879"
    line_color = color if positive else "#a4a7ab"
    area = (
        f'<path d="{area_path}" fill="#52b879" fill-opacity=".7" stroke="none" />'
        if positive
        else ""
    )
    endpoint = "#52b879" if positive else "#d9534f"
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(label)} three-month trend" '
        'preserveAspectRatio="none" style="display:block;width:100%;height:36px">'
        f'<line x1="{inset}" y1="{height - inset}" x2="{width - inset}" '
        f'y2="{height - inset}" stroke="#8e9399" stroke-opacity=".35" />'
        f'<line x1="{width - inset}" y1="{inset}" x2="{width - inset}" '
        f'y2="{height - inset}" stroke="#8e9399" stroke-opacity=".35" />'
        f'{area}'
        f'<path d="{path}" fill="none" stroke="{line_color}" stroke-opacity=".8" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />'
        f'<circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="2.5" fill="{endpoint}" />'
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

            color = "#52b879" if daily_move is not None and daily_move >= 0 else "#e87552"
            trend_svg = make_snapshot_sparkline(trend, name, color)

        change_class = (
            "neutral"
            if daily_move is None
            else "positive" if daily_move >= 0 else "negative"
        )
        change_text = f"{daily_move:+.2f}%" if daily_move is not None else "N/A"
        ytd_text = f"YTD {ytd_move:+.1f}%" if ytd_move is not None else "YTD N/A"
        cards.append(
            f'<article class="market-snapshot-card {change_class}" aria-label="{escape(name)}">'
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
            margin-right: 8px;
            padding: 14px;
            border: 0;
            border-radius: 6px;
            background: color-mix(in srgb, var(--tile-color) 7%, transparent);
        }}
        .market-snapshot-card.positive {{ --tile-color:#52b879; }}
        .market-snapshot-card.negative {{ --tile-color:#e87552; }}
        .market-snapshot-card.neutral {{ --tile-color:#8b9099; }}
        .market-snapshot-card .market-snapshot-name,
        .market-snapshot-card .market-snapshot-ytd {{
            color: color-mix(in srgb,currentColor 72%,transparent);
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
        .market-snapshot-change.positive {{ color: #52b879; }}
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
render_section_rule()
render_nse_snapshot()
