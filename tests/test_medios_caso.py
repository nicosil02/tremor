import sqlite3
from datetime import date

from tremor.web import medios_recientes


def test_medios_del_caso_piden_contraparte_o_conflicto():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE nota (medio, publicado, titular, resumen, enlace, filtro)")
    hoy = date.today().isoformat()
    con.executemany("INSERT INTO nota VALUES (?, ?, ?, ?, ?, NULL)", [
        ("A", hoy, "Papa rinde homenaje a la independencia", "", "x"),
        ("B", hoy, "Independencia: comuneros reclaman a Raura", "", "y"),
        ("C", hoy, "Chuicuni anuncia paro", "", "z"),
    ])
    out = medios_recientes(con, ["Independencia - Raura", "Comunidad Campesina de Chuicuni", "Minera Las Bambas (II)"])
    assert [m["medio"] for m in out[0]] == ["B"]
    assert [m["medio"] for m in out[1]] == ["C"]
    assert out[2] == []
