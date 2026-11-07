# Contrato: línea de comandos de 002

Desde la raíz del repo; todos idempotentes.

```
python -m tremor.egpp cargar RUTA.xlsx        # → tabla egpp_evento en datos/tremor.db (reemplaza la versión cargada)
python -m tremor.egpp perfil                  # → datos/exportes/perfil_distrito.csv y perfil_distrito_anio.csv
python -m tremor.egpp ranking [--tipo socioambiental_extractivo] [--n 20]   # imprime los distritos más conflictivos

python -m tremor.prensa recolectar [--desde AAAA-MM-DD --hasta AAAA-MM-DD]  # sin fechas: últimas 24 h
python -m tremor.prensa codificar [--max-solicitudes 200]                   # lo que falta, en lotes
python -m tremor.prensa agrupar
python -m tremor.prensa validar [--mes AAAA-MM]                             # contra Defensoría y contra la EGPP
python -m tremor.prensa exportar                                           # datos/exportes/notas.csv, eventos_prensa.csv
python -m tremor.prensa todo                                               # recolectar, codificar, agrupar, exportar
```

## Salida LLM esperada (por titular)

```json
{"id": "a1b2", "es_protesta": true, "estado": "anunciada", "fecha_evento": "2026-11-12",
 "region": "Puno", "provincia": "El Collao", "distrito": "Ilave", "localidad": "puente internacional",
 "sector": "Educativo", "actor": "Docentes colegios", "accion": "Bloqueo de vías",
 "adversario": "Poder Ejecutivo", "empresa": null, "operacion": null,
 "reclamo": "Políticos", "sub_reclamo": "Rechazo de mandatos", "heridos": null, "muertos": null, "detenidos": null}
```

## Salida de `validar`

```
Defensoría 2026-09: 2 512 acciones con provincia; detectadas por prensa 41% (socioambientales 48%)
  anunciadas antes: 18% de las detectadas, anticipación mediana 4 días
EGPP 2025-12: es_protesta P 0.88 R 0.71 F1 0.79; kappa acción 0.62, reclamo 0.55, adversario 0.58, distrito 0.70
```
(cifras ilustrativas; las reales se publican tal como salen)
