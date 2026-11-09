# Feature Specification: Modelo de alerta de conflicto por distrito

**Feature Branch**: `002-prensa-egpp` (el modelo sale en el mismo PR, #46)

**Created**: 2026-11-07

**Status**: Draft

**Input**: "El backend debe terminar en el modelo que predice: por distrito, con días de anticipación y razones
explicables. Niveles de escalada 0–4, eje de relevancia extractiva y alerta por corredor logístico."

## Contexto

Los módulos 001–004 dejaron en `datos/tremor.db` la historia de protestas (Defensoría 2008–2026, EGPP
1980–2025, prensa), los casos de conflicto mes a mes y el perfil de cada distrito (`distrito_variable`:
IDH, pobreza, minería, hidrocarburos, elecciones; MEF; BCRP; ENAHO). La literatura que respalda cada
variable está en `literatura.md`. Este módulo convierte todo eso en una **alerta**.

## Escala de escalada (la variable que se predice)

Nivel de un distrito en un mes = el máximo de lo que ocurrió ahí:

| Nivel | Nombre | Regla |
|---|---|---|
| 0 | Sin señal | nada |
| 1 | Seguimiento | caso de la Defensoría **latente** en el distrito |
| 2 | Tensión | caso **activo**, o protesta sin medida de fuerza (plantón, marcha, vigilia), o protesta anunciada |
| 3 | Medida de fuerza | paro, huelga, bloqueo de vías, toma de local, paralización, invasión, retención |
| 4 | Crisis | enfrentamiento, o protesta con heridos o muertos |

Fuentes: acciones de protesta de la Defensoría (mes del reporte), EGPP (sin los eventos que la EGPP
asignó a la capital por no saber el distrito), casos de la Defensoría, eventos de prensa.

## User Stories

### US1 — Alerta de los próximos 3 meses (P1)

El analista abre la alerta y ve los distritos con mayor **probabilidad de una medida de fuerza (nivel ≥ 3)
en los 3 meses siguientes al último reporte** (la Defensoría publica con un mes de rezago: con 1 mes la
alerta hablaría de un mes ya pasado), y la misma probabilidad solo para medidas de tema **extractivo**, con las 3 razones principales de cada uno y si el distrito tiene operaciones
extractivas (eje de relevancia).

**Acceptance**: tabla `alerta` con una fila por distrito para la ventana de 3 meses:
probabilidad, puesto, nivel actual, extractivo (sí/no), razones en castellano.

### US2 — Evidencia de que funciona (P1)

El jurado ve que el modelo se probó en meses que no vio y que le gana a la regla ingenua.

**Acceptance**: entrenamiento con meses objetivo hasta 2023-12; prueba 2024-01 en adelante. Tabla
`modelo_metrica` con, para cada modelo (ingenuo, logística, gradient boosting): PR-AUC, Brier,
**precisión en los 20 distritos más riesgosos de cada mes**, y la misma precisión solo en distritos
sin medidas de fuerza en los 12 meses previos ("nuevos").

### US3 — Variante crisis (P2)

La misma alerta para nivel 4 (crisis). Mismas métricas.

## Requisitos

- **FR-001** Sin fuga: cada variable del mes *t* usa solo datos publicados al cierre de *t*
  (variables anuales: el año anterior; PIM del MEF: el del año en curso, que se publica en enero;
  elecciones: la última ya realizada).
- **FR-002** Prueba temporal, nunca aleatoria.
- **FR-003** Razones por oclusión: cuánto baja la probabilidad si una variable toma su valor típico.
- **FR-004** Todo se recalcula con `python -m tremor.modelo` y queda en la base (y en CSV para la página).
- **FR-005** scikit-learn ya instalado; sin dependencias nuevas.

## Fuera de alcance (por ahora)

- Alerta por corredor vial: la calcula la página cruzando la alerta con la red vial (módulo 006).
- La prensa (diarios, radios, TV, Facebook) entra como **capa en vivo**, no como variable: su historia empieza en
  2026. Una medida de fuerza anunciada u ocurriendo en el distrito o su provincia marca `alerta_inmediata`.

## Riesgos conocidos

- La persistencia es muy fuerte: la regla ingenua es difícil de superar en distritos ya conflictivos. El
  valor del modelo se mide también en los distritos "nuevos".
- ~30 % de las acciones de la Defensoría no tienen distrito y quedan fuera.
- Las variables anuales que empiezan tarde (IDH desde 2017, MEF desde 2012) se dejan vacías antes;
  el gradient boosting maneja vacíos y la logística los imputa con la mediana.
