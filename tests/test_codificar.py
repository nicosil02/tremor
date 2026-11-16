

def test_verificar_radio(monkeypatch):
    import sqlite3
    from tremor.prensa import codificar as cod
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE nota (id, resumen, consulta)")
    con.execute("CREATE TABLE codificacion (nota_id, version, es_protesta, tipo_conflicto)")
    for n in ("a", "b"):
        con.execute("INSERT INTO nota VALUES (?, 'hoy hubo una marcha en la plaza', 'radio')", (n,))
        con.execute("INSERT INTO codificacion VALUES (?, ?, 1, 'socioambiental_extractivo')", (n, cod.VERSION))
    respuestas = iter([{"concreta": False}, {"concreta": True, "contra": "eleccion", "cuando": "hoy"}])
    monkeypatch.setattr(cod, "chat_json", lambda *a: next(respuestas))
    assert cod.verificar_radio(con) == 2
    assert con.execute("SELECT nota_id, es_protesta, tipo_conflicto FROM codificacion ORDER BY nota_id").fetchall() == [
        ("a", 0, "socioambiental_extractivo"), ("b", 1, "otro")]  # a: no es concreta; b: real pero no contra la mina
    assert con.execute("SELECT cuando FROM radio_verificada WHERE nota_id = 'b'").fetchone() == ("hoy",)
    assert cod.verificar_radio(con) == 0  # no se relee


def test_retiros_solo_notas_con_retiro():
    import sqlite3, json
    import tremor.prensa.codificar as C
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE nota (id, titular, resumen)")
    con.execute("CREATE TABLE codificacion (nota_id, version, es_protesta)")
    con.executemany("INSERT INTO nota VALUES (?, ?, ?)", [
        ("a", "Mototaxistas se desligan del paro", ""), ("b", "Anuncian paro", ""),
        # 16 nov 2026: dejar la carretera no es retirarse del paro; esta nota ya ni llega al LLM
        ("c", "Paro de transportistas", "El bloqueo duró varias horas, pero finalmente los transportistas se retiraron.")])
    con.executemany("INSERT INTO codificacion VALUES (?, ?, 1)", [("a", C.VERSION), ("b", C.VERSION), ("c", C.VERSION)])
    pedidos = []
    C.chat_json = lambda con, p, t, k: pedidos.append(t) or {"retiran": [
        {"gremio": "mototaxistas de Islay", "cita": "Mototaxistas se desligan del paro"},
        {"gremio": "gremio inventado", "cita": "frase que la nota no dice sobre el paro"},
        {"gremio": "convocantes", "cita": "Mototaxistas"}], "todos": False}
    assert C.retiros(con) == 1 and len(pedidos) == 1      # ni la nota sin retiro ni la del bloqueo gastan cuota
    assert json.loads(con.execute("SELECT gremios FROM retiro_nota").fetchone()[0]) == ["mototaxistas de Islay"]  # solo el de cita comprobada
    assert C.retiro_valido([{"gremio": "Coordinadora", "cita": "finalmente los transportistas se retiraron"}],
                           "pero finalmente los transportistas se retiraron de la vía") == []
