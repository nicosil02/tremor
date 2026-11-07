# Research: 002 prensa y EGPP

Pruebas hechas el 7 nov 2026 (scripts en el scratchpad de la sesión; cifras en spec.md, Assumptions).

## R1. Dónde vive la EGPP

- **Decision**: en la misma `datos/tremor.db`, tabla `egpp_evento`, publicada con el resto en la rama
  `datos` y citada como fuente. Se carga una vez desde la máquina del autor; el workflow diario la
  conserva porque parte de la base anterior.
- **Rationale**: la base es descargable desde la web de la EGPP y el proyecto es académico; una sola
  base (principio VI) simplifica todos los cruces.
- **Excepción**: no se guarda `Comentar_t` (≈30 comentarios con nombres de dirigentes, principio I); de
  él solo se extrae la operación nombrada.

## R2. Catálogo de distritos

- **Decision**: la hoja `Espaciales` del formulario de la EGPP (1 892 filas: región, provincia, distrito
  con sus ids) exportada a `tremor/ubigeo.csv`. Son los códigos públicos del INEI 2023 que ya usa la base.
- **Rationale**: es exactamente el catálogo con el que se codificó la EGPP, así que el cruce es 1 a 1;
  evita descargar y limpiar el del INEI.
- **Check (hecho)**: 811 de los 813 `Distrito_id` de la EGPP están en el catálogo; los otros dos (`1101` y `160405`) son un evento cada uno: `1101` es Ica (110101) y `160405` (Santa Rosa, Mariscal Ramón Castilla) queda a nivel de provincia 1604.

## R3. Nombre de lugar → ubigeo

- **Decision**: el LLM devuelve **nombres** (región, provincia, distrito, localidad), nunca códigos;
  `lugares.py` los resuelve por reglas: normalizar (sin tildes, minúsculas), buscar de lo más fino a lo
  más grueso, y desambiguar nombres repetidos ("San Juan") con la provincia o región de la misma nota o
  de la consulta. Si no alcanza, se queda en el nivel seguro y guarda `precision`.
- **Rationale**: "primero reglas"; los LLM inventan códigos.
- **Bonus**: la misma función llena `accion_protesta.ubigeo` de la Defensoría (hoy vacío), necesario
  para la validación (R8).

## R4. Fuente de prensa

- **Decision**: Google News RSS (`news.google.com/rss/search?q=…&hl=es-419&gl=PE&ceid=PE:es-419`),
  una consulta por departamento × palabra de acción (paro, bloqueo, huelga, marcha, toma, plantón,
  enfrentamiento, movilización) con `when:1d` en la corrida diaria, y con `after:AAAA-MM-DD
  before:AAAA-MM-DD` por día para la recolección retro de validación. Pausa de 1 s entre consultas.
- **Hallazgos**: cada ítem trae título (con " - Medio" al final), `<source>`, `pubDate` y un enlace
  de redirección de Google; `<description>` no trae resumen. La búsqueda retro devuelve ~10 ítems por
  consulta, por eso se consulta por día. En una semana de Puno aparecieron El Comercio, Pachamama
  Radio, Revelación.pe, Servindi, Cutivalú, RPP, TVPerú, Infobae, etc.
- **Decision (texto)**: la v1 codifica con el **titular**. `ponytail:` sin texto completo; agregar el
  decodificador del enlace de Google y la descarga del texto abierto si la validación muestra que el
  titular no basta para el lugar o la fecha.
- **Alternatives**: GDELT (limita a 1 consulta/5 s y cubre poco la prensa regional peruana); RSS propios
  de cada medio (se pueden sumar después como otra `consulta`); suscripciones (prohibidas, FR-008).

- **Cambio tras probar (7 nov)**: Google News trae ~10 notas por consulta y mezcla otros países si la
  búsqueda no dice "Perú". La fuente principal pasa a ser **los feeds RSS de 21 medios** (RPP, Correo, El
  Comercio, Infobae, Andina, Servindi, Observatorio de Conflictos Mineros, Pachamama, Los Andes, El Búho,
  Radio Uno, Sin Fronteras, Prensa Regional, Inforegión, Diario Ahora, Radio Marañón…), que traen enlace real
  y resumen; Google News queda con 12 búsquedas temáticas + 25 por departamento, todas con "Perú". Una
  corrida: ~850 notas, ~170 pasan el filtro, ~100 s. La recolección retro (validación) usa solo Google News.
- **Validación**: diciembre 2025, porque ese mes tiene a la vez la tabla de la Defensoría (reporte 262) y la
  EGPP. El reporte 271 (septiembre 2026, HTML) no tiene acciones leídas: hueco de 001.

## R5. LLM

- **Decision**: `tremor/llm.py`, `POST {LLM_BASE_URL}/chat/completions` con `response_format:
  {"type":"json_object"}`, temperatura 0, modelo `LLM_MODEL` (Groq `openai/gpt-oss-120b`). Lotes de 25
  titulares por solicitud, cada uno con su id; respuesta = lista de codificaciones. Caché en
  `llm_cache(clave = sha256(modelo + versión del prompt + entrada))`.
- **Presupuesto**: ~1 500 titulares/día → filtro por reglas (palabra de acción y no deportes/espectáculos/
  "marcha blanca") deja ~500 → 20 solicitudes/día. La validación retro de un mes ≈ 750 consultas RSS y
  ≈ 300 solicitudes LLM, repartible en dos días.
- **Prompt**: definición de protesta del manual EGPP (pública, colectiva, contenciosa, episódica),
  más el estado *anunciada* (la EGPP no la tiene), las listas cerradas de `codigos_egpp.json`, la fecha
  de publicación de cada titular para resolver "mañana", "el lunes", "desde el 15".
- **Pendiente del usuario**: crear `.env` con `LLM_API_KEY` (no existe aún) y el secreto `LLM_API_KEY`
  en GitHub para el workflow.

## R6. Categorías

- **Decision**: `tremor/codigos_egpp.json` con las listas de acción (29), sector (32) y actor (≈105),
  adversario (15), reclamo (6) y sub-reclamo (51), tomadas del libro de códigos (hojas del formulario
  de la EGPP). Más el `tipo_conflicto` propio: `socioambiental_extractivo`, `laboral_minero`, `otro`.
- **Regla de `tipo_conflicto`** (EGPP y prensa): `laboral_minero` si el actor es Mineros/Trabajadores
  petroleros y el reclamo es laboral; `socioambiental_extractivo` si el reclamo es ambiental o
  territorial, o el actor es comunidad/ronda/frente de defensa/pobladores y el texto o el adversario
  apuntan a minería, hidrocarburos, energía o una empresa extractiva.

## R7. Operación nombrada

- **Decision**: expresión regular sobre `Reclamo_t`, `Comentar_t` e `Institución_2` (proyecto/mina/
  minera/lote/compañía + nombre propio) más una lista corta de alias (Tía María, Conga, Las Bambas/MMG,
  Antamina, Yanacocha, Tintaya/Antapaccay, Río Blanco/Majaz, Cuajone, Lote 192, Pluspetrol, Southern…).
  En prensa, el LLM devuelve `empresa` y `operacion`.
- **Rationale**: 65% de los eventos socioambientales nombra una operación. Ubicar la operación en el mapa
  (dónde está el conflicto, no dónde se marchó) es del módulo 004.

## R8. Agrupación y validación

- **Agrupar**: dos codificaciones son el mismo evento si comparten provincia (o distrito cuando ambos lo
  tienen), la misma familia de acción y la fecha del evento cae en ±1 día (±3 si es huelga o paro
  indefinido), y no se contradicen en actor. Union-find sobre esos pares. Un evento con alguna nota
  *anunciada* guarda `fecha_anuncio` = la más temprana de esas notas.
- **Validar contra la Defensoría**: acciones de septiembre 2026 (reporte 271) con ubigeo por R3; una
  acción está detectada si hay un evento de prensa en su provincia a ±1 día. Exhaustividad global, por
  departamento y para las socioambientales; anticipación = `fecha_evento − fecha_anuncio` (mediana).
- **Validar contra la EGPP**: recolección retro de diciembre 2025; emparejar eventos por fecha ±1 y
  provincia; precisión/exhaustividad/F1 de "es protesta" y kappa de acción, reclamo, adversario y
  distrito en los pares.
- **Revisión a mano (SC-003)**: muestra de 100 titulares codificados, exportada a CSV para que el autor
  marque aciertos.
