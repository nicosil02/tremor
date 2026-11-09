# Quickstart / validación: 002

Requisitos: `pip install -r requirements.txt`; `.env` con `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`
(ver `.env.example`); el archivo de la EGPP (descargado de su web).

## 1. EGPP y perfil (US1)

```bash
python -m tremor.egpp cargar "<ruta>/protestas_1980-2025.xlsx"
python -m tremor.egpp perfil
python -m tremor.egpp ranking --tipo socioambiental_extractivo --n 10
```
Esperado: 25 429 eventos (≈220 marcados duplicados), conteo por año igual al archivo (SC-001); el ranking
sin capitales trae Challhuahuacho, Cocachacra, Andoas, Urarinas, Espinar/Velille… (SC-001a). Volver a
cargar no cambia los conteos.

## 2. Prensa de hoy (US2–US4)

```bash
python -m tremor.prensa todo
```
Esperado: notas de ≥20 departamentos y ≥30 medios en una semana (SC-002); correrlo dos veces no agrega
filas ni solicitudes al LLM (SC-006); `datos/exportes/eventos_prensa.csv` con estado, fecha, ubigeo y enlaces.

## 3. Validación (US5)

```bash
python -m tremor.prensa recolectar --desde 2026-09-01 --hasta 2026-09-30
python -m tremor.prensa codificar && python -m tremor.prensa agrupar
python -m tremor.prensa validar --mes 2026-09
python -m tremor.prensa recolectar --desde 2025-12-01 --hasta 2025-12-31 && python -m tremor.prensa codificar && python -m tremor.prensa agrupar
python -m tremor.prensa validar --mes 2025-12
```
Esperado: cifras de SC-003/SC-004 publicadas en el README tal como salen.

## 4. Pruebas

```bash
python -m pytest
```
