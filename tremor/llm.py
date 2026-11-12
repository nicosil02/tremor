"""LLM por endpoints compatibles con OpenAI (constitución III).

LLM_MODEL es una cadena separada por comas; cada modelo usa la clave de su proveedor y, si agota su cupo diario,
sigue el siguiente (cada modelo tiene su propio cupo). Prefijos: `gemini:` (GEMINI_API_KEY), `mistral:` (MISTRAL_API_KEY); sin prefijo,
LLM_BASE_URL + LLM_API_KEY (Groq). Un proveedor sin clave se salta.
Cada respuesta se guarda en llm_cache por contenido: volver a correr no gasta cuota.
"""
import hashlib
import json
import os
import time

import requests

from tremor.db import RAIZ, ahora

CADENA = ("openai/gpt-oss-120b,gemini:gemini-3.6-flash,gemini:gemini-3.5-flash,gemini:gemini-3-flash-preview,"
          "gemini:gemini-3.8-flash,gemini:gemini-3.7-flash,gemini:gemini-3.5-flash-lite,gemini:gemini-3.1-flash-lite,"
          "mistral:mistral-large-latest,mistral:mistral-small-latest,"
          "openai/gpt-oss-20b")  # cada modelo, su propio cupo diario; el saturado o retirado cede al siguiente
PROVEEDORES = {"gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
               "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY")}


def _env():
    """Lee .env sin dependencias; las variables ya definidas en el entorno mandan (GitHub Actions)."""
    ruta = RAIZ / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            k, _, v = linea.partition("=")
            if k.strip() and not k.startswith("#") and v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def cadena() -> list[tuple[str, str, str]]:
    """[(modelo, url, clave)] en orden, solo los que tienen clave."""
    _env()
    salida = []
    for m in os.environ.get("LLM_MODEL", CADENA).split(","):
        m = m.strip()
        if m.partition(":")[0] in PROVEEDORES:
            url, clave = PROVEEDORES[m.partition(":")[0]]
            salida.append((m.partition(":")[2], url, os.environ.get(clave, "")))
        elif m:
            salida.append((m, os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
                           os.environ.get("LLM_API_KEY", "")))
    return [x for x in salida if x[2]]


class SinCuota(Exception):
    pass


class RespuestaInvalida(Exception):
    """400: casi siempre JSON mal formado por el modelo (json_validate_failed)."""


AGOTADOS = set()  # modelos sin cupo diario en esta corrida


def chat_json(con, sistema: str, usuario: str, version: str) -> dict:
    modelos = cadena()
    clave_de = lambda m: hashlib.sha256(f"{m}\n{version}\n{sistema}\n{usuario}".encode()).hexdigest()
    for m, _, _ in modelos:
        fila = con.execute("SELECT respuesta FROM llm_cache WHERE clave = ?", (clave_de(m),)).fetchone()
        if fila:
            return json.loads(fila[0])
    if not modelos:
        raise SinCuota("Falta LLM_API_KEY (o GEMINI_API_KEY) en .env")
    for m, url, clave in modelos:
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
        try:
            r = requests.post(f"{url}/chat/completions", json=cuerpo, timeout=90,
                              headers={"Authorization": f"Bearer {clave}"})
        except (requests.ConnectionError, requests.Timeout):  # red caída o modelo colgado: dos intentos y al siguiente
            if intento >= 1:
                raise SinCuota("sin respuesta")
            time.sleep(10)
            continue
        if r.status_code == 429:
            espera = float(r.headers.get("retry-after", 20 * (intento + 1)))
            if espera > 120 or "per day" in r.text.lower() or "PerDay" in r.text:  # cupo diario: siguiente modelo
                raise SinCuota(r.text[:200])
            time.sleep(espera)
            continue
        if r.status_code >= 500:  # proveedor saturado (Gemini da 503): un reintento y al siguiente modelo
            if intento >= 1:
                raise SinCuota(f"saturado ({r.status_code})")
            time.sleep(10)
            continue
        if r.status_code in (403, 404):  # modelo retirado o no habilitado para esta clave
            raise SinCuota(f"no disponible ({r.status_code})")
        if r.status_code in (400, 413):  # 413: lote demasiado grande; quien llama lo parte en dos
            raise RespuestaInvalida(f"{r.status_code}: {r.text[:300]}")
        r.raise_for_status()
        texto = r.json()["choices"][0]["message"]["content"]
        texto = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        datos = json.loads(texto)
        con.execute("INSERT OR REPLACE INTO llm_cache VALUES (?, ?, ?, ?)", (k, texto, modelo, ahora()))
        con.commit()
        return datos
    raise SinCuota("429 repetido")
