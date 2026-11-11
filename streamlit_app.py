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
# la barra de Streamlit (Fork, GitHub) se oculta con !important: su propia regla es más fuerte que un selector simple
st.markdown("<style>.stAppHeader, header[data-testid=stHeader], [data-testid=stSidebar], [data-testid=stSidebarCollapsedControl] {display:none!important}"
            ".block-container{padding:0!important;max-width:100%} iframe{display:block;height:100vh!important}</style>", unsafe_allow_html=True)
componentes.iframe(APP, height=900, scrolling=True)
