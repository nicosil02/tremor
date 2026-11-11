# Pruebas con usuarios

Cuatro personas ajenas al desarrollo probaron la app publicada y la landing. Se nombran por su rol. Cada comentario va con
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

## 2. Analista de una consultora ambiental (11 de noviembre)

Revisó la landing y la app publicadas. Su consultora trabaja con empresas que tienen operaciones en zonas de conflicto.

| Lo que dijo | Qué cambió o qué sigue |
|---|---|
| La página le pareció "bastante de utilidad". | Sin cambios. |
| Las empresas ya tienen seguimiento de medios y social listening, pero cada cosa por separado. Por una tarifa como la de Tremor, que junta el monitoreo y le suma la predicción, estarían dispuestas a pagar. | Confirma la propuesta de valor y el rango de precios de los planes. Lo que se vende es la integración más el pronóstico, no otra herramienta de monitoreo. |
| Lo ideal sería un valor real de las paralizaciones, con cámaras o computer vision. Las cámaras cerca de las operaciones ya detectan gente que se dirige al lugar o tráfico atorado. | Fase siguiente, con presupuesto: leer las cámaras públicas en los puntos de corte de la ruta (conteo de vehículos detenidos y de personas) y, si el cliente lo autoriza, sus propias cámaras. El satélite queda solo para cambios en la operación. |
| Antes de vender, asegurarse de que el producto funciona, e invertir para salir de la demo. | Un piloto pagado con una operación y su ruta, con los aciertos y falsas alarmas medidos al cierre; la radio en vivo, en un servidor propio y no en GitHub Actions. |

## 3. Prueba de experiencia de usuario, persona 1

Recorrió la landing y la demo sin explicación previa.

| Lo que dijo | Qué cambió |
|---|---|
| Al entrar a la demo no se entiende para qué sirve cada parte; recomendó un mini tutorial. | La primera vez que se abre la app sale un recorrido de cinco pasos que explica Monitoreo, Riesgo y País, los tres riesgos y el mapa. Se puede volver a ver con "Ver el recorrido". |

## 4. Prueba de experiencia de usuario, persona 2

Recorrió la landing y la demo sin explicación previa.

| Lo que dijo | Qué cambió |
|---|---|
| No basta con ver los bloqueos o tomas contra la operación: hay que resaltar también las vías de interés de cada operación, porque ahí está el valor adicional. | La ruta de salida de cada unidad es parte central de la app. La pestaña Riesgo muestra la **Carretera** (cortes de hoy en su ruta, según la SUTRAN, las radios y los medios) y cada tramo con su estado; el mapa pinta los distritos de la ruta y los avisos incluyen las protestas que pasan por ella aunque estén lejos de la mina. |

## 5. Pendiente

Una prueba con una persona de relaciones comunitarias de una minera.
