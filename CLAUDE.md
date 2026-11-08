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
  - una prueba pequeña por cada lógica que no sea trivial (`python -m pytest -q`, hoy 79 pruebas);
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
python -m pytest -q         # 79 pasan
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
| `bcrp_mensual` | 95 series, 25 516 filas, 2004-01 a 2026-10 | API del BCRP: cobre, oro y WTI (PN0165xXM) y producción minera por departamento (grupo RD129xx) | `python -m tremor.territorio bcrp` |
| `enaho_departamento` | 26 × 2004–2025 (`ccdd` '00' = nacional) | ENAHO módulo 34: pobreza y pobreza extrema (factor07 × mieperho). Los 22 años cuadran con la serie oficial del INEI (±0.1) | `python -m tremor.territorio enaho` |
| `distrito_variable` (larga: ubigeo, anio, variable, valor, fuente; anio 0 = foto) | ~370 000 | PNUD IDH 2017–2024 y componentes (1 874 distritos); INEI pobreza 2018 (1 873); INGEMMET catastro minero por año (1 719); MINEM pasivos ambientales (284); OEFA unidades mineras, lotes de hidrocarburos y Oleoducto Norperuano; ONPE elecciones municipales distritales 2006-2022 (margen, listas, número efectivo de listas, participación; ubigeo RENIEC traducido por nombre); Censo 2017 por REDATAM (ruralidad, lengua materna e identidad indígena, agua, electricidad; 1 874); BDPI Cultura (comunidades campesinas y nativas y su % del territorio, reservas indígenas; 1 319); MTC red vial nacional (km por distrito); SERNANP ANP y amortiguamiento, MINEM cartera de proyectos y minas por método (`ambiente`); ANA conflictos hídricos y estrés hídrico (`ana`); OEFA denuncias extractivas 2018-2024, solo conteos (`oefa_denuncias`); GEOBOSQUES pérdida de bosque 2001-2025 (Excel bajado a mano, `datos/crudos/geobosques/`); RENAMU 2023: rondas campesinas, oficina ambiental, participación ciudadana, personal municipal (`renamu`) |
| `senace_certificacion` | 3 959 (721 distritos, 1995-2026) | SENACE: certificaciones ambientales de minería, hidrocarburos y electricidad | `python -m tremor.distritos senace` |
| `emergencia` | 5 061 (1 238 distritos, 2020-2026) | Emergencias hídricas INDECI/ANA (lluvias, huaicos, sequías, heladas) | `python -m tremor.distritos emergencias` |
| `nota` (consulta = 'radio') | se acumula | **Radio en vivo** (módulo 003): 225 radios de 96 provincias con operaciones extractivas o casos socioambientales (`tremor/radios.csv`, de OnlineRadioBox, Zeno y webs; streams probados el 7 nov). Graba en franjas de noticieros, transcribe con faster-whisper `small` (CPU int8, sin cuota) y cada fragmento entra como nota al codificador. Solo castellano (quechua y aimara: pendiente) | `python -m tremor.radio escuchar --minutos 30`; en Actions `radio.yml` (15 máquinas, 6:00 y 12:30) |
| `mencion`, `animo` | por nota / por proyecto | **Ánimo hacia proyectos y empresas** (`tremor/animo.py`): 25 proyectos con alias y provincias de influencia; tono por léxico del dominio (reglas); índice de 14 días: menciones, alza frente a las 8 semanas previas y % negativas. Entra a `alerta.animo_proyectos` | `python -m tremor.animo` |
| `acled_evento` | 12 326 (794 distritos, 2018-01 a 2025-11; 535 extractivos) | ACLED (CSV bajado a mano del Data Export Tool, requiere cuenta, en `datos/crudos/acled/`). Solo **valida** el modelo (`precision_top20_acled`), no entra como variable. No se guardan notas ni actores | `python -m tremor.distritos acled` | `python -m tremor.distritos todo` (exporta `distrito_variable.csv`) |
| `distrito_corredor` | 920 distritos | Corredores logísticos (C01–C20) y alimentadores (AL…) del MTC, más el Corredor Minero del Sur (PE-3SG) | `python -m tremor.distritos vias` |
| `nivel_mes`, `modelo_metrica`, `modelo_importancia`, `modelo_perfil`, `alerta` | escala 0–4 por distrito-mes; métricas en 2024+; alerta de los 1 892 distritos | Modelo de `specs/005-modelo` | `python -m tremor.modelo` (~10 min; exporta CSV) |

Archivos que acompañan a la base:
- `datos/distritos.geojson`: límites INEI 2025 (capa del PNUD, simplificada a ~100 m), para mapas y cruces;
- `tremor/fuentes_facebook.csv`: 158 páginas para vigilar a mano, por departamento;
- `tremor/ubigeo.csv`: catálogo de los 1 892 distritos (INEI 2023);
- `tremor/codigos_egpp.json`: listas cerradas de acción, actor, adversario y reclamo.

**MCP** (`python -m tremor.mcp_server`):
- `buscar_lugar`;
- `perfil_distrito`;
- `ranking`;
- `consulta_amigable`: el MEF libre, con la URL como fuente; el método viene del MCP de Noelia León
  (`NoeliaLRuiz/mcp-consulta-amigable`);
- `serie_bcrp`: las series del BCRP guardadas (precios y producción minera por departamento);
- `ranking_variable`: distritos ordenados por cualquier variable de `distrito_variable`;
- `alerta`: la alerta del modelo con razones, capa de prensa en vivo y el desempeño en 2024+.
- `perfil_distrito` también trae la pobreza (ENAHO) y la producción minera anual (BCRP) del departamento.

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
  - casos ubicados (`ubicar_caso`, 7 nov): 1 420 a distrito, 144 a provincia, 221 a departamento (la ficha no
    trae ubicación), 58 sin lugar;
  - la **fase por caso no se publica en los PDF** (revisados 2016 y 2024): solo el total por fase. Existe desde el
    reporte 271 (HTML), 77 caso-mes. En su lugar, un indicador de escalamiento por reglas: diálogo (leído en
    ~30 900 caso-mes desde el reporte 50), latente → activo, hechos del mes (violencia, heridos, paro, bloqueo) y
    víctimas;
  - el **reporte 271** (HTML): sus acciones se leen de la hoja de Google enlazada (`base_abierta`, 151 acciones).

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
1. ✅ Ubicar los casos (`ubicar_caso` en `tremor/prensa/eventos.py`, corre con `validar`).
2. Indicador de escalamiento por caso-mes en lugar de la fase (ver sección 5).
3. ✅ Leer las acciones de protesta del reporte 271 (`python -m tremor.defensoria abierta`).

**C. Perfil territorial del distrito** (`tremor/territorio.py`). Cada variable va con su año, para no usar un dato
publicado después del mes que se predice.
1. ✅ MEF: canon y presupuesto municipal.
2. ✅ BCRP: precios y producción minera mensual por departamento (`bcrp_mensual`).
3. ✅ ENAHO: pobreza por departamento 2004–2025 (`enaho_departamento`).
4. ✅ Distrito (`tremor/distritos.py`): IDH, pobreza 2018, Censo 2017, BDPI, pasivos, OEFA, ONPE (Infogob tiene
   el servidor de descargas caído: error 500), red vial, SENACE, ANA, OEFA denuncias, emergencias, GEOBOSQUES,
   RENAMU 2023 (foto; cada año tiene otro código en el INEI) y ACLED (validación externa).

**D. Operaciones extractivas (módulo 004):** concesiones y unidades mineras (Ingemmet, Minem) y lotes de
Perupetro, cada una con su distrito y sus coordenadas.

**E. El modelo (módulo 005), el centro del backend** — ✅ hecho en `tremor/modelo.py` (spec, plan y tareas en
`specs/005-modelo`). Decisiones que cambiaron respecto de lo de abajo: horizonte de **3 meses** (la Defensoría
publica con un mes de rezago), tres objetivos (medida de fuerza, medida de fuerza **extractiva**, crisis),
competencia de modelos al estilo de los repos del profesor (14.388 y MGTECON 634 en `d2cml-ai`): logística, Lasso,
árbol, bosque, boosting y ensamble; razones por oclusión de grupos; la prensa entra como capa en vivo
(`alerta_inmediata`), no como variable. Plan original:
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
