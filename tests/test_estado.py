import pymupdf

from tremor.estado import paginas


def test_paginas_con_tablas_de_casos():
    doc = pymupdf.open()
    for t in ("Presentación de la revista", "Nombre Ubicación Tipología Situación", "Caso Situación actual"):
        doc.new_page().insert_text((72, 72), t)
    pdf = doc.tobytes()
    assert [p.strip() for p in paginas(pdf, "PCM")] == ["Nombre Ubicación Tipología Situación"]
    assert [p.strip() for p in paginas(pdf, "MINAM")] == ["Caso Situación actual"]
