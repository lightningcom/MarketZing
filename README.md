# MarketZing

MarketZing is a multipage Streamlit market dashboard. Its Markets page displays intraday percentage moves and sparklines for major indices across India, the United States, Europe, and Asia Pacific. Market data is retrieved through `yfinance`.

The other sections are currently navigation and layout scaffolds. Their data sources and analytics have not yet been implemented.

## Features

- Intraday index moves and sparklines for four regions
- Market breadth summary: advancing indices, average move, leader, and laggard
- Automatic chart refresh while the Markets page is open
- NSE market snapshot with breadth, investor flows, movers, and sector performance
- Reusable NSE index performance table with sparklines and value-tinted period returns
- Shared page header and navigation across the app
- Multipage structure ready for future macro, trading, flow, economy, fund, world-market, watchlist, and research tools

## Architecture

```text
dashboard.py
  └── Registers the app's pages with Streamlit navigation
      └── pages/
          ├── 00_Markets.py       Implemented intraday index dashboard
          ├── 01_Macro.py         Placeholder page
          ├── 02_Indian_Macro.py  Placeholder page
          ├── 03_Trading.py       Placeholder page
          ├── 04_Flows.py         Placeholder page
          ├── 05_Economy.py       Placeholder page
          ├── 06_Funds.py         Placeholder page
          ├── 06_Watchlist.py     Placeholder page
          ├── 07_World.py         Placeholder page
          └── 08_Tools.py         Placeholder page

navigation.py
  └── Shared page header, section navigation, and placeholder-page layout

market_widgets.py
  └── Reusable index data and sparkline helpers

requirements.txt
  └── Runtime dependencies for local use and Streamlit hosting
```

### Request and rendering flow

1. Streamlit starts `dashboard.py`, which registers each page with `st.navigation`.
2. The selected page runs. `00_Markets.py` requests one-minute index data from Yahoo Finance via `yfinance` and snapshot data from NSE India's public market-data endpoints.
3. The Markets page renders index sparklines, a global asset carousel, and an NSE snapshot. `render_index_performance_table` can display broad-market or sector-index rows from the NSE feed; it fills missing return periods from NSE historical index-close archives and builds a distinct 52-week sparkline from those closes when NSE has no chart for an index.
4. Page headers and section links are rendered by `navigation.py`. The other pages currently use its shared placeholder layout.

Market data availability, freshness, and ticker coverage depend on Yahoo Finance, `yfinance`, and NSE India endpoints; data may be delayed, rate-limited, or unavailable. This dashboard is for informational purposes only and is not investment advice.

## Run locally

Python 3.10 or newer is recommended.

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run dashboard.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run dashboard.py
```

Streamlit prints a local URL in the terminal after the app starts.

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create an app and select the repository and branch.
3. Set the **Main file path** to `dashboard.py`.
4. Deploy. Streamlit installs the packages listed in `requirements.txt`.

No API keys or secrets are required by the current implementation.

## Repository layout

```text
.
├── dashboard.py
├── market_widgets.py
├── navigation.py
├── pages/
├── README.md
└── requirements.txt
```
