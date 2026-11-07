# Data model: 002 prensa y EGPP

## `datos/egpp.db` (local, nunca publicada)

### egpp_evento
| Campo | Notas |
|---|---|
| id INTEGER PK | `ID` de la EGPP |
| fecha TEXT | ISO |
| ubigeo TEXT | `Distrito_id` con 6 dígitos (cero a la izquierda) |
| capital_por_defecto INTEGER | 1 si el distrito termina en 01 (posible capital asignada por falta de dato) |
| periodico, sector, actor, actor_t, accion_1..4, adversario, institucion_1, institucion_2, reclamo, sub_reclamo, reclamo_t, comentario | tal cual |
| participantes, duracion_h, heridos, muertos, detenidos, fuerza_estatal | numéricos |
| tipo_conflicto TEXT | `socioambiental_extractivo` / `laboral_minero` / `otro` (research R6) |
| operacion TEXT | operación o empresa nombrada (R7), o NULL |
| duplicado_de INTEGER | id del evento que se conserva si es repetido (FR-004e) |
| version TEXT | versión del archivo cargado (`2025-12`) |

## `datos/perfil_distrito_egpp.csv` (publicado, versionado)

Una fila por ubigeo con al menos un evento no duplicado: `ubigeo, region, provincia, distrito, eventos,
eventos_2015_2025, primer_anio, ultimo_anio, socioambiental, laboral_minero, ambientales, territoriales,
laborales, politicos, economicos, servicios, top_subreclamos, top_actores, pct_bloqueo, pct_heridos,
pct_muertos, pct_represion, contra_empresa, operaciones, pct_capital_por_defecto`.
Columnas de texto (`top_*`, `operaciones`) son categorías o nombres de empresas, nunca texto libre.
Y `perfil_distrito_anio_egpp.csv`: `ubigeo, anio, eventos, socioambiental, laboral_minero, con_violencia`.

## `datos/tremor.db` (pública) — tablas nuevas

### nota
| Campo | Notas |
|---|---|
| id TEXT PK | sha1(medio normalizado + titular normalizado) |
| medio, titular, publicado (ISO), enlace | del RSS |
| consulta TEXT | la búsqueda que la trajo (dpto + palabra + ventana) |
| departamento_consulta TEXT | ayuda a desambiguar el lugar |
| descargado TEXT | fecha de descarga |
| filtro TEXT | NULL (pasa) o motivo del descarte por reglas |

### codificacion
`nota_id` + `version` (PK), `es_protesta`, `estado` (anunciada/ocurrida/suspendida), `fecha_evento`,
`region`, `provincia`, `distrito`, `localidad` (como los nombra la nota), `ubigeo`, `precision`
(departamento/provincia/distrito/localidad), `sector`, `actor`, `accion`, `adversario`, `empresa`,
`operacion`, `reclamo`, `sub_reclamo`, `heridos`, `muertos`, `detenidos`, `tipo_conflicto`.
Las categorías son las de `codigos_egpp.json`; valor fuera de lista → NULL.

### evento_prensa / evento_nota
`evento_prensa(id, estado, fecha_anuncio, fecha_evento, ubigeo, precision, accion, actor, reclamo,
tipo_conflicto, empresa, operacion, n_notas, n_medios)`; `evento_nota(evento_id, nota_id)`.
Se reconstruyen enteras en cada `agrupar` (barato y determinista).

Estados: una nota *anunciada* y una *ocurrida* del mismo grupo dejan el evento `ocurrida` con
`fecha_anuncio`; una nota posterior *suspendida* lo deja `suspendida`.

### llm_cache
`clave TEXT PK` (sha256 de modelo + versión de prompt + entrada), `respuesta TEXT`, `modelo`, `creado`.

### accion_protesta (existente)
Se llena `ubigeo` y `departamento` con `lugares.py` a partir de `lugar` y `actores`.
