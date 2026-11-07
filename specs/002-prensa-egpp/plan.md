# Implementation Plan: Señal de protesta desde la prensa y base histórica de la EGPP

**Branch**: `002-prensa-egpp` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-prensa-egpp/spec.md`

## Summary

Dos piezas que llegan al distrito (ubigeo):

1. **EGPP → perfil de conflictividad por distrito.** Se cargan los 25 429 eventos a una base local
   aparte (`datos/egpp.db`, nunca publicada), se clasifica cada evento en *socioambiental-extractivo*,
   *laboral minero* u *otro*, se extrae la operación o empresa nombrada, y se publica solo el perfil
   agregado por distrito (`perfil_distrito_egpp.csv`, versionado en el repo).
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

**Storage**: `datos/tremor.db` (pública, en la rama `datos`) para prensa, codificaciones y eventos;
`datos/egpp.db` (local, nunca publicada) para los eventos de la EGPP.

**Testing**: pytest, como en 001: pruebas con textos y titulares cortos, sin red.

**Target Platform**: máquina del autor (carga EGPP) y GitHub Actions (prensa diaria).

**Project Type**: CLI (`python -m tremor.egpp`, `python -m tremor.prensa`).

**Performance Goals**: corrida diaria de prensa < 15 min; carga y perfil de la EGPP < 2 min.

**Constraints**: costo cero; < 1 000 solicitudes/día al LLM (objetivo: < 100); sin credenciales de
suscripción; eventos EGPP no publicados.

**Scale/Scope**: ~25 dptos × 8 palabras ≈ 200 consultas RSS/día; ~1 000–2 000 titulares/día antes del
filtro; validación retro de un mes ≈ 25 × 30 consultas.

## Constitution Check

| Principio | Cómo se cumple |
|---|---|
| I. Fuentes públicas y trazables | Cada nota guarda medio, titular, fecha, enlace y fecha de descarga; cada evento, sus notas. Actores por rol (categorías EGPP); los textos libres de la EGPP no se publican. La EGPP es de uso académico y no se redistribuye. |
| II. Medir antes de avanzar | `prensa validar` publica exhaustividad y anticipación contra la Defensoría, y precisión, exhaustividad, F1 y kappa contra la EGPP, tal como salen. El perfil se verifica con SC-001a. |
| III. Costo cero, sin proveedor fijo | Groq gratis vía `LLM_BASE_URL/LLM_MODEL/LLM_API_KEY`; reglas antes que LLM (filtro y ubigeo por reglas); caché por contenido (`llm_cache`). |
| IV. Incremental e idempotente | Nota identificada por hash de medio + titular normalizado; `INSERT OR IGNORE`; la codificación se guarda por nota y versión del prompt. |
| V. Identidad por contenido | Ídem: no se usa el enlace de Google (cambia) como identidad. |
| VI. Simple | Un paquete `tremor/prensa` de 4 archivos, `tremor/egpp.py`, `tremor/lugares.py`, `tremor/llm.py`. Sin SDK ni frameworks. |

**Resultado**: pasa, con una excepción justificada (abajo).

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
├── egpp.py               # cargar xlsx → datos/egpp.db; perfil → datos/perfil_distrito_egpp.csv
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

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Segunda base SQLite (`datos/egpp.db`) frente a "una sola base" (VI) | La EGPP es de uso académico: sus eventos no pueden terminar en `tremor.db`, que se publica en la rama `datos` | Tablas EGPP dentro de `tremor.db`: basta con publicar la base local una vez (como el 7 nov) para redistribuirla sin querer |
| `perfil_distrito_egpp.csv` versionado en `main` (excepción a `datos/*` en `.gitignore`) | El workflow reconstruye la rama `datos` como huérfana en cada corrida y GitHub Actions no tiene el archivo de la EGPP | Subirlo a `datos` a mano: el workflow lo borraría al día siguiente |
