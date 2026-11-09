"""El informe mensual en PDF, igual para todos: se imprime con Chromium (Playwright) en vez de depender de la
impresora y los márgenes del navegador de cada usuario. Deja docs/informes/informe-<empresa>.pdf.
`python -m tremor.informe_pdf`"""
import functools
import http.server
import threading
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
EMPRESAS = ("bambas", "southern", "antamina", "yanacocha")  # las mismas de docs/informe.html


def main():
    from playwright.sync_api import sync_playwright
    class Callado(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    manejador = functools.partial(Callado, directory=str(DOCS))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    (DOCS / "informes").mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pag = b.new_page()
        pag.route("https://raw.githubusercontent.com/**", lambda r: r.abort())  # usa docs/web.json
        for k in EMPRESAS:
            pag.goto(f"http://127.0.0.1:{srv.server_port}/informe.html?e={k}")
            pag.wait_for_selector(".evaluacion", timeout=60_000)
            pag.evaluate("document.fonts.ready.then(() => 1)")
            pag.emulate_media(media="print")
            salida = DOCS / "informes" / f"informe-{k}.pdf"
            pag.pdf(path=str(salida), format="A4", print_background=True, prefer_css_page_size=True)
            pag.emulate_media(media="screen")
            print(f"{salida.relative_to(DOCS.parent)}  {salida.stat().st_size // 1024} KB")
        b.close()
    srv.shutdown()


if __name__ == "__main__":
    main()
