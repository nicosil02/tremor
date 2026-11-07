"""Base SQLite única de Tremor. Esquema: specs/001-recolector-defensoria/data-model.md."""
import sqlite3
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
RUTA_DB = DATOS / "tremor.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS documento (
    url TEXT PRIMARY KEY,
    fuente TEXT NOT NULL,             -- listado | wayback | zip
    titulo TEXT,
    fecha_publicacion TEXT,
    formato TEXT,                     -- pdf | html | zip
    num_titulo INTEGER,               -- número según el título o la URL (pista, no verdad)
    huella TEXT,                      -- SHA-256 del contenido, vacío si no se descargó
    reporte_num INTEGER,              -- número leído de la portada
    anio INTEGER, mes INTEGER,        -- periodo leído de la portada
    rol TEXT,                         -- principal | copia | parte | especial | sin_numero
    error TEXT,
    descubierto_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS faltante (
    num INTEGER PRIMARY KEY,
    fuentes_probadas TEXT NOT NULL,
    revisado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reporte (
    num INTEGER PRIMARY KEY,
    anio INTEGER, mes INTEGER,
    huella TEXT,
    total INTEGER, activos INTEGER, latentes INTEGER, en_dialogo INTEGER,
    acciones_declaradas INTEGER,
    estado TEXT NOT NULL DEFAULT 'pendiente',   -- pendiente | valido | fallido
    detalle_validacion TEXT
);
CREATE TABLE IF NOT EXISTS seccion (
    reporte_num INTEGER NOT NULL,
    titulo_original TEXT NOT NULL,
    canonica TEXT NOT NULL,
    pagina_inicio INTEGER, pagina_fin INTEGER,
    UNIQUE (reporte_num, titulo_original, pagina_inicio)
);
CREATE TABLE IF NOT EXISTS caso (
    id INTEGER PRIMARY KEY,
    codigo TEXT UNIQUE,
    nombre TEXT,                      -- solo los reportes de 2026 traen nombre corto
    nombres_anteriores TEXT,
    descripcion TEXT, ubicacion TEXT, actores TEXT,  -- última versión, para enlazar meses sin código
    tipo TEXT, ingreso TEXT,         -- mes de ingreso al registro: llave del enlace entre meses
    departamento TEXT, provincia TEXT, distrito TEXT, ubigeo TEXT
);
CREATE TABLE IF NOT EXISTS caso_mes (
    caso_id INTEGER NOT NULL REFERENCES caso(id),
    reporte_num INTEGER NOT NULL,
    estado TEXT, con_hechos INTEGER, fase TEXT, dialogo TEXT, competencia TEXT, ubicacion TEXT,
    actores_primarios TEXT, actores_secundarios TEXT, actores_terciarios TEXT,
    descripcion TEXT, hechos_mes TEXT,
    pagina INTEGER,
    enlace_confianza REAL,
    PRIMARY KEY (caso_id, reporte_num)
);
CREATE TABLE IF NOT EXISTS accion_protesta (
    reporte_num INTEGER NOT NULL,
    n INTEGER NOT NULL,
    fecha TEXT, medida TEXT, actores TEXT, lugar TEXT, demanda TEXT,
    departamento TEXT, ubigeo TEXT,
    pagina INTEGER,
    PRIMARY KEY (reporte_num, n)
);
CREATE TABLE IF NOT EXISTS victimas (
    reporte_num INTEGER NOT NULL,
    caso_id INTEGER,
    lugar_caso TEXT,                  -- como lo escribe la tabla; enlazar con caso queda pendiente
    fallecidos INTEGER, heridos INTEGER,
    pagina INTEGER
);
-- 002: base de protestas de la EGPP PUCP (Arce 2024; actualización dic. 2025), sin Comentar_t.
CREATE TABLE IF NOT EXISTS egpp_evento (
    id INTEGER PRIMARY KEY,
    fecha TEXT NOT NULL, ubigeo TEXT NOT NULL, precision TEXT, capital_por_defecto INTEGER,
    periodico TEXT, sector TEXT, actor TEXT, actor_t TEXT,
    accion_1 TEXT, accion_2 TEXT, accion_3 TEXT, accion_4 TEXT, accion_t TEXT,
    adversario TEXT, institucion_1 TEXT, institucion_2 TEXT,
    reclamo TEXT, sub_reclamo TEXT, reclamo_t TEXT,
    participantes REAL, duracion_h REAL, heridos REAL, muertos REAL, detenidos REAL, fuerza_estatal INTEGER,
    tipo_conflicto TEXT, operacion TEXT, duplicado_de INTEGER, version TEXT
);
CREATE INDEX IF NOT EXISTS egpp_fecha_lugar ON egpp_evento (fecha, ubigeo);
-- 002: prensa (specs/002-prensa-egpp/data-model.md)
CREATE TABLE IF NOT EXISTS nota (
    id TEXT PRIMARY KEY, medio TEXT, titular TEXT NOT NULL, publicado TEXT, enlace TEXT,
    consulta TEXT, departamento_consulta TEXT, descargado TEXT NOT NULL, filtro TEXT
);
CREATE TABLE IF NOT EXISTS codificacion (
    nota_id TEXT NOT NULL, version TEXT NOT NULL,
    es_protesta INTEGER, estado TEXT, fecha_evento TEXT,
    region TEXT, provincia TEXT, distrito TEXT, localidad TEXT, ubigeo TEXT, precision TEXT,
    sector TEXT, actor TEXT, accion TEXT, adversario TEXT, empresa TEXT, operacion TEXT,
    reclamo TEXT, sub_reclamo TEXT, heridos INTEGER, muertos INTEGER, detenidos INTEGER, tipo_conflicto TEXT,
    PRIMARY KEY (nota_id, version)
);
CREATE TABLE IF NOT EXISTS evento_prensa (
    id INTEGER PRIMARY KEY, estado TEXT, fecha_anuncio TEXT, fecha_evento TEXT, ubigeo TEXT, precision TEXT,
    accion TEXT, actor TEXT, reclamo TEXT, tipo_conflicto TEXT, empresa TEXT, operacion TEXT,
    n_notas INTEGER, n_medios INTEGER
);
CREATE TABLE IF NOT EXISTS evento_nota (evento_id INTEGER NOT NULL, nota_id TEXT NOT NULL, PRIMARY KEY (evento_id, nota_id));
CREATE TABLE IF NOT EXISTS llm_cache (clave TEXT PRIMARY KEY, respuesta TEXT NOT NULL, modelo TEXT, creado TEXT);
CREATE TABLE IF NOT EXISTS corrida (
    id INTEGER PRIMARY KEY,
    paso TEXT NOT NULL,
    inicio TEXT NOT NULL, fin TEXT,
    nuevos INTEGER DEFAULT 0, errores INTEGER DEFAULT 0,
    detalle TEXT
);
"""


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def conectar(ruta: Path = RUTA_DB) -> sqlite3.Connection:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    # Columnas añadidas después de la primera versión (bases ya creadas).
    existentes = {f[1] for f in con.execute("PRAGMA table_info(documento)")}
    for col, tipo in [("anio", "INTEGER"), ("mes", "INTEGER"), ("rol", "TEXT")]:
        if col not in existentes:
            con.execute(f"ALTER TABLE documento ADD COLUMN {col} {tipo}")
    if "ingreso" not in {f[1] for f in con.execute("PRAGMA table_info(caso)")}:
        con.execute("ALTER TABLE caso ADD COLUMN ingreso TEXT")
    return con
