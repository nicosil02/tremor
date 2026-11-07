<!--
Sync Impact Report
- Versión: plantilla → 1.0.0 (primera adopción)
- Principios añadidos: I a VI
- Secciones añadidas: Requisitos del proyecto final, Flujo de trabajo
- Pendientes: ninguno
-->

# Constitución de Tremor

Tremor escucha y lee las fuentes públicas del Perú (reportes de la Defensoría del Pueblo, diarios
nacionales y regionales, radios locales) para registrar protestas y conflictos sociales y anticipar
cuáles van a escalar.

## Principios

### I. Solo fuentes públicas y trazables

- Cada dato guardado DEBE llevar su fuente: URL, fecha de descarga y, cuando aplique, página del
  PDF o minuto del audio. Un dato sin fuente no entra a la base.
- Solo se usan fuentes públicas: documentos oficiales publicados, notas de prensa abiertas y
  transmisiones de radio abiertas.
- No se guardan perfiles de personas. Los actores se registran por su rol u organización
  ("Frente de Defensa de X"), nunca por su nombre ni por su voz. No se usan huellas de voz ni
  ningún otro dato biométrico.
- Ninguna clave, credencial ni archivo `.env` real entra al repositorio.

### II. Medir antes de avanzar (no negociable)

Cada módulo tiene un umbral de calidad, y no se construye el siguiente sobre uno que no lo pasa:

- **Defensoría:** para cada reporte, los casos extraídos DEBEN sumar los totales que el propio
  reporte declara en su resumen (total, activos, latentes). Un reporte que no cuadra queda
  marcado como fallido y no alimenta el panel.
- **Codificación de protestas:** la medición se hace contra la base de la EGPP PUCP y las
  codificaciones manuales del autor. Se reportan precisión, exhaustividad, F1 y kappa por
  variable.
- **Transcripción:** error por palabra y por carácter medidos sobre muestras transcritas a mano,
  por idioma.
- **Predicción:** se evalúa solo con datos posteriores a los de entrenamiento (corte temporal).

Las cifras se publican tal como salen, sin re-ejecutar para mejorarlas.

### III. Costo cero y sin depender de un proveedor

- Todo DEBE funcionar sin pagar: modelos abiertos, niveles gratuitos de API y la GPU local del
  autor.
- El LLM se llama mediante un endpoint compatible con OpenAI configurable por variables de
  entorno (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`). Cambiar de proveedor NO DEBE exigir
  cambiar código.
- Primero reglas y después LLM: lo que se puede extraer con estructura fija (encabezados, tablas,
  expresiones regulares) no se manda al LLM. El LLM solo se usa para el texto libre.
- Toda respuesta del LLM se guarda en caché por contenido, de modo que volver a correr no gasta
  la cuota.

### IV. Incremental e idempotente

- La primera corrida procesa todo el histórico. Las siguientes procesan solo lo nuevo.
- Correr dos veces el mismo paso NO DEBE duplicar registros.
- El estado de cada paso vive en la base de datos, no en nombres de archivo ni en "el último
  enlace".

### V. Identidad por contenido, no por nombre de archivo

Un documento se identifica por lo que dice (número y mes del reporte en su portada, fecha y
titular de la nota), no por cómo se llama el archivo o la URL. Los nombres de archivo de las
fuentes no son estándar y no se confía en ellos.

### VI. Simple y entendible

- Python, una sola base SQLite y la menor cantidad posible de dependencias.
- No se crean abstracciones para un solo uso.
- El autor DEBE poder explicar y modificar cualquier parte del código.

## Requisitos del proyecto final (issue #204 de d2cml-ai/Data-Science-Python)

Estos requisitos son parte de la definición de terminado del proyecto:

- Repositorio público con `README.md` de nueve partes: one-liner, founder, problema, solución e
  insight, why now, demo (URL, 3 capturas, diagrama, modelos y por qué), modelo de negocio
  (quién paga, precio y costo por usuario), herramientas del curso con sus archivos, y qué hizo
  el agente.
- `LICENSE`, `.env.example` y `.gitignore`.
- Notas de tres conversaciones con usuarios potenciales en `docs/research/`.
- Al menos dos herramientas del curso dentro del producto, no solo para programar.
- Demo con datos reales en una URL pública y video de respaldo de 60 a 90 segundos.
- Commits en varios días, sin un único commit gigante.
- Revisión de secretos antes de cada push (`git log -p` sin `api_key`, `secret` ni `token`).
- Entrega del enlace en el issue hasta el martes 10 de noviembre de 2026 a las 11:59 p. m.

## Flujo de trabajo

- Cada módulo pasa por Spec Kit en este orden: especificación, plan, tareas e implementación.
- Cada módulo tiene un issue, una rama y un pull request que lo cierra. Los commits llevan el
  número del issue, por ejemplo `(#1)`.
- Los commits y los pull requests no mencionan a Claude ni llevan coautoría de Claude. Lo que hizo
  el agente se documenta en la sección correspondiente del README.
- Todo texto para usuarios está en español.

## Gobernanza

Esta constitución prevalece sobre cualquier otra práctica del repositorio. Una enmienda DEBE
explicar qué cambia y por qué, y subir la versión: MAYOR si se elimina o redefine un principio,
MENOR si se añade uno, PARCHE si solo se aclara la redacción. Cada pull request DEBE revisar que
cumple los principios I a VI.

**Versión**: 1.0.0 | **Ratificada**: 2026-11-06 | **Última enmienda**: 2026-11-06
