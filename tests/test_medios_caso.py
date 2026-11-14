import sqlite3
from datetime import date

from tremor.web import medios_recientes


def test_medios_del_caso_piden_contraparte_o_conflicto():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE nota (medio, publicado, titular, resumen, enlace, filtro, consulta)")
    hoy = date.today().isoformat()
    con.executemany("INSERT INTO nota VALUES (?, ?, ?, ?, ?, NULL, ?)", [
        ("A", hoy, "Papa rinde homenaje a la independencia", "", "x", None),
        ("B", hoy, "Independencia: comuneros reclaman a Raura", "", "y", None),
        ("C", hoy, "Chuicuni anuncia paro", "", "z", None),
        ("D", hoy, "Radio X, en vivo", "Chuicuni anuncia paro", "w", "radio"),
    ])
    out = medios_recientes(con, ["Independencia - Raura", "Comunidad Campesina de Chuicuni", "Minera Las Bambas (II)"])
    assert [m["medio"] for m in out[0]] == ["B"]
    assert [m["medio"] for m in out[1]] == ["C"]
    assert out[2] == []


def test_fecha_pagina():
    from tremor.prensa.ampliar import fecha_pagina
    assert fecha_pagina('<meta property="article:published_time" content="2026-08-12T10:00:00-05:00">') == "2026-08-12"
    assert fecha_pagina('{"@type":"NewsArticle","datePublished": "2026-08-11T09:00"}') == "2026-08-11"
    assert fecha_pagina("<p>sin fecha</p>") is None


def test_elegir_bing():
    from tremor.prensa.ampliar import elegir_bing
    rss = ("<item><title>Otra cosa del día</title><link>http://www.bing.com/news/apiclick.aspx?url=https%3a%2f%2fa.pe%2fx&amp;c=1</link></item>"
           "<item><title>Transportistas de carga pesada anuncian paro nacional</title>"
           "<link>http://www.bing.com/news/apiclick.aspx?ref=1&amp;url=https%3a%2f%2flarepublica.pe%2fparo&amp;c=2</link></item>")
    assert elegir_bing(rss, "Transportistas de carga pesada anuncian paro nacional de 72 horas") == "https://larepublica.pe/paro"
    assert elegir_bing(rss, "Ronderos bloquean la vía en Cajamarca") is None


def test_cita_de_radio_alrededor_de_la_medida():
    from tremor.web import cita
    t = "somos noticia provincial y para que aquellas que quieren hacer una marcha hoy a favor del candidato esto está hoy en la agenda y después vamos con el abogado constitucionalista que nos explica el artículo"
    c = cita(t, ancho=40)
    assert "marcha hoy" in c and c.startswith("…") and c.endswith("…") and len(c) < 120
    assert cita("saludos a los oyentes de Chivay") is None


def test_mencion_de_radio_alrededor_del_proyecto():
    from tremor.web import alrededor
    from tremor.animo import ALIAS
    t = "saludos a los oyentes " * 20 + "los comuneros dicen que Las Bambas contamina el río y anuncian un paro " + "música " * 30
    r = alrededor(t, ALIAS["Las Bambas (MMG)"], ancho=40)
    assert "Las Bambas contamina" in r and r.startswith("…") and r.endswith("…") and len(r) < 140
    assert alrededor("sin la empresa", ALIAS["Las Bambas (MMG)"]) is None


def test_nota_vieja_sin_fecha_por_la_foto():
    """Sin fecha declarada: la carpeta de la foto principal, solo si el texto no nombra un año posterior."""
    from tremor.prensa.ampliar import fecha_por_foto
    foto = '<meta property="og:image" content="https://tvperu.gob.pe/files/noticias/imagen/2024-04-11/a.jpg">'
    assert fecha_por_foto(foto, "piden el aporte para los años 2022 y 2023") == "2024-04-11"
    assert fecha_por_foto(foto, "el paro de este 13 de noviembre de 2026") is None  # foto de archivo en una nota de hoy
    assert fecha_por_foto(foto, "comuneros bloquean la vía") is None                # sin años no hay segunda señal
    assert fecha_por_foto("<p>sin foto</p>", "aportes de 2023") is None


def test_motivo_de_pagina_sin_texto():
    from tremor.prensa.ampliar import sin_texto
    assert sin_texto("https://www.diario.pe/nota/1", 403, "<title>Just a moment...</title>") == "diario.pe: 403 con verificación anti-robots"
    assert sin_texto("https://tvperu.gob.pe/n/2", 200, "<html></html>") == "tvperu.gob.pe: 200, 13 caracteres"


def test_la_misma_nota_en_varios_medios_es_una_historia():
    from tremor.animo import historias
    cable = "Comuneros de Challhuahuacho anuncian paro de 48 horas contra Las Bambas por incumplimiento de acuerdos del convenio marco"
    h = historias([("a", "P", "2026-11-10", cable), ("b", "P", "2026-11-11", cable + " - Diario Sur"),
                   ("c", "P", "2026-11-11", "Las Bambas entrega dos salones multiuso a más de 150 pobladores de la comunidad de Chila"),
                   ("d", "P", "2026-11-20", cable), ("e", "Q", "2026-11-10", cable), ("f", "P", "2026-11-11", "Paro en Las Bambas")])
    assert h[("b", "P")] == "a"                       # la copia apunta a la primera
    assert h[("c", "P")] == "c" and h[("f", "P")] == "f"  # otra nota, y un titular corto no se compara
    assert h[("d", "P")] == "d" and h[("e", "Q")] == "e"  # diez días después u otro proyecto: historia aparte
