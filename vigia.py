"""
Vigía de citas - Consulado General de España en Ciudad de México
Revisa si hay horas disponibles para el trámite de pasaporte y envía
un correo de alerta si detecta cambios.
"""

import os
import smtplib
import sys
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

URL = "https://www.citaconsular.es/es/hosteds/widgetdefault/2d8bebcf444f3db762074e5daef723a59/#services"
TEXTO_SIN_CITAS = "No hay horas disponibles"


def enviar_telegram(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram no configurado, se omite ese aviso.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": texto}).encode()

    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as resp:
            resp.read()
    except Exception as e:
        print(f"Error enviando Telegram: {e}")


def enviar_correo(asunto, cuerpo):
    remitente = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    destinatario = os.environ["ALERT_EMAIL"]

    msg = MIMEText(cuerpo)
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destinatario

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())


def revisar_citas():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Acepta automáticamente el cuadro de diálogo "Welcome/Bienvenido"
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(URL, wait_until="networkidle", timeout=60000)

        # Clic en el botón verde "Continue / Continuar"
        try:
            page.click("text=Continue / Continuar", timeout=15000)
        except Exception:
            pass  # puede que ya haya pasado esa pantalla

        page.wait_for_timeout(5000)  # da tiempo a que cargue el resultado

        contenido = page.content()
        browser.close()

        return contenido


def main():
    contenido = revisar_citas()

    if TEXTO_SIN_CITAS in contenido:
        print("Sigue sin haber citas disponibles. No se envía alerta.")
    else:
        print("¡Posible cambio detectado! Enviando alertas.")
        mensaje = (
            "⚠️ Posible cita disponible - Pasaporte español CDMX\n\n"
            "El sistema de citas ya no muestra el mensaje de "
            "'No hay horas disponibles'. Entra de inmediato a:\n\n"
            f"{URL}\n\n"
            "Es posible que se haya abierto un hueco. ¡Corre!"
        )

        enviar_correo(
            asunto="⚠️ Posible cita disponible - Pasaporte español CDMX",
            cuerpo=mensaje,
        )
        enviar_telegram(mensaje)


if __name__ == "__main__":
    main()
