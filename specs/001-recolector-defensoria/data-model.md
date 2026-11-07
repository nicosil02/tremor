# Modelo de datos: Recolector de reportes de la Defensoría

Base SQLite única: `datos/tremor.db`. Todas las tablas llevan las columnas de trazabilidad que pide
el principio I (URL de origen y página).

## documento
Cada archivo encontrado en una fuente. Un mismo reporte puede tener varios documentos.

| Campo | Tipo | Nota |
|---|---|---|
| url | texto, clave | URL del archivo |
| fuente | texto | `listado`, `wayback` o `zip` |
| titulo | texto | Título de la tarjeta del listado |
| fecha_publicacion | texto ISO | Fecha de la tarjeta |
| formato | texto | `pdf`, `html` o `zip` |
| huella | texto | SHA-256 del contenido; vacío si aún no se descarga |
| reporte_num | entero | Leído de la portada; vacío hasta procesarlo |
| descubierto_en | texto ISO | |

## reporte
Un registro por número de reporte mensual.

| Campo | Tipo | Nota |
|---|---|---|
| num | entero, clave | Número del reporte (1 a 271…) |
| anio, mes | entero | Periodo que cubre, leído de la portada |
| huella | texto | Documento elegido para extraer |
| total, activos, latentes, en_dialogo | entero | Totales declarados en el resumen |
| acciones_declaradas | entero | Total de acciones de protesta declarado |
| estado | texto | `pendiente`, `valido` o `fallido` |
| detalle_validacion | texto | Diferencias encontradas |

## seccion
| Campo | Tipo | Nota |
|---|---|---|
| reporte_num | entero | |
| titulo_original | texto | Como aparece en el reporte |
| canonica | texto | Una de: `resumen`, `estadisticas`, `casos_nuevos`, `fichas_activos`, `activos_sin_hechos`, `latentes`, `resueltos`, `retirados`, `acciones_protesta`, `alertas`, `victimas`, `dialogo`, `acuerdos`, `no_mapeada` |
| pagina_inicio, pagina_fin | entero | |

## caso
| Campo | Tipo | Nota |
|---|---|---|
| id | entero, clave | Interno |
| codigo | texto | Código de la Defensoría cuando existe (`0397-1208`) |
| nombre | texto | Nombre vigente |
| nombres_anteriores | texto | Separados por `;` |
| tipo | texto | Socioambiental, laboral, etc. |
| departamento, provincia, distrito, ubigeo | texto | |

## caso_mes
Un registro por caso y por reporte. Clave: (`caso_id`, `reporte_num`).

| Campo | Tipo | Nota |
|---|---|---|
| estado | texto | `activo` o `latente` |
| con_hechos | booleano | Si tuvo ficha con hechos del mes |
| fase | texto | Temprana, escalamiento, crisis, desescalamiento o acuerdos |
| dialogo | texto | Tal como lo declara la ficha |
| competencia | texto | |
| actores_primarios, actores_secundarios, actores_terciarios | texto | Organizaciones e instituciones, no personas |
| descripcion | texto | |
| hechos_mes | texto | |
| pagina | entero | Página de origen |
| enlace_confianza | real | 1,0 si se enlazó por código |

## accion_protesta
| Campo | Tipo | Nota |
|---|---|---|
| reporte_num | entero | |
| n | entero | Número de orden en la tabla |
| fecha | texto ISO | |
| medida, actores, lugar, demanda | texto | |
| departamento, ubigeo | texto | |
| pagina | entero | |

## victimas
Cifras agregadas, sin nombres: `reporte_num`, `caso_id` (opcional), `fallecidos`, `heridos` y
`pagina`.

## corrida
`id`, `paso`, `inicio`, `fin`, `nuevos`, `errores` y `detalle`.

## Transiciones de estado de `reporte`
`pendiente` → `valido` (los totales cuadran) o `fallido` (no cuadran). Al volver a extraer un
reporte fallido se recalcula su estado. Un reporte `valido` no cambia si su huella no cambia.
