# Contrato: línea de comandos del recolector

Todos los comandos se corren desde la raíz del repositorio y son idempotentes (principio IV).

```
python -m tremor.defensoria descubrir [--completo]   # listado oficial (+ Wayback para faltantes)
python -m tremor.defensoria descargar                # baja lo que no tiene huella
python -m tremor.defensoria extraer [--num N]        # secciones, fichas, acciones y víctimas
python -m tremor.defensoria validar                  # compara con los totales del resumen
python -m tremor.defensoria exportar                 # CSV en datos/exportes/
python -m tremor.defensoria todo                     # los cinco pasos en orden
python -m tremor.defensoria estado                   # resumen: reportes válidos, fallidos y faltantes
```

## Salida de `estado`

```
Reportes en catálogo: 252 de 271  (faltan: 85, 93, ...)
Descargados: 252   Válidos: 230   Fallidos: 18   Pendientes: 4
Último reporte: 271 (setiembre 2026)
```

## Archivos exportados

| Archivo | Una fila por |
|---|---|
| `datos/exportes/reportes.csv` | reporte, con sus totales y su estado |
| `datos/exportes/casos_mes.csv` | caso y mes |
| `datos/exportes/acciones_protesta.csv` | acción de protesta |
| `datos/exportes/faltantes.csv` | número faltante y fuentes probadas |

Código de salida: 0 si todo terminó, 1 si hubo errores (el detalle queda en la tabla `corrida`).
