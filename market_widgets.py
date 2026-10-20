from __future__ import annotations

import math

import pandas as pd
import streamlit as st
import yfinance as yf


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


@st.cache_data(ttl=60, show_spinner=False)
def download_index_data(market_name: str) -> pd.DataFrame:
    symbols = [symbol for _, symbol in MARKET_INDICES[market_name]]
    return yf.download(
        tickers=" ".join(symbols),
        period="1d",
        interval="5m",
        group_by="ticker",
        progress=False,
        threads=True,
    )


def get_close_series(market_data: pd.DataFrame, symbol: str) -> pd.Series:
    try:
        ticker_frame = market_data[symbol]
        close = ticker_frame["Close"].dropna()
    except (KeyError, TypeError, IndexError):
        return pd.Series(dtype="float64")

    return close.astype(float)


def make_index_sparkline_svg(series: pd.Series, label: str) -> str:
    values = [float(value) for value in series.tolist() if math.isfinite(float(value))]
    if not values:
        return ""

    width = 260
    height = 42
    inset = 3
    low = min(values)
    high = max(values)
    spread = high - low or 1.0
    padding = spread * 0.1
    low -= padding
    high += padding
    points = []
    for position, value in enumerate(values):
        x = inset + position * (width - inset * 2) / max(len(values) - 1, 1)
        y = height - inset - (value - low) / (high - low) * (height - inset * 2)
        points.append((x, y))

    path = " ".join(
        f"{'M' if position == 0 else 'L'} {x:.2f} {y:.2f}"
        for position, (x, y) in enumerate(points)
    )
    point_targets = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="transparent" '
        f'pointer-events="all"><title>{timestamp.strftime("%H:%M") if hasattr(timestamp, "strftime") else timestamp}: '
        f'{value:,.2f}</title></circle>'
        for (x, y), timestamp, value in zip(points, series.index, values)
    )
    end_x, end_y = points[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{label} intraday index trend" '
        'preserveAspectRatio="none" style="display:block;width:100%;height:42px">'
        f'<line x1="{inset}" y1="{height / 2}" x2="{width - inset}" '
        f'y2="{height / 2}" stroke="currentColor" stroke-opacity=".12" />'
        f'<path d="{path}" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round" />'
        f'{point_targets}'
        f'<circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="2" fill="currentColor" />'
        '</svg>'
    )


def render_index_rail() -> None:
    market_name = st.selectbox(
        "Index market",
        list(MARKET_INDICES),
        key="index_rail_market",
        label_visibility="collapsed",
    )
    st.markdown("#### Index pulse")

    try:
        market_data = download_index_data(market_name)
    except Exception as error:
        st.warning(f"Index data unavailable: {error}")
        return

    for index_name, symbol in MARKET_INDICES[market_name]:
        close = get_close_series(market_data, symbol)
        if close.empty:
            st.markdown(f"**{index_name}**")
            st.caption("No recent data")
            continue

        move = (close.iloc[-1] / close.iloc[0] - 1) * 100 if close.iloc[0] else 0.0
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;gap:6px;'
            f'align-items:baseline;white-space:nowrap;overflow:hidden">'
            f'<span style="overflow:hidden;text-overflow:ellipsis">{index_name}</span>'
            f'<strong style="flex:none">{move:+.2f}%</strong></div>',
            unsafe_allow_html=True,
        )
        st.markdown(make_index_sparkline_svg(close, index_name), unsafe_allow_html=True)
