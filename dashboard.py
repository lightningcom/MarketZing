import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf
from navigation import render_page_header


pages = [
    st.Page("pages/00_Markets.py", title="Markets", default=True),
    st.Page("pages/01_Macro.py", title="Macro", url_path="macro"),
    st.Page("pages/02_Indian_Macro.py", title="Indian Macro", url_path="indian-macro"),
    st.Page("pages/03_Trading.py", title="Trading", url_path="trading"),
    st.Page("pages/04_Flows.py", title="Flows", url_path="flows"),
    st.Page("pages/05_Economy.py", title="Economy", url_path="economy"),
    st.Page("pages/06_Funds.py", title="Funds", url_path="funds"),
    st.Page("pages/07_World.py", title="World", url_path="world"),
    st.Page("pages/08_Tools.py", title="Tools", url_path="tools"),
    st.Page("pages/06_Watchlist.py", title="Search your stock", url_path="watchlist"),
]

current_page = st.navigation(pages, position="hidden")
current_page.run()

