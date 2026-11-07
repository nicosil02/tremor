# Especificación: Recolector de reportes de la Defensoría

**Rama**: `001-recolector-defensoria`

**Creada**: 2026-11-06

**Estado**: Borrador

**Entrada**: "Construir primero el scraper de la Defensoría. El de antes dependía de tener el último
enlace y los nombres no estaban estandarizados, por eso había muchas casuísticas. Hay que crear un
sistema estructurado para descargar y para encontrar la información que tiene valor (esto solo la
primera vez; de allí se escala a los demás informes). Identificar los conflictos en curso, porque
el reporte tiene varias secciones."

## Contexto verificado (6 de noviembre de 2026)

- El listado oficial (`/categorias_de_documentos/reportes/`, 120 páginas) trae 1.191 documentos
  de todo tipo, con título, fecha de publicación y enlace directo. De ellos, 140 son de conflictos
  sociales.
- Cubre 209 de los reportes del 23 al 271. Faltan 42 números, en su mayoría del 63 al 93
  (2009–2011), más algunos sueltos entre el 125 y el 198. Los reportes del 1 al 22 vienen en dos
  zip anuales (2004 y 2005).
- Los nombres de archivo no siguen ninguna regla (`10.pdf`, `conflictos_sociales42.pdf`,
  `RCS-N°-252-Feb-2025.pdf`, `Reporte-de-Conflictos-Sociales-n-267-VF.pdf`).
- **El reporte 271 (septiembre de 2026) ya no es PDF: es una página HTML** con 69 páginas y un
  índice de secciones.
- Desde 2026 la estructura cambió (Directiva N.° 0001-2026-DP/PAD), con secciones nuevas: alertas
  de atención prioritaria, mediaciones, cumplimiento de acuerdos y fases (temprana, escalamiento,
  crisis, desescalamiento, acuerdos).
- Cada caso tiene un **código estable** (por ejemplo `1053-0717`, número de ingreso y mes y año) y
  una ficha con etiquetas fijas: tipo, código, ubicación, ingreso al registro, competencia,
  fase y diálogo, actuaciones, descripción del caso, actores primarios, secundarios y terciarios,
  y hechos del mes.
- El resumen de cada reporte declara sus totales ("Se da cuenta de 193 conflictos sociales
  registrados: 144 activos… y 49 latentes"). Eso permite validar cada extracción.

## Escenarios de usuario y pruebas

### Historia 1: Catálogo completo de reportes (Prioridad: P1)

Como analista, quiero saber qué reportes de conflictos existen, cuáles tengo descargados y cuáles
faltan, sin depender del nombre del archivo ni del "último enlace".

**Por qué esta prioridad**: sin catálogo no hay nada que extraer. Es la base de todo lo demás.

**Prueba independiente**: se corre el catálogo desde cero y se obtiene la lista de reportes con su
número, mes, año, formato y fuente, más la lista de números faltantes.

**Escenarios de aceptación**:

1. **Dado** un catálogo vacío, **cuando** se corre el descubrimiento completo, **entonces** quedan
   registrados todos los reportes de conflictos del listado oficial, cada uno con número, periodo,
   URL, formato (PDF, HTML o zip) y fecha de publicación.
2. **Dado** un catálogo ya armado, **cuando** se publica un reporte nuevo y se corre la
   actualización, **entonces** se agrega solo ese reporte, sin duplicar los anteriores.
3. **Dado** un número de la secuencia que no aparece en el listado, **cuando** termina el
   descubrimiento, **entonces** el número figura en la lista de faltantes junto con las fuentes
   alternativas que se probaron.

---

### Historia 2: Identidad del reporte por su contenido (Prioridad: P1)

Como analista, quiero que cada archivo descargado se identifique por lo que dice su portada y no
por cómo se llama.

**Por qué esta prioridad**: los nombres y títulos del sitio son inconsistentes. Un error aquí
contamina todo el panel.

**Prueba independiente**: se descargan reportes con nombres raros (`10.pdf`,
`conflictos_sociales42.pdf`, el HTML del 271) y se verifica que el número y el periodo leídos de la
portada coinciden con los reales.

**Escenarios de aceptación**:

1. **Dado** un archivo descargado, **cuando** se procesa, **entonces** el número y el periodo se
   leen de la portada y se comparan con los del listado. Si no coinciden, prevalece la portada y
   se registra la discrepancia.
2. **Dado** el mismo reporte publicado en dos formatos o dos URL, **cuando** se procesa,
   **entonces** queda un solo reporte con sus fuentes asociadas.

---

### Historia 3: Mapa de secciones por época (Prioridad: P1)

Como analista, quiero saber qué información valiosa trae cada reporte y en qué sección, aunque el
formato haya cambiado con los años.

**Por qué esta prioridad**: es el paso que se hace "solo la primera vez". Define qué se extrae y
de dónde para todos los reportes.

**Prueba independiente**: para un reporte de cada época se obtiene la lista de secciones
encontradas y su equivalencia con las secciones canónicas.

**Escenarios de aceptación**:

1. **Dado** un reporte de cada época (2005, 2010, 2015, 2020, 2025 y 2026 en HTML), **cuando** se
   analiza, **entonces** se identifican sus secciones y se asignan a las secciones canónicas:
   resumen y totales, estadísticas, casos nuevos, fichas de casos activos, casos latentes,
   resueltos, retirados, acciones colectivas de protesta, alertas, fallecidos y heridos,
   mediación y diálogo, y cumplimiento de acuerdos.
2. **Dado** un reporte con una sección que no corresponde a ninguna canónica, **cuando** se
   analiza, **entonces** se registra como "sección no mapeada" con su título y página, en lugar de
   descartarse en silencio.

---

### Historia 4: Casos en curso, mes a mes (Prioridad: P1)

Como analista de riesgo, quiero una tabla con un registro por caso y por mes (estado, fase,
diálogo, actores y hechos del mes) para seguir la evolución de cada conflicto.

**Por qué esta prioridad**: es el insumo central para el mapa y para la predicción de escalamiento.

**Prueba independiente**: con los reportes de 2025 y 2026 extraídos, se elige un caso conocido (por
ejemplo `0397-1208`, Cenepa) y se ve su trayectoria mes a mes.

**Escenarios de aceptación**:

1. **Dado** un reporte extraído, **cuando** se valida, **entonces** el número de casos extraídos
   por estado (activos, latentes) coincide con los totales que declara el propio reporte. Si no
   coincide, el reporte queda marcado como fallido y no entra al panel.
2. **Dado** un caso con código, **cuando** aparece en varios reportes, **entonces** todas sus
   apariciones se enlazan por ese código.
3. **Dado** un reporte antiguo sin códigos, **cuando** se enlazan sus casos, **entonces** se usa la
   combinación de nombre del caso, ubicación y actores, y cada enlace lleva un nivel de confianza.
   Los enlaces dudosos van a una lista de revisión.

---

### Historia 5: Acciones colectivas, alertas y víctimas (Prioridad: P2)

Como analista, quiero las tablas de acciones colectivas de protesta, alertas y fallecidos o heridos
de cada reporte en un formato único.

**Por qué esta prioridad**: complementan el panel de casos y sirven para medir la violencia.

**Prueba independiente**: para un reporte se compara el número de acciones de protesta extraídas
con el total que declara su resumen (151 en el reporte 271).

**Escenarios de aceptación**:

1. **Dado** un reporte con tabla de acciones colectivas, **cuando** se extrae, **entonces** cada
   acción queda con fecha, medida, actores, lugar, demanda y ubigeo, y el total coincide con el
   declarado.

### Casos borde

- Un reporte publicado como HTML, zip o PDF escaneado (sin texto).
- Dos documentos con el mismo número (reporte regular y reporte especial, como el 35 y el 35
  especial).
- Notas de prensa o informes defensoriales que mencionan "conflictos" pero no son el reporte
  mensual: no entran al catálogo de reportes.
- Un caso que cambia de nombre ("antes Afrodita") o se fusiona con otro.
- Un caso multirregional sin un único departamento.
- El sitio no responde o corta la conexión a mitad de la descarga.

## Requisitos

### Requisitos funcionales

- **RF-001**: El sistema DEBE descubrir los reportes recorriendo el listado oficial completo la
  primera vez, y solo las páginas recientes en las actualizaciones.
- **RF-002**: El sistema DEBE probar fuentes alternativas para los números faltantes (otras
  secciones del sitio, el archivo de medios del sitio y copias archivadas públicas) y registrar
  qué fuente se usó o que no se encontró.
- **RF-003**: El sistema DEBE aceptar reportes en PDF con texto, PDF escaneado, HTML y zip.
- **RF-004**: El sistema DEBE identificar cada reporte por el número y el periodo de su portada.
- **RF-005**: El sistema DEBE guardar el archivo original de cada reporte, con su huella de
  contenido, para no volver a descargarlo.
- **RF-006**: El sistema DEBE dividir cada reporte en secciones y asignarlas a las secciones
  canónicas, conservando las no mapeadas.
- **RF-007**: El sistema DEBE extraer cada ficha de caso con sus campos: código, nombre, tipo,
  ubicación (departamento, provincia, distrito y ubigeo), ingreso al registro, competencia,
  estado, fase, diálogo, actores por nivel, descripción y hechos del mes.
- **RF-008**: El sistema DEBE validar cada reporte contra los totales de su resumen y marcarlo
  como válido o fallido, con el detalle de la diferencia.
- **RF-009**: El sistema DEBE enlazar los casos entre reportes por código, y por similitud con
  nivel de confianza cuando no hay código.
- **RF-010**: El sistema DEBE extraer las acciones colectivas de protesta, las alertas y los
  fallecidos y heridos cuando el reporte las trae.
- **RF-011**: Correr cualquier paso dos veces NO DEBE duplicar datos.
- **RF-012**: El sistema DEBE dejar un registro de cada corrida: qué se descubrió, descargó,
  extrajo y validó, y qué falló.
- **RF-013**: El sistema DEBE exportar el panel de casos y las tablas de acciones en CSV.
- **RF-014**: Las reglas fijas DEBEN usarse antes que el LLM. El LLM solo se usa para texto libre
  que las reglas no pueden estructurar, y sus respuestas se guardan en caché.

### Entidades clave

- **Reporte**: número, periodo (mes y año), fecha de publicación, formato, fuentes (URL),
  huella del archivo, estado de validación y totales declarados.
- **Sección**: reporte, título original, sección canónica, páginas y texto.
- **Caso**: código, nombre vigente, nombres anteriores, tipo, ubigeo y fecha de ingreso al
  registro.
- **Caso-mes**: caso, reporte, estado, fase, diálogo, competencia, actores, descripción, hechos
  del mes y página de origen.
- **Acción colectiva**: reporte, fecha, medida, actores, lugar, ubigeo y demanda.
- **Víctima agregada**: reporte, caso, fallecidos y heridos (cifras agregadas, sin nombres).
- **Corrida**: inicio, fin, paso, conteos y errores.

## Criterios de éxito

### Resultados medibles

- **CE-001**: El catálogo contiene al menos 249 de los 271 reportes (92%), y cada faltante tiene
  documentado dónde se buscó.
- **CE-002**: El 100% de los reportes de 2023 a 2026 queda validado contra sus totales.
- **CE-003**: Al menos el 90% de los reportes de 2015 a 2022 queda validado contra sus totales.
- **CE-004**: En una revisión manual de 30 fichas al azar, al menos el 95% de los campos coincide
  con el reporte original.
- **CE-005**: Una actualización mensual (un reporte nuevo) termina en menos de 5 minutos.
- **CE-006**: Volver a correr todo el proceso sin reportes nuevos no agrega ni modifica ningún
  registro.

## Supuestos

- La Defensoría sigue publicando el listado en la misma dirección. Si cambia, solo se ajusta el
  descubrimiento.
- Los reportes de 2004 a 2008 pueden tener un formato muy distinto. Para la demo del 11 de
  noviembre bastan los reportes desde 2015, y lo anterior se completa después.
- Las bases ya compiladas por terceros (por ejemplo, la de conflictos 2004–2024 del repositorio
  público Violencia_BD) se usan solo como contraste para validar, no como fuente.
- Los datos personales que aparecen en los reportes (nombres de comisionados o de dirigentes) no
  se extraen.
