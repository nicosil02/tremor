# Plan de implementación: Recolector de reportes de la Defensoría

**Rama**: `001-recolector-defensoria` | **Fecha**: 2026-11-06 | **Spec**: [spec.md](spec.md)

## Resumen

Un recolector que arma el catálogo de reportes de conflictos sociales desde el listado oficial,
completa los faltantes con el Wayback Machine, descarga cada archivo una sola vez, lo identifica
por su portada, lo divide en secciones, extrae las fichas de casos y las tablas, y valida cada
reporte contra los totales de su propio resumen. Todo con reglas fijas, sin LLM. Detalle de las
decisiones en [research.md](research.md).

## Contexto técnico

**Lenguaje**: Python 3.12

**Dependencias**: `requests`, `pymupdf` y `beautifulsoup4` (las tres ya instaladas). `difflib`,
`sqlite3`, `zipfile` y `hashlib` de la librería estándar.

**Almacenamiento**: SQLite en `datos/tremor.db`; archivos originales en `datos/crudos/defensoria/`.

**Pruebas**: `pytest`, con fragmentos de texto reales como datos de prueba.

**Plataforma**: Windows (laptop del autor) y Linux (GitHub Actions y Streamlit Cloud más adelante).

**Tipo de proyecto**: paquete de Python con línea de comandos ([contrato](contracts/cli.md)).

**Rendimiento**: corrida completa en menos de 30 minutos; actualización mensual en menos de 5.

**Restricciones**: costo cero, una solicitud a la vez al sitio y nada de datos personales.

**Escala**: unos 270 reportes, unos 50.000 registros de caso-mes y unas 40.000 acciones de
protesta.

## Revisión de la constitución

| Principio | Cómo se cumple | Estado |
|---|---|---|
| I. Fuentes públicas y trazables | Cada fila guarda la URL y la página; no se extraen nombres de personas | Cumple |
| II. Medir antes de avanzar | Cada reporte se valida contra sus totales; los fallidos no entran al panel | Cumple |
| III. Costo cero | Sin LLM en este módulo; solo librerías ya instaladas | Cumple |
| IV. Incremental e idempotente | Claves únicas en la base y archivos nombrados por su huella | Cumple |
| V. Identidad por contenido | Número y mes leídos de la portada | Cumple |
| VI. Simple | Cuatro archivos de código y una base | Cumple |

Revisada otra vez después del diseño: sin cambios.

## Estructura del proyecto

### Documentación

```
specs/001-recolector-defensoria/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/cli.md
└── tasks.md
```

### Código

```
tremor/
├── __init__.py
├── db.py                 # conexión SQLite y esquema (data-model.md)
└── defensoria/
    ├── __init__.py
    ├── __main__.py       # línea de comandos (contracts/cli.md)
    ├── catalogo.py       # descubrir, buscar faltantes en Wayback, descargar, leer la portada
    ├── extraer.py        # secciones, fichas, acciones y víctimas por época
    └── validar.py        # totales, enlace de casos y exportes CSV
tests/
├── fragmentos/           # textos reales cortos de portadas, resúmenes y fichas
└── test_defensoria.py
requirements.txt
```

**Decisión de estructura**: un solo paquete `tremor` con un subpaquete por fuente. Los módulos que
vienen después (prensa, radios, riesgo) se suman como `tremor/prensa/`, `tremor/radios/`, etc., y
comparten `db.py`.

## Seguimiento de complejidad

Sin violaciones de la constitución que justificar.
