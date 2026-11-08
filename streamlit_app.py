"""Tremor: alerta temprana de conflicto social cerca de operaciones extractivas (módulo 006).

Lee los CSV que publica la rama `datos` (los actualizan los workflows); en local usa `datos/exportes/`.
    streamlit run streamlit_app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

RAMA = "https://raw.githubusercontent.com/nicosil02/tremor/datos/"
LOCAL = Path(__file__).parent / "datos"
AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # secuencial de un tono
OBJETIVOS = {"Medida de fuerza en zona extractiva": ("y_extractivo", "prob_extractivo", "puesto_extractivo",
                                                     "razones_extractivo"),
             "Cualquier medida de fuerza (paro, bloqueo, toma)": ("y_fuerza", "prob", "puesto", "razones"),
             "Crisis (violencia, heridos o muertos)": ("y_crisis", "prob_crisis", None, "razones")}
NIVEL = {0: "sin registro", 1: "caso latente", 2: "protesta o caso activo", 3: "medida de fuerza", 4: "crisis"}

st.set_page_config(page_title="Tremor", page_icon="🌋", layout="wide")


@st.cache_data(ttl=3600, show_spinner="Cargando datos…")
def leer(nombre):
    for ruta in (LOCAL / "exportes" / nombre, LOCAL / nombre):
        if ruta.exists():
            return pd.read_csv(ruta, dtype={"ubigeo": str})
    try:
        return pd.read_csv(RAMA + nombre, dtype={"ubigeo": str})
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner="Cargando el mapa…")
def mapa_base():
    ruta = LOCAL / "distritos.geojson"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else requests.get(RAMA + "distritos.geojson",
                                                                                            timeout=60).json()


alerta, metrica = leer("alerta.csv"), leer("modelo_metrica.csv")
if alerta.empty:
    st.error("No se pudieron leer los datos de la rama `datos`.")
    st.stop()

st.title("Tremor")
st.markdown("**Alerta temprana de conflicto social cerca de operaciones extractivas en el Perú.** "
            f"Probabilidad de protesta por distrito para **{alerta.ventana.iloc[0]}**, con datos hasta "
            f"{alerta.mes_base.iloc[0]} y las razones de cada alerta.")

eleccion = st.radio("¿Qué quieres anticipar?", list(OBJETIVOS), horizontal=True)
objetivo, col_prob, col_puesto, col_razon = OBJETIVOS[eleccion]
a = alerta.sort_values(col_prob, ascending=False).reset_index(drop=True)
a["puesto_vista"] = a.index + 1


def valor(modelo, objetivo, m):
    v = metrica[(metrica.modelo == modelo) & (metrica.objetivo == objetivo) & (metrica.metrica == m)].valor
    return float(v.iloc[0]) if len(v) else float("nan")


mejor = metrica[(metrica.objetivo == objetivo) & (metrica.metrica == "precision_top20")
                & (metrica.modelo != "ingenuo")].sort_values("valor").modelo.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Aciertos en los 20 distritos más altos", f"{valor(mejor, objetivo, 'precision_top20'):.0%}",
          f"{valor(mejor, objetivo, 'precision_top20') - valor('ingenuo', objetivo, 'precision_top20'):+.0%} vs. "
          "repetir el mes pasado", help="Promedio mensual en 2024-2026 (datos que el modelo no vio al entrenar).")
c2.metric("Validación externa (ACLED)", f"{valor(mejor, objetivo, 'precision_top20_acled'):.0%}",
          f"{valor(mejor, objetivo, 'precision_top20_acled') - valor('ingenuo', objetivo, 'precision_top20_acled'):+.0%}"
          " vs. repetir el mes pasado",
          help="Los mismos 20 distritos, contrastados con ACLED, una base independiente de la Defensoría.")
c3.metric("Tasa base", f"{valor(mejor, objetivo, 'tasa_base'):.1%}", help="Distritos-mes con el evento en 2024+.")
c4.metric("Alertas en vivo (prensa y radio)", int(a.alerta_inmediata.fillna(0).astype(bool).sum()),
          help="Protestas anunciadas o en curso en los últimos 30 días.")

t_mapa, t_ranking, t_distrito, t_animo, t_modelo = st.tabs(
    ["Mapa", "Ranking", "Distrito", "Ánimo hacia proyectos", "¿Funciona?"])

with t_mapa:
    fig = px.choropleth_map(a, geojson=mapa_base(), locations="ubigeo", featureidkey="properties.ubigeo",
                            color=col_prob, color_continuous_scale=AZUL, range_color=(0, a[col_prob].quantile(.995)),
                            hover_name="lugar", hover_data={col_prob: ":.1%", "puesto_vista": True, "ubigeo": False},
                            labels={col_prob: "probabilidad", "puesto_vista": "puesto"},
                            map_style="carto-positron", center={"lat": -9.6, "lon": -75.3}, zoom=4.7, opacity=.85)
    fig.update_traces(marker_line_width=0)
    fig.update_coloraxes(colorbar_tickformat=".0%", colorbar_title="probabilidad")
    fig.update_layout(height=680, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Color: probabilidad calibrada de que ocurra el evento elegido en los próximos 3 meses. "
               "Límites distritales INEI 2025.")

with t_ranking:
    n = st.slider("Distritos", 10, 100, 30, step=10)
    vista = a.head(n).assign(probabilidad=lambda d: (d[col_prob] * 100).round(1),
                             nivel_actual=lambda d: d.nivel_actual.map(NIVEL)).fillna("")
    columnas = {"puesto_vista": "Puesto", "lugar": "Distrito", "probabilidad": "Prob. (%)",
                "nivel_actual": "Situación del último mes", col_razon: "Por qué", "senal_prensa": "Prensa y radio (30 días)"}
    if "animo_proyectos" in vista:
        columnas["animo_proyectos"] = "Ánimo hacia proyectos (14 días)"
    st.dataframe(vista[list(columnas)].rename(columns=columnas), hide_index=True, use_container_width=True,
                 column_config={"Prob. (%)": st.column_config.ProgressColumn(min_value=0, max_value=float(a[col_prob].max() * 100), format="%.1f")})
    st.download_button("Descargar la alerta completa (CSV)", alerta.to_csv(index=False).encode("utf-8"), "alerta.csv")

with t_distrito:
    lugar = st.selectbox("Distrito", a.lugar, index=0)
    r = a[a.lugar == lugar].iloc[0]
    d1, d2, d3 = st.columns(3)
    d1.metric("Probabilidad", f"{r[col_prob]:.1%}")
    d2.metric("Puesto nacional", f"{int(r.puesto_vista)} de {len(a)}")
    d3.metric("Último mes", NIVEL.get(int(r.nivel_actual), "—"))
    st.markdown(f"**Por qué:** {r[col_razon]}")
    if isinstance(r.get("corredores"), str):
        st.markdown(f"**Corredor:** {r.corredores}")
    if isinstance(r.get("senal_prensa"), str):
        st.markdown(f"**Prensa y radio:** {r.senal_prensa}" + (f" ([nota]({r.enlace_prensa}))"
                                                                 if isinstance(r.get("enlace_prensa"), str) else ""))
    if isinstance(r.get("animo_proyectos"), str):
        st.markdown(f"**Ánimo hacia proyectos:** {r.animo_proyectos}")
    h = leer("nivel_mes.csv")
    h = h[h.ubigeo == r.ubigeo]
    if len(h):
        h = h.assign(fecha=pd.to_datetime(h.mes), situacion=h.nivel.map(NIVEL))
        fig = px.bar(h, x="fecha", y="nivel", hover_data={"situacion": True, "nivel": False},
                     labels={"fecha": "", "nivel": "nivel (0-4)"}, color_discrete_sequence=[AZUL[4]])
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis_range=[0, 4.2], bargap=.1)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Historia del distrito según la Defensoría del Pueblo y la base de protestas EGPP-PUCP: "
                   "1 caso latente · 2 protesta o caso activo · 3 medida de fuerza · 4 crisis.")
    else:
        st.info("Sin protestas ni casos registrados en este distrito.")

with t_animo:
    animo = leer("animo.csv")
    st.markdown("Antes de un conflicto suelen subir las menciones a la empresa o al proyecto y el tono se vuelve "
                "negativo. Tremor escucha **225 radios de 96 provincias** con operaciones extractivas y lee la prensa "
                "regional; mide cuántas veces se nombra cada proyecto en 14 días frente a lo normal y con qué tono.")
    if len(animo):
        v = animo.sort_values(["menciones_14d", "alza"], ascending=False)
        st.dataframe(v[["proyecto", "menciones_14d", "base_14d", "alza", "pct_negativo", "tono_14d"]].rename(columns={
            "proyecto": "Proyecto", "menciones_14d": "Menciones (14 días)", "base_14d": "Lo normal (14 días)",
            "alza": "Alza (×)", "pct_negativo": "Negativas", "tono_14d": "Tono (-1 a 1)"}), hide_index=True,
            use_container_width=True, column_config={"Negativas": st.column_config.NumberColumn(format="percent")})
    else:
        st.info("El índice de ánimo se publica con la primera corrida de radio.")
    ev = leer("eventos_prensa.csv")
    if len(ev):
        ev = ev.merge(alerta[["ubigeo", "lugar"]], on="ubigeo", how="left")
        st.subheader("Protestas detectadas en prensa y radio")
        cols = [c for c in ("fecha_evento", "estado", "lugar", "accion", "actor", "reclamo", "medios") if c in ev]
        st.dataframe(ev.sort_values(cols[0], ascending=False)[cols].head(50), hide_index=True,
                     use_container_width=True)

with t_modelo:
    st.markdown(
        "**Cómo se entrena.** Panel distrito × mes desde 2010 con 60 variables (historia de protestas, casos de la "
        "Defensoría, operaciones y concesiones, comunidades, canon, pobreza, elecciones, vías, agua, bosques, "
        "gobernanza municipal). Se entrena con los meses hasta 2023 y se mide en 2024-2026, que el modelo nunca vio. "
        "Compiten logística, Lasso, árbol, bosque aleatorio, boosting y un ensamble; gana el que más acierta en los 20 "
        "distritos más altos. El método ingenuo es repetir lo que pasó el mes anterior.")
    m = metrica[metrica.objetivo == objetivo].pivot_table(index="modelo", columns="metrica", values="valor")
    cols = {"precision_top20": "Aciertos top 20", "precision_top20_nuevos": "Top 20 sin conflicto en 12 meses",
            "precision_top20_acled": "Top 20 según ACLED", "pr_auc": "PR-AUC", "brier": "Brier"}
    st.dataframe(m[[c for c in cols if c in m]].rename(columns=cols).sort_values("Aciertos top 20", ascending=False)
                 .style.format("{:.3f}", na_rep=""), use_container_width=True)
    imp = leer("modelo_importancia.csv")
    imp = imp[imp.objetivo == objetivo].nlargest(12, "importancia").sort_values("importancia")
    if len(imp):
        fig = px.bar(imp, x="importancia", y="variable", orientation="h", hover_data=["grupo"],
                     color_discrete_sequence=[AZUL[4]], labels={"importancia": "importancia (permutación)",
                                                                 "variable": ""})
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=30, b=0), title="Variables que más pesan")
        st.plotly_chart(fig, use_container_width=True)
    cal = leer("modelo_calibracion.csv")
    cal = cal[cal.objetivo == objetivo]
    if len(cal):
        fig = px.line(cal.melt(id_vars="decil", value_vars=["calibrada", "observada"]), x="decil", y="value",
                      color="variable", markers=True, color_discrete_sequence=["#2a78d6", "#eb6834"],
                      labels={"value": "frecuencia", "decil": "decil de riesgo predicho", "variable": ""})
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=30, b=0), title="Calibración: predicho vs. observado")
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption("Fuentes: Defensoría del Pueblo (reportes de conflictos 2004-2026), base de protestas EGPP-PUCP (Arce 2024), "
           "ACLED (validación), INEI (Censo 2017, ENAHO, RENAMU), PNUD, MEF, BCRP, INGEMMET, MINEM, OEFA, SENACE, ANA, "
           "SERNANP, MINAM-GEOBOSQUES, Ministerio de Cultura (BDPI), MTC, ONPE, SUTRAN, prensa regional y radios en vivo. "
           "Los actores se nombran por su rol, nunca como personas. Código: github.com/nicosil02/tremor · "
           "Diplomado Q-Lab PUCP 2026.")
