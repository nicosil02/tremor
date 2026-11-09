"""De qué trata cada nota y su tono hacia la empresa, con un transformer de inferencia (NLI) multilingüe en
clasificación sin entrenamiento (zero-shot): mDeBERTa-v3 base, local, sin cuota. El léxico de tremor.animo marcaba
"Fiscalía pide prisión para defensores por las protestas del 2015" como crítica y la página la ponía junto a las
protestas; con esto queda como proceso judicial que solo informa.

    python -m tremor.clasifica        # notas de menciones (30 días) y de eventos (45 días) aún sin clasificar

El resultado queda en `nota_tema`: tremor.web lo lee sin necesitar transformers. Sin transformers, no hace nada."""
from datetime import date, timedelta

from tremor.db import conectar

MODELO = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
TEMAS = {
    "protesta": "una protesta, paro o bloqueo que ocurre ahora o está anunciado",
    "judicial": "un proceso judicial o fiscal",
    "dialogo": "una mesa de diálogo, reunión o acuerdo",
    "aporte": "una donación, obra o programa social de la empresa",
    "ambiente": "contaminación o daño ambiental",
    "otro": "otro tema",
}
# El tono se pregunta por lo que hace la nota con la empresa. En procesos judiciales el modelo falla ("victoria para
# defensores" sale favorable a la minera): ahí queda en 0 y la página solo dice "Proceso judicial".
TONOS = {-1: "la noticia cuestiona o denuncia a la empresa", 1: "la noticia destaca algo bueno que hizo la empresa",
         0: "la noticia no juzga a la empresa"}


def pendientes(con, dias_menciones=30, dias_eventos=45):
    hoy = date.today()
    return con.execute(
        """SELECT DISTINCT n.id, n.titular, substr(COALESCE(n.resumen, ''), 1, 300) FROM nota n
           WHERE n.id NOT IN (SELECT nota_id FROM nota_tema) AND (
             n.id IN (SELECT nota_id FROM mencion WHERE fecha >= ?) OR
             n.id IN (SELECT en.nota_id FROM evento_nota en JOIN evento_prensa e ON e.id = en.evento_id
                      WHERE COALESCE(e.fecha_evento, e.fecha_anuncio) >= ?))""",
        ((hoy - timedelta(days=dias_menciones)).isoformat(), (hoy - timedelta(days=dias_eventos)).isoformat())).fetchall()


def main():
    con = conectar()
    con.execute("CREATE TABLE IF NOT EXISTS nota_tema (nota_id TEXT PRIMARY KEY, tema TEXT, p_tema REAL, tono INTEGER, p_tono REAL)")
    notas = pendientes(con)
    if not notas:
        return
    try:
        from transformers import pipeline
    except ImportError:
        print("Sin transformers: las notas quedan sin clasificar")
        return
    p = pipeline("zero-shot-classification", model=MODELO, device=-1)
    inv_t, inv_o = {v: k for k, v in TEMAS.items()}, {v: k for k, v in TONOS.items()}
    for id_, tit, res in notas:
        x = f"{tit}. {res}"
        a = p(x, list(TEMAS.values()), hypothesis_template="Esta noticia trata de {}.")
        b = p(x, list(TONOS.values()), hypothesis_template="{}.")
        tema = inv_t[a["labels"][0]]
        con.execute("INSERT OR REPLACE INTO nota_tema VALUES (?, ?, ?, ?, ?)",
                    (id_, tema, round(a["scores"][0], 3), 0 if tema == "judicial" else inv_o[b["labels"][0]], round(b["scores"][0], 3)))
        con.commit()
    print(f"{len(notas)} notas clasificadas")


if __name__ == "__main__":
    main()
