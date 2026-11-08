# Implementation Plan: Modelo de alerta (005)

**Spec**: `spec.md` · **Literatura**: `literatura.md`

## Enfoque

Un solo módulo, `tremor/modelo.py`, que lee `datos/tremor.db` y escribe tablas nuevas en la misma base.

1. `niveles(con)`: eventos de todas las fuentes → nivel 0–4 por distrito y mes (tabla `nivel_mes`, solo > 0).
2. `panel(con)`: matriz distrito × mes (2010-01 → último reporte de la Defensoría). Variables:

| Grupo | Variables |
|---|---|
| Historia | medidas de fuerza en el mes, 3, 12 y 36 meses; protestas de cualquier tipo en 12 meses; crisis en 36 meses; meses desde la última medida de fuerza |
| Casos Defensoría | casos activos, latentes y en diálogo en el mes |
| Contagio | medidas de fuerza en 3 meses en el resto de la provincia y del departamento |
| Extracción | unidades mineras, pasivos, lotes (explotación, exploración), oleoducto; concesiones y concesiones metálicas nuevas (año anterior) |
| Economía | variación en 12 meses del cobre y del oro (BCRP); PIM de canon per cápita del año; ejecución del canon del año anterior |
| Desarrollo | IDH del año anterior; pobreza distrital 2018; pobreza departamental ENAHO del año anterior |
| Política | meses a la próxima elección municipal; margen, listas efectivas y participación de la última elección |

3. `entrenar`: ingenuo (fuerza el último mes, desempate por 12 meses), `LogisticRegression` (log1p, mediana,
   escala, `class_weight=None`) y `HistGradientBoostingClassifier`. Corte: objetivo ≤ 2023-12 entrena.
4. Métricas en prueba → `modelo_metrica`. El mejor por precisión@20 genera `alerta` (reentrenado con todo).
5. Razones: oclusión de cada variable con su mediana de entrenamiento; las 3 que más suben la probabilidad.

## Constitución

- Datos reales y fuentes citadas: cada variable viene de una tabla con su `fuente`.
- Código mínimo (ponytail): pandas + numpy + scikit-learn, sin dependencias nuevas.
- Prueba: `tests/test_prensa.py::test_niveles_y_rezagos` con un caso hecho a mano.
