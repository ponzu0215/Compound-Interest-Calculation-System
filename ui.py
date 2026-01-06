from __future__ import annotations
import streamlit as st

def inject_css():
    try:
        with open("assets/styles.css", "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except Exception:
        pass

def page_header():
    st.markdown('<div class="container">', unsafe_allow_html=True)
    st.markdown('<h1>💰 投資複利計算システム</h1>', unsafe_allow_html=True)

def page_footer():
    st.markdown("</div>", unsafe_allow_html=True)  # container close
