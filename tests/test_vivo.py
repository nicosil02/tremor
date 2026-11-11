import sqlite3
from datetime import datetime, timedelta

from tremor import vivo


def _con():
    con = sqlite3.connect(":memory:")
    con.executescript("""CREATE TABLE nota (id TEXT PRIMARY KEY, medio, titular, resumen, publicado, enlace, consulta, departamento, recogido, filtro);
                         CREATE TABLE llm_cache (clave TEXT PRIMARY KEY, respuesta TEXT, creado TEXT);""")
    return con


RADIO = {"medio": "Radio Calor", "departamento": "Arequipa", "provincia": "Caylloma", "ubigeo_provincia": "0405", "stream": "https://s/x.m3u8"}
RELLENO = ("buenos días a toda la provincia, hoy el alcalde explicó el avance de la carretera y del canal de riego, mientras los "
           "agricultores del valle esperan la lluvia para la siembra de papa y maíz; además el hospital anunció una campaña de "
           "vacunación para niños y adultos mayores en los centros poblados más alejados del distrito. ")
CON_PARO = RELLENO + "los dirigentes de la comunidad de Chivay anuncian un paro de 48 horas desde mañana contra la empresa minera por el agua del río. " + RELLENO


def test_vivo_guarda_y_avisa_una_vez(monkeypatch):
    con, enviados, memoria = _con(), [], {}
    monkeypatch.setattr("tremor.llm.chat_json", lambda con, s, u, v: {"concreta": True, "contra": "minera", "quienes": "dirigentes de la comunidad",
                                                                       "cuando": "mañana", "duracion": "48 horas", "lugar": "Chivay"})
    t = datetime(2026, 11, 11, 9, 0)
    # sin medida: se guarda la nota y no hay aviso
    assert vivo.procesar(con, RADIO, t, RELLENO + RELLENO + "gracias por sintonizarnos.", "Bateas", memoria, enviados.append) == []
    assert con.execute("SELECT COUNT(*) FROM nota").fetchone()[0] == 1 and not enviados
    # con medida concreta: aviso con la cita y clave única
    avisos = vivo.procesar(con, RADIO, t + timedelta(minutes=1), CON_PARO, "Bateas", memoria, enviados.append)
    assert len(avisos) == 1 and "EN VIVO · Radio Calor, 09:01" in avisos[0] and "Paro de dirigentes de la comunidad" in avisos[0]
    assert "«" in avisos[0] and "paro de 48 horas" in avisos[0] and "https://s/x.m3u8" in avisos[0]
    assert con.execute("SELECT clave FROM aviso_enviado").fetchall() == [("vivo:Radio Calor:2026-11-11T09:01",)]
    # la misma medida en la misma radio 10 minutos después: se guarda, no se avisa
    assert vivo.procesar(con, RADIO, t + timedelta(minutes=11), CON_PARO + " ahora", "Bateas", memoria, enviados.append) == []
    assert len(enviados) == 1
    # el LLM dice que no es concreta: nada
    monkeypatch.setattr("tremor.llm.chat_json", lambda *a: {"concreta": False})
    assert vivo.procesar(con, {**RADIO, "medio": "Radio Sol"}, t, CON_PARO, "Bateas", {}, enviados.append) == []


def test_medida():
    assert vivo.medida("anuncian un bloqueo de la vía")[0] == "Bloqueo"
    assert vivo.medida("saludos a los oyentes") == (None, None)


def test_conexion_compartida_entre_hilos(tmp_path):
    """La radio en vivo escribe desde varios hilos con una sola conexión (bajo candado): sqlite debe permitirlo."""
    import threading
    from tremor.db import conectar
    con = conectar(tmp_path / "t.db", hilos=True)
    err = []
    def escribe():
        try: con.execute("CREATE TABLE IF NOT EXISTS x (a)"); con.execute("INSERT INTO x VALUES (1)"); con.commit()
        except Exception as e: err.append(e)
    t = threading.Thread(target=escribe); t.start(); t.join()
    assert not err and con.execute("SELECT COUNT(*) FROM x").fetchone()[0] == 1
