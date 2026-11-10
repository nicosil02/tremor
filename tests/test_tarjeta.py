def test_camino_sigue_su_via_y_salta_los_cortes():
    from tremor.tarjeta import camino, destino, red
    # la vía X viene en dos trozos con un hueco de 0.005°; la Y es un atajo por arriba
    g = red([("X", [(0, 0), (1, 0)]), ("X", [(1.005, 0), (2, 0)]), ("Y", [(0, 0.01), (1, 0.5), (2, 0.01)])])
    por_x = camino(g, [(0, 0)], (2, 0), via="X")
    assert por_x[0] == (0, 0) and por_x[-1] == (2, 0) and all(y == 0 for _, y in por_x)  # cruza el hueco, no toma el atajo
    assert (1, 0.5) in camino(g, [(0, 0)], (2, 0), via="Y")
    assert camino(g, [(5, 5)], (2, 0)) is None  # lejos de la red: recta
    # sale del punto de la ruta ya trazada más cercano por la red
    assert camino(g, [(-3, 3), (1, 0)], (2, 0), via="X")[0] == (1, 0)
    assert destino("Puerto de Matarani, zinc") == "Matarani" and destino("Panamericana Sur al Callao, plomo") == "Callao"
