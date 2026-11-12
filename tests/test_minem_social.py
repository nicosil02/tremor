from tremor.minem_social import fichas

# dos formatos reales: 2018 (rótulos en mayúsculas, "Distritos" con lista) y 2014 (sin dos puntos, sin problemática)
TEXTO = """2.1 Atención directa de seguimiento de casos asignados
ZONA NORTE
REGIÓN ANCASH
NOMBRE DEL CASO: ANTAMINA Y GRUPO DE INVERSIÓN SOCIAL DE LA
ASOCIACIÓN DE MUNICIPALIDADES (AMUCEPS)
UBICACIÓN GEOGRÁFICA:
Departamento
: Ancash
Provincia
: Huari
Distritos
: Chavín de Huantar, San Marcos, Huachis.
ACTORES:
• AMUCEPS Huari
• ANTAMINA
PROBLEMÁTICA:
La Asociación pide que las empresas asuman sus responsabilidades sociales.
DESCRIPCIÓN DE LOS HECHOS:
OCTUBRE-DICIEMBRE DEL 2018:
Se cumplieron los compromisos.
SITUACIÓN ACTUAL Y SEGUIMIENTO
Se prevé un clima de tranquilidad en la zona.
REGIÓN PIURA
Nombre del Caso : Mesa de Trabajo Raura - Comunidad Campesina de Quichas
Ubicación Geográfica
Región
:
Lima
Provincia
:
Oyón
Distrito
:
Oyón
C Campesina
:
Quichas
Actores
:
• Empresa Compañía Minera Raura
OCTUBRE:
Se realizaron reuniones con la empresa.
4.- INVERSIÓN SOCIAL Y DESARROLLO SOSTENIBLE
NOMBRE DEL CASO: esto ya no es una ficha
"""


def test_fichas_dos_formatos():
    a, b = fichas(TEXTO)  # la sección de inversión social ya no cuenta
    assert a["nombre"] == "ANTAMINA Y GRUPO DE INVERSIÓN SOCIAL DE LA ASOCIACIÓN DE MUNICIPALIDADES (AMUCEPS)"
    assert (a["departamento"], a["provincia"], a["ubigeo"]) == ("Ancash", "Huari", "021004")  # Chavín de Huántar
    assert a["distrito"].startswith("Chavín de Huantar, San Marcos")
    assert a["actores"] == "AMUCEPS Huari ; ANTAMINA"
    assert a["problematica"].startswith("La Asociación pide")
    assert a["situacion"] == "Se prevé un clima de tranquilidad en la zona"  # sin el "REGIÓN PIURA" que sigue
    assert (b["departamento"], b["provincia"], b["distrito"], b["ubigeo"]) == ("Lima", "Oyón", "Oyón", "150901")
    assert b["actores"] == "Empresa Compañía Minera Raura" and b["problematica"] is None
    assert b["situacion"].endswith("reuniones con la empresa")  # sin situación actual: lo último de los hechos
