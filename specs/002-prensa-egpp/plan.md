# Implementation Plan: Señal de protesta desde la prensa y base histórica de la EGPP

**Branch**: `002-prensa-egpp` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-prensa-egpp/spec.md`

## Summary

Dos piezas que llegan al distrito (ubigeo):

1. **EGPP → perfil de conflictividad por distrito.** Se cargan los 25 429 eventos a la misma base
   (`datos/tremor.db`), se clasifica cada evento en *socioambiental-extractivo*, *laboral minero* u
   *otro*, se extrae la operación o empresa nombrada y se arma el perfil por distrito. Se publica con
   la base, citando a la EGPP; no se guarda la columna de comentarios libres (trae nombres de dirigentes).
2. **Prensa en vivo.** Google News RSS por departamento × palabras de acción (titulares), un filtro
   por reglas, codificación en lotes con Groq usando las categorías del libro de códigos de la EGPP
   más el estado *anunciada/ocurrida/suspendida*, lugar resuelto a ubigeo por reglas sobre el
   catálogo, agrupación en eventos y validación contra la tabla de protestas de la Defensoría
   (septiembre 2026) y contra la EGPP (diciembre 2025).

## Technical Context

**Language/Version**: Python 3.12 (el mismo del módulo 001)

**Primary Dependencies**: las ya instaladas (`requests`, `pymupdf`, `beautifulsoup4`) más `pandas` y
`openpyxl`, solo para leer el `.xlsx` de la EGPP. El LLM se llama con `requests` al endpoint compatible
con OpenAI (sin SDK).

**Storage**: una sola base, `datos/tremor.db` (rama `datos`): Defensoría, EGPP, prensa y eventos.

**Testing**: pytest, como en 001: pruebas con textos y titulares cortos, sin red.

**Target Platform**: máquina del autor (carga EGPP) y GitHub Actions (prensa diaria).

**Project Type**: CLI (`python -m tremor.egpp`, `python -m tremor.prensa`).

**Performance Goals**: corrida diaria de prensa < 15 min; carga y perfil de la EGPP < 2 min.

**Constraints**: costo cero; < 1 000 solicitudes/día al LLM (objetivo: < 100); sin credenciales de
suscripción.

**Scale/Scope**: ~25 dptos × 8 palabras ≈ 200 consultas RSS/día; ~1 000–2 000 titulares/día antes del
filtro; validación retro de un mes ≈ 25 × 30 consultas.

## Constitution Check

| Principio | Cómo se cumple |
|---|---|
| I. Fuentes públicas y trazables | Cada nota guarda medio, titular, fecha, enlace y fecha de descarga; cada evento, sus notas. Actores por rol (categorías EGPP); el comentario libre de la EGPP no se guarda. La EGPP se cita como fuente (Arce 2024; EGPP PUCP 2025). |
| II. Medir antes de avanzar | `prensa validar` publica exhaustividad y anticipación contra la Defensoría, y precisión, exhaustividad, F1 y kappa contra la EGPP, tal como salen. El perfil se verifica con SC-001a. |
| III. Costo cero, sin proveedor fijo | Groq gratis vía `LLM_BASE_URL/LLM_MODEL/LLM_API_KEY`; reglas antes que LLM (filtro y ubigeo por reglas); caché por contenido (`llm_cache`). |
| IV. Incremental e idempotente | Nota identificada por hash de medio + titular normalizado; `INSERT OR IGNORE`; la codificación se guarda por nota y versión del prompt. |
| V. Identidad por contenido | Ídem: no se usa el enlace de Google (cambia) como identidad. |
| VI. Simple | Un paquete `tremor/prensa` de 4 archivos, `tremor/egpp.py`, `tremor/lugares.py`, `tremor/llm.py`. Sin SDK ni frameworks. |

**Resultado**: pasa, sin excepciones.

## Project Structure

### Documentation (this feature)

```text
specs/002-prensa-egpp/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/cli.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
tremor/
├── db.py                 # + tablas de prensa (nota, codificacion, evento_prensa, evento_nota, llm_cache)
├── llm.py                # chat JSON contra endpoint OpenAI-compatible, con caché por contenido
├── lugares.py            # catálogo ubigeo (tremor/ubigeo.csv) y nombre → ubigeo con desambiguación
├── ubigeo.csv            # 1 892 distritos INEI 2023
├── codigos_egpp.json     # categorías del libro de códigos (acción, actor, adversario, reclamo)
├── egpp.py               # cargar xlsx → tabla egpp_evento; perfil → tabla y CSV perfil_distrito
└── prensa/
    ├── __main__.py       # CLI: recolectar, codificar, agrupar, validar, exportar, todo
    ├── recolectar.py     # Google News RSS → nota
    ├── codificar.py      # filtro por reglas + LLM en lotes → codificacion (+ ubigeo por lugares.py)
    └── eventos.py        # agrupar en evento_prensa; validar contra Defensoría y EGPP
tests/
├── test_lugares.py
├── test_egpp.py
└── test_prensa.py
.github/workflows/defensoria.yml   # agrega `python -m tremor.prensa todo` (misma base, misma rama datos)
```

**Structure Decision**: un solo proyecto, el mismo paquete `tremor`, como 001. `lugares.py` y `llm.py`
quedan fuera de `prensa/` porque también los usan la EGPP, la Defensoría (ubigeo de `accion_protesta`)
y los módulos 004–005.

## Complexity Tracking

Sin violaciones.
