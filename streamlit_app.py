"""Tremor en Streamlit Community Cloud: la app real (GitHub Pages) a pantalla completa, y detrás los datos del modelo.

Sin acceso por usuario para que cualquiera pueda revisar la demo. El acceso por cliente (una cuenta ve solo su
empresa) está listo en `tremor.acceso` para cuando haya clientes.

    streamlit run streamlit_app.py
"""
import streamlit as st
import streamlit.components.v1 as componentes

APP = "https://nicosil02.github.io/tremor/app.html?admin"  # la misma app publicada, con todas las mineras

st.set_page_config(page_title="Tremor", layout="wide", initial_sidebar_state="collapsed")


def operaciones():
    # sin márgenes ni cabecera: la app ocupa toda la ventana
    st.markdown("<style>.block-container{padding:0;max-width:100%} header[data-testid=stHeader]{height:0}"
                "iframe{display:block}</style>", unsafe_allow_html=True)
    componentes.iframe(APP, height=900, scrolling=True)


st.navigation([st.Page(operaciones, title="Operaciones", default=True),
               st.Page("paginas/explorar.py", title="Datos del modelo")]).run()
