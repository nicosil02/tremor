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
| 001 Recolector de la Defensoría | [spec](specs/001-recolector-defensoria/spec.md) | Funciona: 271 reportes, panel caso-mes 2004–2026 |

### Módulo 001: recolector de la Defensoría

Junta los 271 reportes mensuales de conflictos sociales (marzo 2004 – septiembre 2026) y los
identifica por su portada. De cada uno extrae:

- los totales que el reporte declara de sí mismo (activos, latentes, en diálogo y acciones de protesta),
  desde 2004;
- una fila por caso y mes, desde 2004: las fichas de los casos activos (tipo, ubicación, fase, diálogo,
  actores, hechos del mes) y las de activos sin hechos y latentes. De 2004 a marzo de 2008, donde el formato
  cambia de mes a mes, cada caso se lee por su número dentro de las secciones por estado y departamento. Cada fila se enlaza al mismo caso a lo largo de los años: por código, por fecha de
  ingreso al registro y por parecido de descripción, ubicación y actores;
- la tabla de acciones colectivas de protesta (fecha, medida, actores, lugar, demanda);
- fallecidos y heridos, enlazados al caso del mes.

Cada reporte se compara con sus propios totales y queda marcado `valido`, `aproximado` (±3 casos),
`fuente_incompleta` (el propio PDF trae menos fichas de las que declara) o `fallido`. Manda el detalle: si se
leyeron todas las fichas y filas que el reporte publica y su resumen declara otra cifra, es `valido` con una
nota. Las protestas se comparan con las filas que trae la tabla, no con las que anuncia el texto.

Resultado (7 nov 2026): 266 de 271 reportes válidos; quedan 4, 5 y 6 (2004, a 1 caso), 265 (publica menos
fichas de las que declara) y el n.° 1 (no declara totales). 1 843 casos seguidos en promedio 25 meses,
~46 500 filas caso-mes, 29 707 acciones de protesta (completas en 160 de 162 reportes con tabla; en el 134
faltan 3 filas cuyos actores bajan a la fila siguiente) y 103 filas de víctimas.

```bash
pip install -r requirements.txt
python -m tremor.defensoria todo        # descubre, descarga, identifica, extrae y exporta lo nuevo
python -m tremor.defensoria estado      # catálogo y faltantes
python -m tremor.defensoria validar     # resultado de la validación por reporte
python -m pytest                        # pruebas
```

Los CSV quedan en `datos/exportes/` (`reportes`, `casos`, `caso_mes`, `acciones_protesta`,
`victimas`). Una tarea diaria de GitHub Actions corre el recolector y publica los CSV y la base
(`tremor.db.gz`, comprimida porque pasa los 100 MB por archivo de GitHub) en la rama `datos`.
