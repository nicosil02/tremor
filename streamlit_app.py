"""Tremor en Streamlit Community Cloud: la app real (GitHub Pages) a pantalla completa, sin barra ni menú.

Sin acceso por usuario para que cualquiera pueda revisar la demo. El acceso por cliente (una cuenta ve solo su
empresa) está listo en `tremor.acceso` para cuando haya clientes. Los datos del modelo se exploran con
`streamlit run paginas/explorar.py`.

    streamlit run streamlit_app.py
"""
import streamlit as st
import streamlit.components.v1 as componentes

APP = "https://nicosil02.github.io/tremor/app.html?admin"  # la misma app publicada, con todas las mineras

st.set_page_config(page_title="Tremor", layout="wide", initial_sidebar_state="collapsed")
# la barra de Streamlit Cloud ("Fork") va por encima de la app y no se puede quitar: la app empieza debajo de ella
st.markdown("<style>header, [data-testid=stSidebar], [data-testid=stSidebarCollapsedControl] {display:none}"
            ".block-container{padding:3.6rem 0 0;max-width:100%} iframe{display:block;height:calc(100vh - 3.6rem)!important}</style>", unsafe_allow_html=True)
componentes.iframe(APP, height=900, scrolling=True)
