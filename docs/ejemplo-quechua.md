# Ejemplo: una radio en quechua, de la voz al castellano

Prueba del 11 de noviembre de 2026 con 60 segundos de una radio de Puno grabada en vivo, en una laptop sin GPU
(`tremor/radio.py`, funciones `mms` y `traducir`).

**1. Transcripción en quechua** (MMS de Meta, `facebook/mms-1b-all`, adaptador quechua Cusco-Collao; 68 s de
cálculo para 60 s de audio):

> ñawpaqninpi sayariykunku paykunan huk ordenanzata mana uyachkankuchu chaymi kamachikun llaqtapa chawpinpi mana
> purinankuta […] moto taxistakunan autoridadkunata mañakuchkanku chay ordenansata holluchinankupaq […] kinsa pachak
> moto takistakunan kanku alexis garcía jerente municipalñataqmi kaynata nirqa

**2. Traducción al castellano** (NLLB-200 600M de Meta, 22 s):

> Y se han parado en el frente de la ciudad porque no escuchan una ordenanza y se les ha ordenado que no se vayan por
> el centro de la población […] los taxistas de motocicletas piden a las autoridades que demuestren que la ordenanza
> funciona […] trescientos motociclistas, Alexis García, gerente municipal, dijo

**3. Lo que entiende el codificador:** un plantón de mototaxistas contra una ordenanza municipal que les prohíbe
circular por el centro; unos trescientos; declaración del gerente municipal. No es contra una minera, así que no sale
como alerta extractiva, pero queda como protesta en la zona.

Límites: la traducción es aproximada (MMS no puntúa y NLLB se confunde con las cifras); sirve para detectar que hay
una protesta, quién y contra qué, no para citar textualmente. Por eso los avisos de radio en quechua y aimara dicen
"según la radio" y llevan la hora para que el equipo escuche el original.
