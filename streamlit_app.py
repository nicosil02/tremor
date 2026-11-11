"""Tremor en Streamlit Community Cloud: la app de docs/app.html con todas las mineras, y detrás los datos del modelo.

Sin acceso por usuario para que cualquiera pueda revisar la demo. El acceso por cliente (una cuenta ve solo su
empresa) está listo en `tremor.acceso` para cuando haya clientes.

    streamlit run streamlit_app.py
"""
import json
from pathlib import Path

import streamlit as st

AQUI = Path(__file__).parent
PAGINAS = "https://nicosil02.github.io/tremor/"  # de ahí lee la app sus datos y su mapa

st.set_page_config(page_title="Tremor", page_icon="docs/favicon.svg" if (AQUI / "docs/favicon.svg").exists() else None, layout="wide")


def operaciones():
    html = (AQUI / "docs" / "app.html").read_text(encoding="utf-8").replace(
        "<head>", f'<head><base href="{PAGINAS}"><script>window.TREMOR = {json.dumps({"todas": True})}</script>', 1)
    st.markdown('<style>.block-container{padding:1rem 1rem 0}</style>', unsafe_allow_html=True)
    st.iframe(html, height=840)


st.navigation([st.Page(operaciones, title="Operaciones", default=True),
               st.Page("paginas/explorar.py", title="Datos del modelo")]).run()
