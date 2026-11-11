"""Tremor en Streamlit: acceso con usuario y contraseña y, detrás, la app de docs/app.html con la empresa de la cuenta.

Las cuentas van en los secretos (local: .streamlit/secrets.toml, fuera del repo; en Streamlit Cloud: Settings > Secrets):

    [cuentas.equipo]
    sal = "..."
    huella = "..."     # python streamlit_app.py --huella  (pide la contraseña y la imprime cifrada)
    empresa = "*"      # "*" ve todas las mineras; un cliente lleva la suya, p. ej. "Bateas"

    streamlit run streamlit_app.py
"""
import json, secrets, sys
from pathlib import Path

from tremor.acceso import huella, valida

AQUI = Path(__file__).parent
PAGINAS = "https://nicosil02.github.io/tremor/"  # de ahí lee la app sus datos y su mapa


if __name__ == "__main__" and "--huella" in sys.argv:
    import getpass
    sal = secrets.token_hex(16)
    print(f'sal = "{sal}"\nhuella = "{huella(getpass.getpass("Contraseña: "), sal)}"')
    sys.exit()

import streamlit as st

st.set_page_config(page_title="Tremor", page_icon="docs/favicon.svg" if (AQUI / "docs/favicon.svg").exists() else None, layout="wide")


def acceso():
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro, st.form("acceso"):
        st.markdown("## Tremor\nAcceso de clientes")
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar", type="primary", use_container_width=True):
            empresa = valida(st.secrets.get("cuentas", {}), usuario, clave)
            if empresa:
                st.session_state.update(usuario=usuario.strip().lower(), empresa=empresa)
                st.rerun()
            st.error("Usuario o contraseña incorrectos.")
        st.caption("¿Aún no tiene acceso? Escríbanos a nicolas.silva@pucp.edu.pe para un piloto.")


def operacion():
    todas = st.session_state.empresa == "*"
    config = {"todas": todas, "empresa": None if todas else st.session_state.empresa}
    html = (AQUI / "docs" / "app.html").read_text(encoding="utf-8").replace(
        "<head>", f'<head><base href="{PAGINAS}"><script>window.TREMOR = {json.dumps(config)}</script>', 1)
    st.markdown('<style>.block-container{padding:1rem 1rem 0}</style>', unsafe_allow_html=True)
    st.iframe(html, height=840)


if "empresa" not in st.session_state:
    acceso()
    st.stop()

paginas = [st.Page(operacion, title="Mi operación", default=True)]
if st.session_state.empresa == "*":
    paginas.append(st.Page("paginas/explorar.py", title="Datos del modelo"))
with st.sidebar:
    st.caption(f"Sesión de **{st.session_state.usuario}**")
    if st.button("Cerrar sesión"):
        st.session_state.clear()
        st.rerun()
st.navigation(paginas).run()
