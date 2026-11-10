from tremor.oefa import soles


def test_soles_dos_formatos():
    assert soles("S/.24.866,80") == 24866.8
    assert soles("S/.23,000,000.00") == 23000000.0
    assert soles("S/.324327.60") == 324327.6
    assert soles(None) is None
