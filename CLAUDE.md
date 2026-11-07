# Tremor: memoria del proyecto

Léelo entero antes de trabajar. Es el estado al **7 nov 2026, noche**. Lo actualiza quien avance.

## 1. Qué queremos

Una página web que **avise del riesgo de conflicto social cerca de operaciones extractivas** (minería,
hidrocarburos, energía, concesiones) en el Perú, días antes, con razones explicables por distrito.

- Es el proyecto final del Diplomado Q-Lab PUCP (Python Intermedio, prof. Alexander Quispe), **issue #204 de
  `d2cml-ai/Data-Science-Python`**.
- Fechas:
  - comentario con el link en el issue hasta el **mar 10 nov 23:59**;
  - presentación el **mié 11 nov**: 3 minutos, 30 s de problema, 2 min de demo y 30 s de negocio.
- La URL pública de la demo vale **8 de 20** puntos.
- Requisitos del issue:
  - 2 herramientas del curso dentro del producto;
  - README en 9 partes, LICENSE, `.env.example` y `.gitignore`;
  - 3 conversaciones con usuarios reales en `docs/research/`, que tiene el autor (no inventarlas);
  - commits en varios días;
  - video de respaldo de 60 a 90 s;
  - ninguna clave en el repo.
- **Decisión del autor:** primero cerrar bien el backend, que termina en el **modelo que predice**, y después
  la página.

## 2. Cómo se trabaja (reglas que no se discuten)

- **Spec Kit:** cada módulo tiene `specs/NNN-*/` con spec, plan y tasks. La constitución está en
  `.specify/memory/constitution.md`. Hay skills `/speckit-*` en `.claude/skills`.
- **Flujo de git:**
  - issue → rama → PR → merge; nunca push directo a `main`;
  - commits con `(#n)`;
  - autor: `git -c user.name="Nicolas Silva" -c user.email="nicolas.silva@pucp.edu.pe" commit ...`.
- **Sin atribución a Claude:** nada de "Generated with Claude Code" ni co-autor en commits ni PRs.
- **Código mínimo** (estilo "ponytail"):
  - reglas antes que LLM;
  - una prueba pequeña por cada lógica que no sea trivial (`python -m pytest -q`, hoy 69 pruebas);
  - mejor borrar que agregar.
- **Una sola base:** `datos/tremor.db` (SQLite). Se publica comprimida en la rama **`datos`**
  (`tremor.db.gz` + CSV); `datos/` no va en `main`.
- **Costo cero.** El LLM va por un endpoint compatible con OpenAI (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`).
  - Hoy es Groq: `openai/gpt-oss-120b`, con `openai/gpt-oss-20b` de respaldo cuando el primero agota su cupo.
  - Cada modelo tiene un cupo de **200 000 tokens por día**, unas 200 notas.
  - Todo queda en la caché `llm_cache`: volver a correr no gasta cuota.
- **Privacidad:**
  - los actores se nombran por rol, nunca a personas;
  - no se guarda `Comentar_t` de la EGPP;
  - no se lee Facebook de forma automática (condiciones de Meta).
- **Seguridad:**
  - la clave de Groq va solo en `.env` (gitignored) y en el secreto `LLM_API_KEY` de GitHub; nunca se imprime;
  - no abrir `Credenciales.docx` (viene en el zip de la EGPP).
- **Preguntar antes de hacer algo hacia afuera:** push a `datos`, publicar, comentar en issues.

## 3. Arranque en otra máquina

```bash
git clone https://github.com/nicosil02/tremor && cd tremor && git checkout 002-prensa-egpp
pip install -r requirements.txt
cp .env.example .env        # y pegar LLM_API_KEY=gsk_... (la misma clave de Groq; no está en el repo)
mkdir -p datos && git fetch origin datos && git show origin/datos:tremor.db.gz | gunzip > datos/tremor.db
python -m pytest -q         # 69 pasan
```

En Windows sin `gunzip`:
`python -c "import gzip,shutil;shutil.copyfileobj(gzip.open('tremor.db.gz'),open('datos/tremor.db','wb'))"`,
después de `git show origin/datos:tremor.db.gz > tremor.db.gz`.

La base trae todo, también la EGPP, así que no hace falta el xlsx original. Al abrir Claude Code en esta
carpeta, aprobar el servidor MCP `tremor` (`.mcp.json`).

## 4. Qué hay en la base (7 nov)

| Tabla | Filas | De dónde | Comando |
|---|---|---|---|
| `reporte`, `caso`, `caso_mes`, `accion_protesta`, `victimas` | 271 reportes, 1 843 casos, 46 470 caso-mes, 29 710 acciones | Defensoría, reportes mensuales 2004–2026 | `python -m tremor.defensoria todo` |
| `egpp_evento`, `perfil_distrito`, `perfil_distrito_anio` | 25 429 eventos, 812 distritos | Base de protestas EGPP PUCP 1980–2025 (citada: Arce 2024; EGPP 2025) | `python -m tremor.egpp cargar <xlsx>`, `perfil`, `ranking` |
| `nota`, `codificacion`, `evento_prensa`, `evento_nota`, `llm_cache` | 1 469 notas, 256 codificadas (quedan 92), 35 eventos | 55 feeds RSS + Google News; codifica Groq con el manual EGPP | `python -m tremor.prensa todo` (o recolectar, codificar, agrupar, validar --mes, exportar) |
| `sutran_alerta` | 28 (se acumulan) | API pública `api.sigea.sutran.gob.pe/public/alerts`: solo da las vigentes | `python -m tremor.sutran` |
| `mef_municipal` | 28 091 (≈1 890 municipalidades × 2012–2026) | Consulta Amigable del MEF: presupuesto total y rubro 18 (canon, sobrecanon, regalías) | `python -m tremor.territorio mef` |

Archivos que acompañan a la base:
- `tremor/fuentes_facebook.csv`: 158 páginas para vigilar a mano, por departamento;
- `tremor/ubigeo.csv`: catálogo de los 1 892 distritos (INEI 2023);
- `tremor/codigos_egpp.json`: listas cerradas de acción, actor, adversario y reclamo.

**MCP** (`python -m tremor.mcp_server`):
- `buscar_lugar`;
- `perfil_distrito`;
- `ranking`;
- `consulta_amigable`: el MEF libre, con la URL como fuente; el método viene del MCP de Noelia León
  (`NoeliaLRuiz/mcp-consulta-amigable`).

**Workflow** `.github/workflows/defensoria.yml`:
- corre cada 4 h: Defensoría → SUTRAN → prensa → perfil EGPP, y publica en `datos`;
- **solo corre desde `main`**: se activa al fusionar el PR de 002;
- el secreto `LLM_API_KEY` ya está en GitHub.

## 5. Hallazgos que guían el diseño

- **EGPP:**
  - cuando no sabe el distrito, codifica la capital: el 64% de los eventos cae en un distrito "..01". Los rankings
    excluyen las capitales;
  - no registra protestas anunciadas;
  - tiene cerca de 1/5 de las acciones de la Defensoría de 2022–25;
  - el 65% de los conflictos socioambientales nombra una operación;
  - el 74% de "Mineros" son conflictos laborales: se separan `socioambiental_extractivo` y `laboral_minero`;
  - focos sin capitales: Cocachacra (Tía María, 84), Challhuahuacho (Las Bambas, 75), Andoas (39),
    Desaguadero (38), Capacmarca y Velille (27), Urarinas (25).
- **Validación de la prensa, diciembre 2025, parcial** (quedan notas sin codificar):
  - detecta el 13% de las 242 acciones de la Defensoría;
  - 5 de las detectadas estaban anunciadas, con una anticipación mediana de 5 días;
  - encuentra el 24% de los eventos de la EGPP;
  - kappa: acción 0.67, reclamo 1.0, distrito 0.43.
- **Errores del LLM ya corregidos con reglas:**
  - tomaba como peruanas protestas de otros países: se descartan los dominios extranjeros;
  - copiaba el departamento de la búsqueda: si la nota no lo nombra, la protesta queda sin lugar.
- **Canon:** Challhuahuacho pasó de casi S/ 0 (2012) a S/ 95 millones (2024), y llegó a depender de él en un 88%
  en 2020. San Marcos (Antamina) dependía en un 97% en 2012.
- **Huecos de la Defensoría:**
  - **ningún caso tiene ubigeo** (0 de 1 843);
  - la **fase** solo se leyó en 77 de 46 470 caso-mes;
  - el **reporte 271** (HTML) no tiene sus acciones de protesta leídas.

## 6. Pasos que siguen (en este orden)

**A. Cerrar 002, rama `002-prensa-egpp`, issue #46**
1. Terminar de codificar las 92 notas pendientes cuando se renueve el cupo de Groq:
   `python -m tremor.prensa codificar --max-solicitudes 400`, luego `agrupar` y `validar --mes 2025-12`.
2. Exportar la muestra de 100 notas para revisión a mano (`datos/exportes/muestra_revision.csv`, T025). La revisa
   el autor.
3. README del módulo 002 con las cifras y la cita de la EGPP (T027).
4. Revisar que no haya secretos (`git log -p | grep -i "gsk_\|api_key"`), abrir el PR que cierra #46 y fusionarlo.
   Eso activa el workflow.
5. El autor revisa las 26 páginas de Facebook con confianza "media" (columna `origen`).

**B. Completar la Defensoría (módulo 001)**
1. Ubicar los casos: `caso.ubigeo` con `lugares.resolver` sobre `departamento`, `provincia`, `distrito` y
   `ubicacion`, como `ubicar_defensoria` en `tremor/prensa/eventos.py`.
2. Leer bien la **fase** de cada caso-mes (temprana, escalamiento, crisis, desescalamiento, diálogo). Es
   probablemente el mejor predictor.
3. Leer las acciones de protesta del reporte 271 (HTML).

**C. Perfil territorial del distrito** (`tremor/territorio.py`). Cada variable va con su año, para no usar un dato
publicado después del mes que se predice.
1. ✅ MEF: canon y presupuesto municipal.
2. BCRP: precio mensual del cobre y del oro, y producción minera mensual por departamento (series `RD12957DM` y
   similares; servidor MCP del autor en `agente-socioeconomico-peru/tarea_4/mcp/server.py`). Llamar la API
   directo desde el código.
3. ENAHO: pobreza por departamento y año desde 2004 (skills del autor en `enaho-skills` y
   `agente-socioeconomico-peru`). Pobreza sobre miembros con `p204==1`.
4. Distrito:
   - Mapa de pobreza distrital del INEI e IDH del PNUD;
   - Censo 2017: servicios básicos, ruralidad, lengua materna y autoidentificación indígena;
   - comunidades campesinas y nativas (BDPI del Ministerio de Cultura);
   - pasivos ambientales mineros (Minem) y OEFA;
   - RENAMU;
   - ONPE / Infogob.

   **Primero verificar que cada fuente se pueda descargar a nivel distrital.**

**D. Operaciones extractivas (módulo 004):** concesiones y unidades mineras (Ingemmet, Minem) y lotes de
Perupetro, cada una con su distrito y sus coordenadas.

**E. El modelo (módulo 005), el centro del backend**
- Unidad: distrito × mes para entrenar; para la alerta, recálculo cada 4 h.
- Variable objetivo: alguna protesta en los próximos 30 días (Defensoría y EGPP). Variante: escalamiento o
  violencia.
- Variables:
  - estructurales: perfil territorial e historia EGPP;
  - coyunturales: casos activos y su fase, canon del año y su cambio;
  - inmediatas: protestas anunciadas en la prensa y bloqueos de la SUTRAN;
  - espaciales: conflicto en distritos vecinos y operaciones cercanas;
  - calendario.
- Validación temporal: entrenar con los años anteriores a 2024 y probar con 2024–2026. Comparar contra el método
  ingenuo ("hubo protesta el mes pasado") y medir cuántas de las alertas más altas aciertan.
- La prensa y la SUTRAN tienen poca historia: entran como ajuste explicable sobre el riesgo hasta que se acumule.
- La salida tiene que explicarse, por ejemplo: "caso en escalamiento + paro anunciado + canon en caída + 3
  comunidades".

**F. Después:**
- módulo 006: la página, un mapa en Streamlit Cloud con URL pública que lee la rama `datos`;
- módulo 003: radios y YouTube (Whisper / Omnilingual para quechua y aymara);
- los entregables del #204: README en 9 partes, video, comentario en el issue.
