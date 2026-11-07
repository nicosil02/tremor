# Investigación: Recolector de reportes de la Defensoría

Hecha el 6 de noviembre de 2026 sobre el sitio real y siete reportes de muestra (n.° 42, 179, 203,
251, 270 y 271).

## 1. Descubrimiento de reportes

- **Decisión**: recorrer el listado `/categorias_de_documentos/reportes/page/N/` (120 páginas) y
  leer cada tarjeta (`card-title`, fecha en `card-subtitle` y enlace). En las actualizaciones
  basta con recorrer páginas hasta encontrar un documento ya conocido.
- **Por qué**: cada tarjeta trae el enlace directo al archivo, sea cual sea su nombre. Es la misma
  fuente para todos los años y no depende de adivinar URL.
- **Alternativas descartadas**: armar la URL a partir del número y el mes (el método anterior,
  frágil); el sitemap del sitio (solo tiene 76 páginas generales); la API REST de WordPress (el
  tipo de contenido "documentos" no está expuesto y la búsqueda de medios es incompleta).

## 2. Reportes que faltan en el listado

- **Decisión**: para los 42 números que faltan, consultar la API CDX del Wayback Machine sobre la
  web antigua (`defensoria.gob.pe/modules/Downloads/conflictos/*`) y descargar la copia archivada.
- **Por qué**: una consulta de prueba devolvió 226 PDF archivados que cubren casi todo el hueco
  del 63 al 91 (2009–2011). Es una fuente pública y conserva el archivo original.
- **Alternativas descartadas**: escribir a la Defensoría (no da tiempo para la demo); usar bases
  compiladas por terceros (no son la fuente original).

## 3. Formatos

- **Decisión**: PDF con texto mediante PyMuPDF (ya instalado); HTML (reporte 271 en adelante)
  mediante BeautifulSoup (ya instalado); zip de 2004 y 2005 con `zipfile` de la librería
  estándar. OCR con PaddleOCR solo como respaldo para páginas sin texto.
- **Por qué**: las siete muestras tienen texto en el 100% de sus páginas. El OCR es lento y no
  hace falta para las muestras.
- **Alternativas descartadas**: pdfplumber (el extractor anterior); funciona, pero PyMuPDF es
  más rápido y también detecta tablas con `find_tables()`, así que basta con una sola librería.

## 4. Identidad del reporte

- **Decisión**: leer el número y el mes de la primera página ("N.° 271 · SETIEMBRE 2026",
  "Reporte Mensual de Conflictos Sociales N.° 179") con expresiones regulares. El título de la
  tarjeta queda como respaldo.
- **Por qué**: los nombres de archivo no siguen ninguna regla (`10.pdf`,
  `conflictos_sociales42.pdf`).

## 5. Validación contra los totales

- **Decisión**: usar la frase del resumen "Se da cuenta de N conflictos sociales: A activos (…) y
  L latentes" como verdad de referencia del reporte.
- **Hallazgo**: aparece igual en 2019, 2021, 2025 y 2026. En 2007 no aparece con esa forma, así
  que para los reportes antiguos se buscarán los totales en el cuadro de estadísticas.
- **Regla**: los casos activos son las fichas con hechos del mes más la lista de "activos sin
  hechos". Los latentes salen de su propia lista. En 2019 y 2021 el número de fichas coincide
  exactamente con los activos (133 y 145). En 2025 y 2026 las fichas son solo los activos con
  hechos, y el resto está en la lista aparte.

## 6. Enlace de casos entre meses

- **Decisión**: desde 2026 las fichas traen "Código" (113 en el reporte 270) y se enlaza por
  código. Antes de 2026 se enlaza por nombre normalizado del caso más el departamento, con la
  similitud de `difflib` (librería estándar). Por debajo de un umbral, el enlace va a revisión.
- **Por qué**: el código es exacto. Para lo anterior, la similitud de texto alcanza porque el
  nombre del caso casi no cambia de un mes a otro.
- **Contraste**: la base de conflictos 2004–2024 del repositorio público Violencia_BD trae un
  código por caso. Sirve para medir cuántos enlaces acierta Tremor, no como fuente.

## 7. Almacenamiento

- **Decisión**: una sola base SQLite (`datos/tremor.db`) y los archivos originales en
  `datos/crudos/defensoria/<huella>.<ext>`, nombrados por la huella SHA-256 de su contenido.
- **Por qué**: está en la librería estándar, no requiere servidor y la huella evita volver a
  descargar o guardar dos veces el mismo archivo.

## 8. Cortesía con el sitio

- **Decisión**: una solicitud a la vez, con pausa de 0,7 s, tres reintentos y un User-Agent de
  navegador. La primera corrida completa del listado tomó unos 3 minutos.
