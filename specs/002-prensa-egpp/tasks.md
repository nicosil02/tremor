# Tasks: Señal de protesta desde la prensa y base histórica de la EGPP

**Input**: `specs/002-prensa-egpp/` (plan, spec, research, data-model, contracts/cli.md, quickstart)

Pruebas: una prueba pequeña por lógica no trivial (constitución VI y práctica de 001), sin red.

## Phase 1: Setup

- [x] T001 Agregar `pandas` y `openpyxl` a `requirements.txt`
- [x] T002 [P] Exportar la hoja `Espaciales` del formulario de la EGPP a `tremor/ubigeo.csv` (columnas `ubigeo` de 6 dígitos, `region`, `provincia`, `distrito`; 1 892 filas)
- [x] T003 [P] Exportar las hojas `Acción`, `Actor`, `Adversario` y `Reclamo` del formulario y las listas de sub-reclamo de la base a `tremor/codigos_egpp.json` (acción 29, sector 32, actor ≈105, adversario 15, reclamo 6, sub-reclamo 51)

## Phase 2: Foundational

- [x] T004 `tremor/lugares.py`: cargar `ubigeo.csv`, normalizar nombres (sin tildes, minúsculas) y `resolver(region, provincia, distrito, localidad, pista_departamento)` → `(ubigeo, precision)`; nombres repetidos se desambiguan con provincia/región; si no alcanza, queda en el nivel seguro (research R3)
- [x] T005 [P] `tests/test_lugares.py`: "Ilave" con Puno → 210401; "San Juan" sin pista no resuelve a distrito; "Cusco" solo → precisión departamento
- [x] T006 Tablas nuevas en `tremor/db.py`: `egpp_evento`, `perfil_distrito`, `nota`, `codificacion`, `evento_prensa`, `evento_nota`, `llm_cache` según `data-model.md`

## Phase 3: US1 — Perfil de conflictividad por distrito (P1) 🎯 MVP

Prueba independiente: `python -m tremor.egpp cargar …` y `perfil`; conteo por año = archivo; ranking socioambiental trae Challhuahuacho, Cocachacra, Andoas, Urarinas, Espinar (SC-001a).

- [x] T007 [US1] `tremor/egpp.py` `cargar(ruta)`: leer el xlsx, mapear a `egpp_evento` sin `Comentar_t`; `ubigeo` = `Distrito_id` con 6 dígitos (`1101`→`110101`; `160405`→ provincia `1604` con precisión provincia); `capital_por_defecto` = distrito termina en 01; reemplaza la versión anterior (idempotente)
- [x] T008 [US1] En `cargar`: `tipo_conflicto` (`laboral_minero`, `socioambiental_extractivo`, `otro`) con la regla de research R6, y `operacion` con la regex + alias de R7 sobre `Reclamo_t`, `Comentar_t` e `Institución_2` (se lee `Comentar_t` solo para esto)
- [x] T009 [US1] En `cargar`: marcar `duplicado_de` en eventos con misma fecha, ubigeo, actor, acción 1 y `Reclamo_t` (conserva el de menor id)
- [x] T010 [US1] `perfil()` en `tremor/egpp.py`: tabla `perfil_distrito` y `datos/exportes/perfil_distrito.csv` + `perfil_distrito_anio.csv` con las columnas de `data-model.md`, sin duplicados
- [x] T011 [US1] CLI `python -m tremor.egpp {cargar,perfil,ranking}` (contracts/cli.md); `ranking --tipo --n` excluye capitales por defecto con `--sin-capitales`
- [x] T012 [P] [US1] `tests/test_egpp.py`: `tipo_conflicto` y `operacion` sobre filas de ejemplo (Tía María, huelga minera laboral, marcha docente)
- [x] T013 [US1] Correr sobre el archivo real; verificar SC-001 y SC-001a; exportar en `datos/exportes/` para la rama `datos`

## Phase 4: US2 — Notas de prensa del día (P1)

Prueba independiente: `python -m tremor.prensa recolectar` dos veces; mismas filas.

- [ ] T014 [US2] `tremor/prensa/recolectar.py`: consultas Google News RSS por departamento × palabra (research R4), `when:1d` o `after/before` por día; pausa 1 s; separar " - Medio" del título; `nota.id` = sha1(medio + titular normalizados); `INSERT OR IGNORE`
- [ ] T015 [US2] Filtro por reglas en `tremor/prensa/recolectar.py` (`nota.filtro`): sin palabra de acción, deportes, espectáculos, "marcha blanca", "paro cardiaco"
- [ ] T016 [P] [US2] `tests/test_prensa.py`: parseo de un RSS de ejemplo, identidad estable y filtro

## Phase 5: US3 — Codificar como la EGPP, con lugar preciso (P1)

Requiere `.env` con `LLM_API_KEY`.

- [ ] T017 `tremor/llm.py`: `chat_json(sistema, usuario)` contra `{LLM_BASE_URL}/chat/completions`, `response_format json_object`, temperatura 0, reintento ante 429; caché `llm_cache` por sha256(modelo + versión + entrada); lee `.env` sin dependencias
- [ ] T018 [US3] `tremor/prensa/codificar.py`: lotes de 25 titulares con id, fecha de publicación y departamento de consulta; prompt con la definición de protesta del manual, estado anunciada/ocurrida/suspendida y listas de `codigos_egpp.json`; valor fuera de lista → NULL; `ubigeo` y `precision` con `lugares.resolver`; `tipo_conflicto` con la regla R6; `--max-solicitudes`
- [ ] T019 [P] [US3] `tests/test_prensa.py`: validación de la respuesta (categorías fuera de lista, fechas relativas ya resueltas, lote incompleto) con una respuesta LLM fija

## Phase 6: US4 — Un evento, varias notas (P2)

- [ ] T020 [US4] `tremor/prensa/eventos.py` `agrupar()`: union-find por provincia (o distrito), familia de acción y fecha ±1 (±3 huelga/paro indefinido); `fecha_anuncio`, `estado`, `n_notas`, `n_medios`; reconstruye `evento_prensa` y `evento_nota`
- [ ] T021 [P] [US4] `tests/test_prensa.py`: cinco notas del mismo paro → 1 evento; anunciada + ocurrida → 1 evento con dos fechas; mismo gremio en dos provincias → 2
- [ ] T022 [US4] CLI `python -m tremor.prensa {recolectar,codificar,agrupar,validar,exportar,todo}` en `tremor/prensa/__main__.py`; `exportar` → `datos/exportes/notas.csv`, `eventos_prensa.csv`

## Phase 7: US5 — Medir la señal (P2)

- [ ] T023 [US5] Llenar `accion_protesta.ubigeo` y `departamento` con `lugares.resolver` sobre `lugar` y `actores` (en `tremor/prensa/eventos.py`, reutilizable desde 001)
- [ ] T024 [US5] `validar(mes)` en `tremor/prensa/eventos.py`: exhaustividad contra la Defensoría (provincia, ±1 día), global, por departamento y socioambiental; anticipación mediana de las anunciadas; contra EGPP: P/R/F1 y kappa de acción, reclamo, adversario y distrito
- [ ] T025 [US5] Recolección retro 2026-09 y 2025-12, codificar, agrupar y `validar`; exportar muestra de 100 para revisión a mano (SC-003) en `datos/exportes/muestra_revision.csv`

## Phase 8: Polish

- [ ] T026 Workflow `.github/workflows/defensoria.yml`: `python -m tremor.prensa todo` después de la Defensoría con `LLM_API_KEY` desde secretos; publicar siempre que cambien los CSV
- [ ] T027 [P] README: módulo 002 con cifras reales de validación y cita de la EGPP (Arce 2024; EGPP PUCP 2025)
- [ ] T028 Revisión de secretos (`git log -p` sin `api_key`/`token`) y PR que cierra #46

## Dependencies

Setup → Foundational → US1 (independiente de la prensa) | US2 → US3 → US4 → US5. US1 y US2 pueden ir en paralelo. US3 necesita la clave de Groq.

## Implementation Strategy

MVP = US1 (perfil por distrito, sin LLM). Luego US2–US4 para la señal diaria, y US5 para las cifras del pitch.
