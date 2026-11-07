"""LLM por endpoint compatible con OpenAI (constitución III): LLM_BASE_URL, LLM_MODEL, LLM_API_KEY.

Cada respuesta se guarda en llm_cache por contenido: volver a correr no gasta cuota.
LLM_MODEL puede ser una lista separada por comas: si un modelo agota su cupo diario, sigue con el siguiente.
"""
import hashlib
import json
import os
import time

import requests

from tremor.db import RAIZ, ahora


def _env():
    """Lee .env sin dependencias; las variables ya definidas en el entorno mandan (GitHub Actions)."""
    ruta = RAIZ / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            k, _, v = linea.partition("=")
            if k.strip() and not k.startswith("#") and v.strip():
                os.environ.setdefault(k.strip(), v.strip())
    return (os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
            os.environ.get("LLM_MODEL", "openai/gpt-oss-120b,openai/gpt-oss-20b"), os.environ.get("LLM_API_KEY", ""))


class SinCuota(Exception):
    pass


class RespuestaInvalida(Exception):
    """400 de Groq: casi siempre JSON mal formado por el modelo (json_validate_failed)."""


AGOTADOS = set()  # modelos sin cupo diario en esta corrida


def chat_json(con, sistema: str, usuario: str, version: str) -> dict:
    url, modelos, clave = _env()
    modelos = [m.strip() for m in modelos.split(",") if m.strip()]
    clave_de = lambda m: hashlib.sha256(f"{m}\n{version}\n{sistema}\n{usuario}".encode()).hexdigest()
    for m in modelos:
        fila = con.execute("SELECT respuesta FROM llm_cache WHERE clave = ?", (clave_de(m),)).fetchone()
        if fila:
            return json.loads(fila[0])
    if not clave:
        raise SinCuota("Falta LLM_API_KEY en .env")
    for m in modelos:
        if m in AGOTADOS:
            continue
        try:
            return _llamar(con, url, clave, m, clave_de(m), sistema, usuario)
        except SinCuota as e:
            print(f"  {m} sin cupo: {str(e)[:90]}")
            AGOTADOS.add(m)
    raise SinCuota("todos los modelos sin cupo")


def _llamar(con, url, clave, modelo, k, sistema, usuario) -> dict:
    cuerpo = {"model": modelo, "temperature": 0, "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
    for intento in range(8):
        r = requests.post(f"{url}/chat/completions", json=cuerpo, timeout=120,
                          headers={"Authorization": f"Bearer {clave}"})
        if r.status_code == 429:
            espera = float(r.headers.get("retry-after", 20 * (intento + 1)))
            if espera > 120:  # límite diario: pasa al siguiente modelo
                raise SinCuota(r.text[:200])
            time.sleep(espera)
            continue
        if r.status_code == 400:
            raise RespuestaInvalida(r.text[:300])
        r.raise_for_status()
        texto = r.json()["choices"][0]["message"]["content"]
        datos = json.loads(texto)
        con.execute("INSERT OR REPLACE INTO llm_cache VALUES (?, ?, ?, ?)", (k, texto, modelo, ahora()))
        con.commit()
        return datos
    raise SinCuota("429 repetido")
