import sqlite3

from tremor.avisos import empujan, eventos, zona


def test_empujan_descarta_lo_que_esta_bajo_lo_habitual():
    r = ("sube: medidas de fuerza en la zona en los últimos 3 meses: 1 (lo habitual, 2) · sube: casos nuevos: 3 (lo habitual, 0)"
         "; señales cerca de lo habitual · baja: algo: 5 (lo habitual, 1) · sube: en octubre suele haber más protestas")
    assert empujan(r) == ["casos nuevos: 3 (lo habitual, 0)", "en octubre suele haber más protestas"]


def test_eventos_en_la_zona_o_que_nombran_a_la_empresa():
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE operacion (empresa, unidad, tipo, ubigeo, etapa);
        INSERT INTO operacion VALUES ('MINERA LAS BAMBAS S.A.', 'Las Bambas', 'mineria', '030506', 'operación');
        CREATE TABLE evento_prensa (id, estado, fecha_anuncio, fecha_evento, ubigeo, accion, empresa, operacion);
        INSERT INTO evento_prensa VALUES (1, 'anunciada', '2026-11-08', '2026-11-12', '030501', 'Paro', NULL, NULL),
                                         (2, 'ocurrida', NULL, '2026-11-08', '150101', 'Marcha', NULL, NULL),
                                         (3, 'ocurrida', NULL, '2026-11-08', '04', 'Bloqueo', 'Minera Las Bambas', NULL),
                                         (4, 'anunciada', '2026-10-01', '2026-10-02', '030506', 'Paro', NULL, NULL);
        CREATE TABLE evento_nota (evento_id, nota_id); CREATE TABLE nota (id, medio, enlace);""")
    z = zona(con, "minera las bambas", {"030506": ["030501"]})
    assert z == {"030506": "Las Bambas", "030501": "Las Bambas"}
    assert [e["clave"] for e in eventos(con, z, r"las bambas", "2026-11-01")] == ["evento:1", "evento:3"]
