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
    tipo TEXT,
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
    return con
