"""Manda el informe en PDF de cada empresa del piloto: por Telegram (el mismo bot y chat de los avisos) y por correo
si hay cuenta SMTP. Sin claves, solo genera los PDF y dice qué mandaría.

    python -m tremor.envio

Secretos: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID; para el correo SMTP_USER, SMTP_PASSWORD (en Gmail, una contraseña de
aplicación), CORREO_PARA (uno o varios, separados por coma) y, si no es Gmail, SMTP_HOST.
ponytail: un solo chat y una sola lista de correo para todo el piloto; con clientes reales, uno por empresa."""
import os
import smtplib
from datetime import date
from email.message import EmailMessage

import requests

from tremor import informe_pdf

PILOTO = {"bateas": "Bateas", "raura": "Raura", "poderosa": "Poderosa", "bambas": "Las Bambas"}
ENLACE = "https://nicosil02.github.io/tremor/"


def telegram(pdf, texto):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print(f"(sin Telegram) mandaría {pdf.name}: {texto}")
        return False
    with open(pdf, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", timeout=60,
                          data={"chat_id": chat, "caption": texto}, files={"document": (pdf.name, f, "application/pdf")})
    print(f"Telegram {pdf.name}: {'enviado' if r.ok else r.status_code}")
    return r.ok


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
    for k, p in zip(PILOTO, pdfs):
        telegram(p, f"Tremor, informe de riesgo social de {PILOTO[k]} al {hoy}. Avisos al día en {ENLACE}")
    correo(pdfs, hoy)


if __name__ == "__main__":
    main()
