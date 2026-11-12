import pandas as pd

from tremor.huelgas import numero, por_mes


def test_cuadro_mensual_con_asteriscos():
    nan = float("nan")
    # forma real del anuario: título, encabezado en dos filas, "*" dentro de la celda o en columna aparte
    hoja = pd.DataFrame([
        [nan, "HUELGAS, TRABAJADORES COMPRENDIDOS Y HORAS - HOMBRE", nan, nan, nan, nan],
        [nan, "MES", "AGRICULTURA", "EXPLOTACIÓN DE MINAS Y CANTERAS", nan, "TOTAL"],
        [nan, nan, nan, nan, nan, "ABSOLUTO"],
        [nan, "JULIO *", nan, nan, nan, nan],
        [nan, "Huelgas", 1, "*", nan, 1],
        [nan, "Trabajadores Comprendidos", 10, 1, nan, 11],
        [nan, "Horas - Hombre Perdidas", 80, "8 160", "*", "8 240*"],
        [nan, "TOTAL", nan, nan, nan, nan],
        [nan, "Huelgas", 1, 0, nan, 1],
        [nan, " FUENTE : MTPE", nan, nan, nan, nan],
        [nan, "Huelgas", 9, 9, nan, 9],  # después de FUENTE no cuenta
    ])
    m = por_mes(hoja)
    assert m[7] == {"huelgas": (0, 1), "trabajadores": (1, 11), "horas_hombre": (8160, 8240)}
    assert m[0] == {"huelgas": (0, 1)}
    assert (numero("-"), numero(nan), numero("NO SE REGISTRÓ HUELGAS"), numero(12.0)) == (0, 0, 0, 12)
