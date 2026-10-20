import numpy as np
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

selected_market = st.session_state.get("market_selector", "India")
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


@st.fragment(run_every="20s")
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
            f'<span style="font-size:11px;opacity:.65;flex:none">{label}</span>'
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

st.divider()
