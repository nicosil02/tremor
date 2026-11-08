# 006: Página pública (Streamlit)

**Objetivo.** Mostrar la alerta del modelo (005) a cualquier persona con una URL pública: dónde es más probable una
protesta en los próximos 3 meses, por qué, qué dicen la prensa y las radios, y qué tan bien acierta el modelo.

**Requisitos**
- FR-001: lee los CSV de la rama `datos` (sin la base completa); en local, `datos/exportes/`.
- FR-002: tres objetivos a elegir: medida de fuerza en zona extractiva (por defecto), cualquier medida de fuerza, crisis.
- FR-003: mapa de los 1 892 distritos coloreado por la probabilidad calibrada (un solo tono, claro → oscuro).
- FR-004: ranking con razones, señal de prensa y radio, y ánimo hacia proyectos; descarga en CSV.
- FR-005: ficha del distrito con su historia mensual (nivel 0-4).
- FR-006: pestaña "¿Funciona?" con el desempeño en 2024-2026 contra el método ingenuo y contra ACLED.
- FR-007: actores por rol, nunca personas; no se publica la tabla cruda de ACLED (condiciones de uso).

**Despliegue.** Streamlit Community Cloud, archivo `streamlit_app.py`, rama `main` (la cuenta la conecta el autor).

**Tareas**
- [x] T001 `streamlit_app.py` con mapa, ranking, distrito, ánimo y desempeño.
- [ ] T002 Publicar en `datos` las tablas del modelo y el ánimo (sin `acled_evento`).
- [ ] T003 Desplegar en Streamlit Cloud y poner la URL en el README y en el issue #204.
