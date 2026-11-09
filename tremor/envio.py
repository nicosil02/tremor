"""Manda por correo el informe en PDF de cada empresa del piloto, si hay cuenta SMTP. Sin claves, solo genera los PDF.
Telegram queda solo para los avisos de la operación del cliente (tremor.avisos), no para el informe.

    python -m tremor.envio

Secretos: SMTP_USER, SMTP_PASSWORD (en Gmail, una contraseña de
aplicación), CORREO_PARA (uno o varios, separados por coma) y, si no es Gmail, SMTP_HOST.
ponytail: una sola lista de correo para todo el piloto; con clientes reales, una por empresa. Falta diseñar el correo."""
import os
import smtplib
from datetime import date
from email.message import EmailMessage

from tremor import informe_pdf

PILOTO = {"bateas": "Bateas", "raura": "Raura", "poderosa": "Poderosa", "bambas": "Las Bambas"}
ENLACE = "https://nicosil02.github.io/tremor/"


def correo(pdfs, hoy):
    usuario, clave, para = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD"), os.environ.get("CORREO_PARA")
    if not (usuario and clave and para):
        print(f"(sin correo) mandaría {len(pdfs)} informes a CORREO_PARA")
        return False
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = f"Tremor: informe de riesgo social al {hoy}", usuario, para
    m.set_content(f"Adjuntos, los informes de riesgo social de sus operaciones al {hoy}.\n\nLa app con los avisos al día: {ENLACE}\n\nTremor")
    for p in pdfs:
        m.add_attachment(p.read_bytes(), maintype="application", subtype="pdf", filename=p.name)
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), 465, timeout=60) as s:
        s.login(usuario, clave)
        s.send_message(m)
    print(f"Correo enviado a {para.count(',') + 1} destinatario(s)")
    return True


def main():
    informe_pdf.main()
    hoy = date.today().strftime("%d/%m/%Y")
    pdfs = [informe_pdf.DOCS / "informes" / f"informe-{k}.pdf" for k in PILOTO]
    correo(pdfs, hoy)


if __name__ == "__main__":
    main()
