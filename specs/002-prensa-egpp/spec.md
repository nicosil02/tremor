# Feature Specification: Señal de protesta desde la prensa y base histórica de la EGPP

**Feature Branch**: `002-prensa-egpp`

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "002-prensa-egpp: señal de protesta desde la prensa y base histórica de la EGPP, para alertar riesgo de conflicto social alrededor de operaciones extractivas. Histórico EGPP por distrito; prensa amplia y gratuita; codificación con el manual EGPP, incluidas las protestas anunciadas; ubicación precisa del evento; agrupar notas del mismo evento; validar contra la Defensoría y la EGPP."

## Contexto

Tremor es una página que alerta el riesgo de conflicto social alrededor de las operaciones de empresas
extractivas (minería, energía, hidrocarburos, concesiones). El módulo 001 ya da el panel mensual de
casos de la Defensoría (2004–2026). Este módulo agrega dos piezas:

1. **El histórico de protestas por distrito** desde 1980, con la base de la Escuela de Gobierno y
   Políticas Públicas de la PUCP (EGPP), que codificó a mano tres diarios nacionales.
2. **La señal en vivo**: protestas que la prensa reporta día a día, en especial las **anunciadas**
   (un paro convocado para dentro de una semana), que son la alerta temprana que una empresa no
   obtiene de la Defensoría, cuyo reporte sale un mes después.

Ambas piezas deben llegar al nivel de **distrito**, porque es ahí donde se cruzan con las operaciones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Histórico de protestas por distrito (Priority: P1)

El analista de relaciones comunitarias de una minera quiere saber cuántas protestas hubo en los
distritos donde opera, de qué tipo y contra quién, desde 1980 hasta 2025, junto con los casos de la
Defensoría de esos mismos distritos.

**Why this priority**: sin histórico no hay línea de base para el modelo de alerta (módulo 005) ni
contexto en la página. Es la pieza con datos ya existentes y verificados a mano.

**Independent Test**: cargar la base de la EGPP y pedir las protestas de un distrito conocido; el
conteo por año coincide con el del archivo original y cada evento conserva su distrito, actor,
acción, adversario, reclamo y víctimas.

**Acceptance Scenarios**:

1. **Given** el archivo de la EGPP 1980–2025, **When** se carga, **Then** quedan los 25 429 eventos con su
   fecha y su código de distrito, y el conteo por año y por región es igual al del archivo.
2. **Given** la base cargada, **When** se vuelve a cargar el mismo archivo, **Then** no se duplica ningún evento.
3. **Given** la base cargada, **When** se piden los datos para publicar, **Then** solo salen agregados por
   distrito y mes (nunca los eventos uno por uno), por el uso académico de la base.

---

### User Story 2 - Notas de prensa del día sobre protestas (Priority: P1)

Cada día, Tremor junta las notas de prensa peruanas, nacionales y regionales, que hablan de protestas
(paros, bloqueos, huelgas, marchas, tomas, plantones, enfrentamientos, movilizaciones) en cualquier
departamento, sin usar suscripciones pagadas.

**Why this priority**: es la materia prima de la señal en vivo; sin ella no hay alerta temprana.

**Independent Test**: correr la recolección un día y revisar que haya notas de los 25 departamentos o la
mayoría, de varios medios, cada una con su enlace, medio y fecha; correrla otra vez el mismo día no
agrega duplicados.

**Acceptance Scenarios**:

1. **Given** el día de hoy, **When** corre la recolección, **Then** se guardan las notas nuevas con título, medio,
   fecha de publicación, enlace y, cuando el medio es abierto, el texto.
2. **Given** una nota ya guardada, **When** vuelve a aparecer (otro día u otra búsqueda), **Then** no se duplica.
3. **Given** un medio que exige suscripción, **When** su nota aparece, **Then** se guarda solo lo público (título,
   resumen, enlace) y no se intenta entrar con credenciales.

---

### User Story 3 - Codificar cada nota como en la EGPP, con lugar preciso (Priority: P1)

Cada nota se lee y se codifica con las mismas variables del manual de la EGPP: si es una protesta, si
ya ocurrió o está **anunciada**, la fecha del evento, el lugar (región, provincia, distrito y, si la
nota lo dice, la localidad o comunidad), el actor, la acción, el adversario (incluida la empresa, si
se nombra), el reclamo y las víctimas.

**Why this priority**: la alerta depende de saber dónde y cuándo será la protesta, y contra quién.

**Independent Test**: codificar una muestra de notas revisadas a mano y comparar variable por variable.

**Acceptance Scenarios**:

1. **Given** una nota "Comunidades de Chumbivilcas anuncian paro indefinido contra minera desde el 15", **When**
   se codifica, **Then** queda como protesta anunciada, con fecha 15 del mes, distrito o provincia de
   Chumbivilcas (Cusco), actor comunidades campesinas, acción paro, adversario la empresa minera.
2. **Given** una nota que no trata de una protesta (p. ej. un partido de fútbol "paralizado"), **When** se
   codifica, **Then** queda descartada y no genera evento.
3. **Given** una nota que solo dice el departamento, **When** se codifica, **Then** el lugar queda a nivel de
   departamento y se marca la precisión alcanzada (departamento, provincia, distrito o localidad).
4. **Given** una nota ya codificada, **When** se vuelve a procesar, **Then** se reutiliza la codificación guardada
   sin gastar cuota del servicio de lenguaje.

---

### User Story 4 - Un evento, varias notas (Priority: P2)

Varias notas de medios distintos sobre la misma protesta se agrupan en un solo evento, que guarda
todas sus fuentes. Una protesta anunciada que luego ocurre queda como el mismo evento, con la fecha
del anuncio y la de la realización.

**Why this priority**: sin agrupar, una protesta muy cubierta parece diez y la alerta se infla.

**Independent Test**: tomar un día con una protesta muy cubierta y verificar que sus notas forman un
solo evento con todos los enlaces.

**Acceptance Scenarios**:

1. **Given** cinco notas sobre el mismo paro en el mismo distrito y fecha, **When** se agrupan, **Then** queda un
   evento con cinco fuentes.
2. **Given** un paro anunciado para el día 12 y notas del día 12 que lo reportan, **When** se agrupan, **Then**
   queda un evento con su fecha de anuncio y su fecha de realización.
3. **Given** dos paros del mismo gremio en distritos distintos, **When** se agrupan, **Then** quedan como dos eventos.

---

### User Story 5 - Medir la señal antes de usarla (Priority: P2)

Antes de que la prensa alimente la alerta, se mide qué tan bien funciona: qué parte de las protestas
que registra la Defensoría detecta la prensa, con cuántos días de anticipación cuando estaban
anunciadas, y qué tanto coincide la codificación automática con la manual de la EGPP.

**Why this priority**: es el principio de la constitución "medir antes de avanzar" y la cifra central
del pitch (cuántos días antes avisa Tremor).

**Independent Test**: correr la medición sobre el último mes con reporte de la Defensoría y publicar
las cifras tal como salen.

**Acceptance Scenarios**:

1. **Given** las protestas de la Defensoría de un mes y los eventos de prensa del mismo mes, **When** se
   comparan, **Then** se informa el porcentaje de protestas de la Defensoría que la prensa detectó y la
   anticipación (días entre el primer anuncio y la protesta) de las que estaban anunciadas.
2. **Given** una muestra de notas de 2025 que también están en la EGPP, **When** se comparan, **Then** se informa
   precisión, exhaustividad, F1 y kappa por variable.

---

### Edge Cases

- Una nota menciona varias protestas en lugares distintos (un "paro nacional" con focos en cinco regiones): se codifica un evento por lugar mencionado.
- Un lugar con nombre repetido en varios departamentos (p. ej. "San Juan"): se usa el contexto de la nota (provincia o departamento); si no alcanza, se deja al nivel que sí es seguro.
- Fechas relativas ("mañana", "el próximo lunes", "desde el 15"): se resuelven a partir de la fecha de publicación de la nota.
- Una protesta anunciada que se suspende o se levanta: el evento queda marcado como suspendido si una nota posterior lo dice.
- El servicio de lenguaje alcanza su límite diario: lo pendiente queda en cola para el día siguiente, sin perder notas.
- Notas en las que el medio es un agregador o una red social sin texto propio: se guardan, pero no cuentan como fuente independiente al agrupar.
- Distritos creados después del año del evento de la EGPP: se mantiene el código de distrito vigente más cercano y se anota.

## Requirements *(mandatory)*

### Functional Requirements

**Histórico EGPP**

- **FR-001**: El sistema DEBE cargar la base de protestas de la EGPP desde el archivo entregado por la EGPP, con todas sus variables, a la misma base de datos del proyecto.
- **FR-002**: Cada evento de la EGPP DEBE quedar con su código de distrito oficial (ubigeo), de modo que se pueda cruzar con los casos de la Defensoría y con las operaciones.
- **FR-003**: La carga DEBE ser idempotente: cargar dos veces el mismo archivo no duplica eventos; cargar una versión más nueva agrega solo lo nuevo.
- **FR-004**: Los eventos individuales de la EGPP NO DEBEN publicarse ni subirse al repositorio; solo se publican agregados por distrito y mes.

**Recolección de prensa**

- **FR-005**: El sistema DEBE buscar a diario notas de prensa peruanas sobre protestas en cada departamento, con las palabras de acción del manual de la EGPP, en fuentes públicas y gratuitas.
- **FR-006**: Cada nota DEBE guardar medio, título, fecha de publicación, enlace, fecha de descarga y, si el medio es abierto, el texto.
- **FR-007**: Una nota se identifica por su contenido (medio, fecha y titular), no solo por su enlace; la misma nota no se guarda dos veces.
- **FR-008**: El sistema NO DEBE usar credenciales de suscripción ni saltarse muros de pago.

**Codificación**

- **FR-009**: Cada nota DEBE codificarse con las variables del manual de la EGPP: es protesta o no, estado (anunciada, ocurrida, suspendida), fecha del evento, región, provincia, distrito, localidad, actor, acción, adversario, empresa nombrada, reclamo, heridos, muertos y detenidos.
- **FR-010**: El lugar DEBE llevarse a código de distrito cuando la nota lo permita, y registrar la precisión alcanzada (departamento, provincia, distrito, localidad).
- **FR-011**: Primero reglas y después el servicio de lenguaje: un filtro por palabras descarta lo que claramente no es protesta antes de gastar cuota, y varias notas viajan en una misma solicitud.
- **FR-012**: Cada codificación DEBE guardarse junto al texto que la produjo, de modo que volver a correr no gaste cuota.
- **FR-013**: Los actores se registran por su rol u organización, nunca por el nombre de una persona.

**Agrupación**

- **FR-014**: Las notas que hablan de la misma protesta (mismo lugar, fecha cercana, mismo actor y acción) DEBEN agruparse en un evento con todas sus fuentes.
- **FR-015**: Un evento anunciado y su realización DEBEN quedar unidos, con ambas fechas.

**Validación**

- **FR-016**: El sistema DEBE comparar los eventos de prensa con la tabla de protestas de la Defensoría del mismo mes e informar el porcentaje detectado y la anticipación de los anunciados.
- **FR-017**: El sistema DEBE comparar la codificación automática con la manual de la EGPP en eventos comunes e informar precisión, exhaustividad, F1 y kappa por variable.
- **FR-018**: Las cifras de validación se publican tal como salen.

### Key Entities

- **Evento histórico (EGPP)**: una protesta reportada por la prensa entre 1980 y 2025 y codificada a mano; fecha, distrito, actor, acción, adversario, reclamo, víctimas, fuerza estatal y diario.
- **Nota de prensa**: una publicación de un medio; medio, titular, fecha, enlace, texto si es abierto, fecha de descarga.
- **Codificación**: lo que una nota dice de una protesta, con las variables del manual de la EGPP y la precisión del lugar.
- **Evento de prensa**: una protesta identificada a partir de una o más notas; estado (anunciada, ocurrida, suspendida), fecha del anuncio, fecha del evento, distrito y sus fuentes.
- **Distrito**: la unidad territorial oficial (ubigeo) que une la EGPP, la Defensoría, la prensa y, más adelante, las operaciones extractivas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los 25 429 eventos de la EGPP quedan cargados y al menos el 95% tiene distrito válido; el conteo por año coincide con el archivo original.
- **SC-002**: Una semana de recolección trae notas de al menos 20 de los 25 departamentos y de al menos 30 medios distintos.
- **SC-003**: En una muestra revisada a mano, la decisión "es protesta / no es protesta" acierta en al menos el 90% de las notas, y el distrito es correcto en al menos el 80% de las que lo mencionan.
- **SC-004**: La prensa detecta al menos la mitad de las protestas que registra la Defensoría en el mismo mes; se informa cuántas de ellas aparecieron antes como anunciadas y con cuántos días de anticipación (mediana).
- **SC-005**: La operación diaria no supera el límite gratuito del servicio de lenguaje y no tiene costo.
- **SC-006**: Volver a correr la recolección y la codificación de un día ya procesado no agrega registros ni consume cuota.

## Assumptions

- La base de la EGPP (`protestas_1980-2025.xlsx`, versión de diciembre de 2025) la entrega el autor, que colabora con la EGPP; se usa solo con fines académicos y vive solo en la máquina del autor y en la base local, no en el repositorio.
- La fuente de prensa principal es un agregador público de noticias (Google News en su versión RSS), que cubre medios nacionales y regionales y permite buscar por departamento; solo cubre semanas recientes, así que el histórico largo viene de la EGPP y de la Defensoría.
- El servicio de lenguaje es gratuito (Groq con un modelo abierto, mediante un endpoint compatible con OpenAI configurable por variables de entorno), con un límite cercano a 1 000 solicitudes al día.
- El catálogo oficial de distritos (ubigeo del INEI) es público y se usa para llevar los nombres de lugares a códigos.
- El cruce con las operaciones extractivas (concesiones, unidades mineras, lotes) es parte del módulo 004; este módulo solo garantiza que todo quede a nivel de distrito.
- La alerta y la página quedan para los módulos 005 y 006.
