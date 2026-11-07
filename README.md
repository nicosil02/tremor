# Tremor

**Escuchamos el temblor antes del conflicto.**

> En construcción. Proyecto final de la Diplomatura Q-Lab PUCP (issue #204). Cada sección se
> completa a medida que avanza el proyecto.

## 1. One-liner

Avisamos a mineras, energéticas y concesionarias qué conflicto social va a escalar cerca de sus
operaciones, días antes, leyendo la Defensoría y los diarios y escuchando las radios locales (en
español, quechua y aymara) con IA.

## 2. Founder

Nicolás Silva Andújar. Pendiente.

## 3. Problema

Pendiente. Notas de las tres conversaciones en [`docs/research/`](docs/research/).

## 4. Solución e insight

Pendiente.

## 5. Why now

Pendiente.

## 6. Demo

Pendiente: URL, cómo correrlo, tres capturas, diagrama de arquitectura y modelos usados.

## 7. Modelo de negocio

Pendiente.

## 8. Herramientas del curso

Pendiente.

## 9. Qué hizo el agente

Pendiente.

## Cómo se trabaja este repo

El proyecto usa [Spec Kit](https://github.com/github/spec-kit). Las reglas están en
[`.specify/memory/constitution.md`](.specify/memory/constitution.md) y cada módulo tiene su
especificación en [`specs/`](specs/).

| Módulo | Especificación | Estado |
|---|---|---|
| 001 Recolector de la Defensoría | [spec](specs/001-recolector-defensoria/spec.md) | Funciona: 271 reportes, panel caso-mes 2012–2026 |

### Módulo 001: recolector de la Defensoría

Junta los 271 reportes mensuales de conflictos sociales (marzo 2004 – septiembre 2026), los
identifica por su portada y extrae de los publicados desde 2012:

- los totales que cada reporte declara de sí mismo (activos, latentes, en diálogo y acciones de protesta);
- una ficha por caso activo y mes (tipo, ubicación, fase, diálogo, actores, hechos del mes), enlazada al
  mismo caso a lo largo de los años por código o, sin código, por parecido de descripción, ubicación y
  actores;
- la tabla de acciones colectivas de protesta (fecha, medida, actores, lugar, demanda);
- fallecidos y heridos por caso.

Cada reporte se compara con sus propios totales y queda marcado `valido`, `aproximado` (±3 casos),
`fuente_incompleta` (el propio PDF trae menos fichas de las que declara) o `fallido`.

```bash
pip install -r requirements.txt
python -m tremor.defensoria todo        # descubre, descarga, identifica, extrae y exporta lo nuevo
python -m tremor.defensoria estado      # catálogo y faltantes
python -m tremor.defensoria validar     # resultado de la validación por reporte
python -m pytest                        # pruebas
```

Los CSV quedan en `datos/exportes/` (`reportes`, `casos`, `caso_mes`, `acciones_protesta`,
`victimas`). Una tarea diaria de GitHub Actions corre el recolector y publica la base en la rama
`datos`.
