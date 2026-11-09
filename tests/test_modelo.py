import numpy as np
import pandas as pd

from tremor.modelo import captura, ingenuo


def test_captura_y_ingenuo_de_zona():
    p = pd.DataFrame({"m": [1] * 10, "zona_fuerza_1": [0] * 9 + [2], "zona_fuerza_12": range(10),
                      "fuerza_1": [1] + [0] * 9, "fuerza_12": [0] * 10})
    y = np.array([0] * 9 + [1])
    assert captura(p, np.arange(10), y) == 1.0       # el evento está en el 10% de arriba
    assert captura(p, -np.arange(10), y) == 0.0
    assert ingenuo(p, "z_fuerza").idxmax() == 9      # el de zona mira la zona, no el distrito
    assert ingenuo(p, "y_fuerza").idxmax() == 0


def test_zonas_disjuntas_no_cuentan_dos_veces():
    from tremor import modelo
    modelo.VECINDAD.update(idx={"a": 0, "b": 1, "c": 2}, W=np.array([[1, 1, 0], [1, 1, 0], [0, 0, 1]], bool))
    p = pd.DataFrame({"ubigeo": ["a", "b", "c"], "m": [1, 1, 1]})
    y = np.array([1, 1, 0])
    assert modelo.precision_top(p, np.array([3, 2, 1]), y, k=2) == 1.0                  # a y b: mismo evento
    assert modelo.precision_top(p, np.array([3, 2, 1]), y, k=2, disjuntas=True) == 0.5  # b se salta: a y c
