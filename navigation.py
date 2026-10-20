import re
from html import escape

import streamlit as st


PAGE_URLS = {
    "Markets": "/",
    "Macro": "/macro",
    "Indian Macro": "/indian-macro",
    "Trading": "/trading",
    "Flows": "/flows",
    "Economy": "/economy",
    "Funds": "/funds",
    "World": "/world",
    "Tools": "/tools",
    "Search your stock": "/watchlist",
}


def render_page_header(active_page):
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&family=Newsreader:ital,opsz,wght@0,6..72,200..800;1,6..72,200..800&display=swap" rel="stylesheet">
        <style>
        .block-container {
            max-width: 1500px;
            padding-top: 2rem;
        }
        body, .stApp, .stApp :is(p, span, div, label, button, input, textarea, select) {
            font-family: 'DM Sans', sans-serif;
        }
        .stApp h1.market-title,
        .stApp h1.market-title > span:first-child {
            font-family: 'Newsreader', Georgia, 'Times New Roman', serif !important;
            font-size: 54px;
            font-weight: 400;
            line-height: 1.2;
            margin: 0;
            padding: 0;
            font-synthesis: none;
        }
        .stApp h1.market-title {
            padding: 8px 0 4px;
        }
        .section-nav {
            display: flex;
            flex-wrap: nowrap;
            align-items: center;
            gap: clamp(14px, 2vw, 28px);
            width: 100%;
            overflow-x: auto;
            white-space: nowrap;
            padding: 6px 2px 12px;
            border-bottom: 1px solid color-mix(in srgb, currentColor 30%, transparent);
            scrollbar-width: thin;
        }
        .section-nav a {
            position: relative;
            flex: 0 0 auto;
            color: inherit;
            text-decoration: none;
            font-size: 14px;
            line-height: 1.4;
            padding: 4px 0;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }
        .section-nav a::after {
            position: absolute;
            right: 0;
            bottom: 0;
            left: 0;
            height: 2px;
            background: transparent;
            border-radius: 0 !important;
            content: "";
        }
        .section-nav a:hover::after,
        .section-nav a[aria-current="page"]::after {
            background: #e87552;
        }
        .stApp hr {
            margin: 8px 0 12px !important;
        }
        .stApp svg text {
            font-family: 'DM Sans', sans-serif;
        }
        [data-testid="stMetric"] {
            display: none;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border: 0 !important;
            border-top: 1px solid color-mix(in srgb, currentColor 30%, transparent) !important;
            border-radius: 0 !important;
            padding: 10px 0 0 !important;
            background: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<h1 class="market-title">Market Zist!</h1>', unsafe_allow_html=True)

    navigation_links = []
    for page_name, page_url in PAGE_URLS.items():
        current_attr = ' aria-current="page"' if page_name == active_page else ""
        navigation_links.append(
            f'<a href="{page_url}" target="_self"{current_attr}>{page_name}</a>'
        )
    st.markdown(
        f'<nav class="section-nav" aria-label="Dashboard sections">'
        f'{"".join(navigation_links)}</nav>',
        unsafe_allow_html=True,
    )


def render_secondary_page(page_name, title, description, sections):
    render_page_header(page_name)

    def section_id(section_title):
        slug = re.sub(r"[^a-z0-9]+", "-", section_title.lower()).strip("-")
        return f"contents-{slug}"

    content_column, contents_column = st.columns([3, 1], gap="large")
    with content_column:
        st.subheader(title)
        st.caption(description)
        for section_title, section_description in sections:
            section_anchor = section_id(section_title)
            st.markdown(
                f'<div id="{section_anchor}"></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<h3>{escape(section_title)}</h3>',
                unsafe_allow_html=True,
            )
            st.caption(section_description)

    with contents_column:
        contents_links = "".join(
            f'<a href="#{section_id(section_title)}" '
            'style="display:block;padding:7px 8px;color:inherit;text-decoration:none;'
            'font-size:13px;line-height:1.4;'
            'border-bottom:1px solid color-mix(in srgb,currentColor 18%,transparent)">'
            f'{escape(section_title)}</a>'
            for section_title, _ in sections
        )
        st.markdown(
            f'<nav aria-label="On this page" style="margin-top:25px">'
            f'{contents_links}</nav>',
            unsafe_allow_html=True,
        )
