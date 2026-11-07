# Tareas: Recolector de reportes de la Defensoría

**Entrada**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md),
[contracts/cli.md](contracts/cli.md)

Formato: `[P]` se puede hacer en paralelo; `[H#]` es la historia de la spec.

## Fase 1: Preparación

- [x] T001 Crear `requirements.txt` con `requests`, `pymupdf`, `beautifulsoup4` y `pytest`
- [x] T002 Crear `tremor/__init__.py`, `tremor/defensoria/__init__.py` y la carpeta `datos/`
      (ignorada salvo `datos/exportes/`)

## Fase 2: Base común (bloquea todo lo demás)

- [x] T003 `tremor/db.py`: conexión y creación del esquema completo de
      [data-model.md](data-model.md), con claves únicas para que nada se duplique
- [x] T004 `tremor/defensoria/__main__.py`: subcomandos del contrato, con registro en `corrida`

## Fase 3: Historia 1, catálogo (P1) 🎯 primer entregable

- [x] T005 [H1] `catalogo.py`: recorrer el listado y guardar cada tarjeta de conflictos en
      `documento` (modo completo y modo incremental, que se detiene en lo ya conocido)
- [x] T006 [H1] `catalogo.py`: para cada número faltante, buscar en la API CDX del Wayback
      Machine y registrar la fuente probada
- [x] T007 [H1] `catalogo.py`: descargar con reintentos, guardar por huella SHA-256 y abrir los
      zip de 2004 y 2005
- [x] T008 [H1] Comando `estado` con catálogo, descargados y faltantes

**Punto de control**: `descubrir --completo` y `estado` muestran al menos 249 reportes (CE-001).
Resultado (6 nov): 271 de 271, con 289 documentos (201 del listado, 64 del Wayback y 24 de los zip).
Al leer las portadas, el periodo de los 249 reportes mensuales (23 a 271) calza con su número.

## Fase 4: Historia 2, identidad por contenido (P1)

- [x] T009 [P] [H2] fragmentos reales de portadas (2004, 2007, 2009, 2012, 2019 y 2026) dentro de `tests/test_defensoria.py`
- [x] T010 [H2] `catalogo.py`: leer número y mes de la portada (PDF y HTML) y resolver los
      duplicados encontrados en el catálogo: copias del mismo reporte con otro nombre (46, 55,
      78, 82, 87, 125, 152, 156, 169), edición especial aparte (35), reporte partido en dos
      archivos que hay que unir (155: `-1.pdf` y `-2.pdf`) y el resumen anual de 2005
      (`conflictos_2005.pdf`), que no es mensual
- [x] T011 [H2] Prueba en `tests/test_defensoria.py` para las cuatro portadas

## Fase 5: Historia 3, mapa de secciones (P1)

- [x] T012 [H3] `extraer.py`: dividir cada reporte en secciones por sus títulos y asignarlas a
      las canónicas; lo que no calce queda como `no_mapeada`
- [x] T013 [H3] Revisar el mapa en un reporte por época (2007, 2016, 2019, 2021, 2025 y 2026) y
      ajustar los patrones hasta que no queden secciones clave sin mapear

## Fase 6: Historia 4, casos mes a mes (P1)

- [x] T014 [P] [H4] `tests/fragmentos/`: frase de totales (2019, 2025, 2026) y una ficha completa
      de 2021 y otra de 2026
- [x] T015 [H4] `extraer.py`: leer los totales del resumen
- [x] T016 [H4] `extraer.py`: extraer fichas por etiquetas (código, tipo, ubicación, fase,
      diálogo, actores, caso y hechos) y las listas de activos sin hechos y de latentes
- [x] T017 [H4] `validar.py`: comparar con los totales y marcar `valido` o `fallido` con el
      detalle
- [x] T018 [H4] `validar.py`: enlazar casos por código y, sin código, por nombre y departamento
      con `difflib`; los dudosos a revisión
- [x] T019 [H4] Pruebas de totales, ficha y enlace

**Punto de control**: el reporte 271 queda `valido` con 193 casos (escenario 4 de la guía).
Resultado final (7 nov): 182 reportes (n.° 90 al 271): 121 `valido`, 60 `aproximado` (±3), 1
`fuente_incompleta` (265) y 0 `fallido`. 1 605 casos enlazados (antes 3 562; ~1 530 códigos oficiales).
Las copias del Wayback de 185, 189, 190 y 198 estaban truncadas en 1 MB; ahora se baja el enlace vivo.
Acciones de protesta: 28 285 filas; 117 de 145 reportes con tabla calzan exacto con lo declarado.
Una segunda corrida tarda 2 s y no agrega nada (CE-006).

## Fase 7: Historia 5, acciones y víctimas (P2)

- [x] T020 [H5] `extraer.py`: tabla de acciones colectivas con `find_tables()` de PyMuPDF y
      lectura por texto como respaldo
- [x] T021 [H5] `extraer.py`: fallecidos y heridos agregados por caso
- [x] T022 [H5] Validar que el número de acciones coincide con el declarado

## Fase 8: Cierre

- [x] T023 `validar.py`: exportar los cuatro CSV del contrato
- [x] T024 Correr todo dos veces y confirmar 0 cambios en la segunda (CE-006)
- [x] ~~T025 Revisión manual de 30 fichas al azar~~ Reemplazada por la validación automática de cada reporte contra sus totales (decisión del 7 nov). Revisión manual de 30 fichas al azar y registrar el resultado en
      `docs/validacion-defensoria.md` (CE-004)
- [x] T026 Actualizar el README (tabla de módulos y cómo correrlo)
- [x] T027 `.github/workflows/defensoria.yml`: correr `python -m tremor.defensoria todo` una vez
      al día (GitHub Actions, gratis). Si hay un reporte nuevo, guardar la base actualizada y los
      CSV; si no, no hacer commit. Como en asi-vota-el-congreso, la base va en una rama `datos`
      para no inflar `main`.

## Dependencias

Fase 1 → Fase 2 → Historia 1 → Historia 2 → Historias 3 y 4 → Historia 5 → Cierre.
T009 y T014 (fragmentos de prueba) se pueden preparar en cualquier momento.
