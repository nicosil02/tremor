# Guía de validación: Recolector de reportes de la Defensoría

## Requisitos

- Python 3.12 con `requests`, `pymupdf` y `beautifulsoup4` (`pip install -r requirements.txt`).
- Conexión a internet. No se necesita ninguna clave.

## Escenario 1: catálogo desde cero (Historia 1)

```
python -m tremor.defensoria descubrir --completo
python -m tremor.defensoria estado
```

Esperado: al menos 249 reportes en el catálogo y una lista de faltantes con las fuentes probadas.

## Escenario 2: idempotencia (CE-006)

```
python -m tremor.defensoria todo
python -m tremor.defensoria todo
```

Esperado: la segunda corrida informa 0 nuevos y 0 cambios.

## Escenario 3: identidad por contenido (Historia 2)

Los reportes 263 (archivo `10.pdf`), 42 (`conflictos_sociales42.pdf`) y 271 (HTML) quedan
registrados con su número y su mes correctos.

## Escenario 4: validación contra los totales (Historia 4)

```
python -m tremor.defensoria extraer --num 271
python -m tremor.defensoria validar
```

Esperado para el 271: 193 casos (144 activos y 49 latentes) y 151 acciones de protesta. Estado
`valido`.

## Escenario 5: trayectoria de un caso

Abrir `datos/exportes/casos_mes.csv` y filtrar el código `0397-1208` (Cenepa). Esperado: una fila
por cada mes de 2026 con su fase.

## Prueba automática

```
python -m pytest tests/
```

Comprueba con fragmentos reales de texto la lectura de la portada, la frase de totales y una ficha
completa.
