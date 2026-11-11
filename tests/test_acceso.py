from tremor.acceso import huella, valida


def test_valida():
    sal = "00" * 16
    cuentas = {"bateas": {"sal": sal, "huella": huella("clave-buena", sal), "empresa": "Bateas"}}
    assert valida(cuentas, " Bateas ", "clave-buena") == "Bateas"
    assert valida(cuentas, "bateas", "otra") is None
    assert valida(cuentas, "nadie", "clave-buena") is None


def test_poderosa_sin_falsos():
    from tremor.animo import menciones
    nombres = lambda t: [n for n, _ in menciones(t)]
    assert "Minera Poderosa" not in nombres("Confía en la poderosa sangre de Cristo. Amén.")
    assert "Minera Poderosa" not in nombres("Escuchas la poderosa mix, la radio de la mina.")
    assert "Minera Poderosa" in nombres("Comuneros de Pataz bloquean el acceso a la Poderosa.")
    assert "Minera Poderosa" in nombres("Minera Poderosa entrega obras.")
