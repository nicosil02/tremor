"""Ánimo hacia proyectos y empresas extractivas en radio y prensa: menciones y tono por proyecto, y su alza frente a
las semanas previas. Hipótesis de diseño: antes de un conflicto suben las menciones del proyecto y el tono se vuelve
negativo. Por reglas (léxico del dominio), no por LLM: cada tono se puede explicar con las palabras que lo dieron.

    python -m tremor.animo        # tablas mencion y animo (foto de los últimos 7 días frente a las 8 semanas previas; avisa picos y rachas negativas)

shortcut: diccionario curado de los proyectos más conflictivos; ampliarlo con SENACE/OEFA cuando haya alias limpios."""
import re
import sqlite3
import sys
from datetime import date, timedelta

import pandas as pd

from tremor.db import DATOS, RAIZ, ahora, conectar
from tremor.lugares import norm

# nombre: (alias, departamento, provincias de la zona de influencia)
PROYECTOS = {
    "Las Bambas (MMG)": (r"las bambas|\bmmg\b", "Apurímac", ["Cotabambas", "Grau"]),
    "Corredor Minero del Sur": (r"corredor minero", "Cusco", ["Chumbivilcas", "Espinar"]),
    "Tía María (Southern)": (r"t[ií]a mar[ií]a|lindero", "Arequipa", ["Islay"]),
    "Toquepala y Cuajone (Southern)": (r"toquepala|cuajone|southern", "Moquegua", ["Mariscal Nieto", "Ilo"]),
    "Antapaccay y Coroccohuayco (Glencore)": (r"antapaccay|tintaya|coroccohuayco|glencore", "Cusco", ["Espinar"]),
    "Constancia (Hudbay)": (r"constancia|hudbay", "Cusco", ["Chumbivilcas"]),
    "Conga y Yanacocha (Newmont)": (r"\bconga\b|yanacocha|newmont", "Cajamarca", ["Cajamarca", "Celendín", "Hualgayoc"]),
    "Michiquillay": (r"michiquillay", "Cajamarca", ["Cajamarca"]),
    "Quellaveco (Anglo American)": (r"quellaveco|anglo american", "Moquegua", ["Mariscal Nieto"]),
    "Antamina": (r"antamina", "Áncash", ["Huari"]),
    "Cerro Verde": (r"cerro verde", "Arequipa", ["Arequipa"]),
    "Zafranal": (r"zafranal", "Arequipa", ["Castilla"]),
    "Río Blanco": (r"r[ií]o blanco copper|proyecto r[ií]o blanco|majaz", "Piura", ["Huancabamba", "Ayabaca"]),
    "Lote 192 y Lote 8": (r"lote 192|lote 1-?ab|lote 8\b", "Loreto", ["Datem del Marañón", "Loreto"]),
    "Oleoducto Norperuano (Petroperú)": (r"oleoducto|petroper[uú]", "Loreto", ["Datem del Marañón", "Loreto"]),
    "Lote 95 (Petrotal)": (r"lote 95|petrotal", "Loreto", ["Requena"]),
    "Camisea (Pluspetrol, TGP)": (r"camisea|pluspetrol|\btgp\b|lote 88|lote 56", "Cusco", ["La Convención"]),
    "Toromocho (Chinalco)": (r"toromocho|chinalco", "Junín", ["Yauli"]),
    "Inmaculada (Hochschild)": (r"inmaculada|hochschild", "Ayacucho", ["Paucar del Sara Sara", "Parinacochas"]),
    "Marcona (Shougang)": (r"shougang|marcona", "Ica", ["Nazca"]),
    "Lagunas Norte (Boroo)": (r"lagunas norte|barrick|boroo", "La Libertad", ["Santiago de Chuco"]),
    "Minera Poderosa": (r"minera poderosa|la poderosa", "La Libertad", ["Pataz"]),
    "Volcan": (r"minera volcan|volcan compa", "Pasco", ["Pasco"]),
    "San Rafael (Minsur)": (r"minsur", "Puno", ["Melgar"]),
    "Corani (Bear Creek)": (r"corani|bear creek", "Puno", ["Carabaya"]),
}
NEGATIVO = re.compile(r"contamin|derram|incumpl|rechaz|denunci|abus|enga[ñn]|despoj|muert|herid|protest|\bparo\b|"
                      r"bloque|huelga|moviliz|exig|reclam|conflict|tensi[oó]n|malestar|indign|amenaz|desaloj|"
                      r"repres|afect|da[ñn]o|perjud|metales pesados|plomo|ars[eé]nico|polvo|rajadur|no queremos|"
                      r"traici|mient|corrup|estado de emergencia|sin consulta|enfrent|ultim[aá]tum", re.I)
POSITIVO = re.compile(r"\bacuerdo|di[aá]logo|mesa de (?:trabajo|desarrollo)|benefici|aporte|inversi[oó]n|desarrollo|"
                      r"empleo|convenio|(?<!in)cumpli[oó]|apoy|financi|construy|entreg|capacit|"
                      r"responsabilidad social|levant(?:an|aron) (?:el )?(?:paro|bloqueo)|tregua", re.I)
ALIAS = {n: re.compile(a, re.I) for n, (a, _, _) in PROYECTOS.items()}


def tono(texto):
    """(negativos, positivos, tono -1..1) en las frases que nombran el proyecto."""
    neg, pos = len(NEGATIVO.findall(texto)), len(POSITIVO.findall(texto))
    return neg, pos, (pos - neg) / (pos + neg) if pos + neg else 0.0


def menciones(texto):
    """[(proyecto, frases que lo nombran ± una frase)]."""
    frases = re.split(r"(?<=[.!?])\s+", texto)
    salida = []
    for nombre, rx in ALIAS.items():
        idx = [i for i, f in enumerate(frases) if rx.search(f)]
        if idx:
            ventana = sorted({j for i in idx for j in (i - 1, i, i + 1) if 0 <= j < len(frases)})
            salida.append((nombre, " ".join(frases[j] for j in ventana)))
    return salida


def provincias():
    """proyecto → ubigeos de provincia (4 dígitos), resueltos por nombre en el catálogo del INEI."""
    u = pd.read_csv(RAIZ / "tremor" / "ubigeo.csv", dtype=str)
    clave = {(norm(r.region), norm(r.provincia)): r.ubigeo[:4] for r in u.itertuples()}
    salida = {n: [clave[(norm(d), norm(p))] for p in ps] for n, (_, d, ps) in PROYECTOS.items()}
    assert all(len(v) == len(PROYECTOS[n][2]) for n, v in salida.items()), "provincia mal escrita"
    return salida


def actualizar(con, hoy=None):
    notas = pd.read_sql("SELECT id, medio, titular, resumen, substr(publicado, 1, 10) AS fecha, consulta FROM nota "
                        "WHERE publicado IS NOT NULL", con)
    filas = []
    for r in notas.itertuples():
        for nombre, frase in menciones(f"{r.titular}. {r.resumen or ''}"):
            neg, pos, t = tono(frase)
            filas.append((r.id, nombre, r.fecha, r.medio, "radio" if r.consulta == "radio" else "web", neg, pos, t))
    m = pd.DataFrame(filas, columns=["nota_id", "proyecto", "fecha", "medio", "origen", "negativos", "positivos", "tono"])
    m.to_sql("mencion", con, if_exists="replace", index=False)
    hoy = hoy or date.today()
    m["dias"] = (pd.Timestamp(hoy) - pd.to_datetime(m.fecha)).dt.days
    reciente, previo = m[m.dias.between(0, 6)], m[m.dias.between(7, 7 + 56 - 1)]
    a = pd.DataFrame({"menciones_7d": reciente.groupby("proyecto").size(),
                      "negativas_7d": reciente[reciente.tono < 0].groupby("proyecto").size(),
                      "tono_7d": reciente.groupby("proyecto").tono.mean(),
                      "base_7d": previo.groupby("proyecto").size() / 8}).reindex(list(PROYECTOS)).fillna(0)
    a["alza"] = (a.menciones_7d / a.base_7d.clip(lower=1)).round(2)  # ×veces lo normal (mínimo 1 de base)
    a["pct_negativo"] = (a.negativas_7d / a.menciones_7d.clip(lower=1)).round(2)
    a["aviso"] = pd.Series(avisos(reciente, previo)).reindex(a.index)
    prov = provincias()
    a = a.reset_index(names="proyecto").assign(provincias=lambda d: d.proyecto.map(lambda n: " ".join(prov[n])),
                                               hasta=str(hoy), creado=ahora())
    a.to_sql("animo", con, if_exists="replace", index=False)
    (DATOS / "exportes").mkdir(parents=True, exist_ok=True)
    a.to_csv(DATOS / "exportes" / "animo.csv", index=False)
    return m, a


def avisos(reciente, previo):
    """Proyecto → aviso de ánimo negativo: un pico (un día con ≥3 menciones negativas y ≥3× su día normal) o una
    racha (menciones negativas en ≥3 de los últimos 7 días). ponytail: umbrales a ojo, calibrar con los eventos."""
    neg = reciente[reciente.tono < 0].groupby(["proyecto", "fecha"]).size()
    normal = previo[previo.tono < 0].groupby("proyecto").size() / 56
    salida = {}
    for proyecto, dias in neg.groupby(level=0):
        dias = dias.droplevel(0)
        pico = dias[(dias >= 3) & (dias >= 3 * normal.get(proyecto, 0))]
        texto = [f"pico negativo el {d} ({n} menciones)" for d, n in pico.items()]
        if len(dias) >= 3:
            texto.append(f"racha negativa: {len(dias)} de los últimos 7 días")
        if texto:
            salida[proyecto] = "; ".join(texto)
    return salida


def senal(con):
    """Provincia (4 dígitos) → frase de ánimo para la alerta, solo de proyectos con menciones recientes."""
    try:
        a = pd.read_sql("SELECT * FROM animo WHERE menciones_7d > 0", con)
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        return {}
    salida = {}
    for r in a.sort_values("menciones_7d", ascending=False).itertuples():
        texto = (f"{r.proyecto}: {r.menciones_7d:.0f} menciones en 7 días (×{r.alza:g}), {r.pct_negativo:.0%} negativas"
                 + (f" — AVISO: {r.aviso}" if isinstance(r.aviso, str) else ""))
        for p in r.provincias.split():
            salida.setdefault(p, []).append(texto)
    return {p: "; ".join(v) for p, v in salida.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    m, a = actualizar(conectar())
    print(f"{len(m)} menciones en {m.nota_id.nunique()} notas ({(m.origen == 'radio').sum()} de radio)")
    print(a[a.menciones_7d > 0][["proyecto", "menciones_7d", "base_7d", "alza", "pct_negativo", "tono_7d"]]
          .sort_values("menciones_7d", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
