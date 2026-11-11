# Pruebas con usuarios

Dos personas ajenas al desarrollo probaron la app publicada y la landing. Se nombran por su rol. Cada comentario va con
lo que cambió por él.

## 1. Analista sénior del Servicio de Asesoría Empresarial de APOYO Consultoría (10 de noviembre, videollamada)

Probó la app de Bateas en computadora, con el mapa y la ruta, mientras conversábamos (notas en
[`research/02-consultor-asesoria.md`](research/02-consultor-asesoria.md)).

| Lo que dijo | Qué cambió |
|---|---|
| "Al principio entendí que las noticias alimentaban el modelo." No quedaba claro qué era monitoreo y qué era predicción. | La app separa las pestañas **Monitoreo** y **Riesgo**, y Monitoreo dice que lo de hoy no cambia el nivel de riesgo. |
| Son tres riesgos distintos: la tensión social de la zona, un bloqueo contra la operación y los cortes de la carretera que no vienen de un conflicto. "Me gustaría ver estas capas por separado." | Tres indicadores con nombre propio en la app, la ficha de cada distrito y el mapa del país: **Zona**, **Operación** y **Carretera**, cada uno con su nivel y su porqué. La landing los explica con los mismos nombres. |
| Un porcentaje a tres meses sobre una carretera conocida no aporta: "al ojo te digo que ahí puede haber protestas". | En la ruta manda el estado de hoy de cada tramo (SUTRAN, radios y medios); el porcentaje a tres meses pasó a dato secundario. |
| Para los cortes que no son conflicto no hace falta un modelo: "hay cosas tan simples… que es solo consolidar lo que existe". | La capa **Carretera** muestra los cortes de la SUTRAN sin modelo y lo dice: "no es pronóstico". |
| El monitoreo sirve también para la reputación, aunque no sea un conflicto, y las menciones podrían alimentar el modelo. | El índice de menciones y tono se llama **Reputación**, se guarda mes a mes para probarlo como variable cuando haya historia, y dispara un aviso cuando se sale de lo habitual. |

## 2. Pendiente

Segunda prueba por hacer, con una persona de relaciones comunitarias de una minera.
