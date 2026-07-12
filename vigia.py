"""
Vigía de citas - Consulado General de España en Ciudad de México
Revisa si hay horas disponibles para el trámite de pasaporte y envía
un correo de alerta si detecta cambios.
"""

import os
import smtplib
import sys
import time
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright
import requests

URL = "https://www.citaconsular.es/es/hosteds/widgetdefault/2d8bebcf444f3db762074e5daef723a59/#services"
TEXTO_SIN_CITAS = "No hay horas disponibles"
MARCADORES_PAGINA_NORMAL = ["bookitit", "Historial y cancelaciones"]


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


def enviar_telegram_foto(caption, ruta_imagen):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram no configurado, se omite el envío de foto.")
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(ruta_imagen, "rb") as foto:
            requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": foto},
                timeout=30,
            )
    except Exception as e:
        print(f"Error enviando foto por Telegram: {e}")


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

        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(URL, wait_until="networkidle", timeout=60000)

        try:
            page.click("text=Continue / Continuar", timeout=15000)
        except Exception:
            pass  # puede que ya haya pasado esa pantalla

        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass

        contenido = ""
        for intento in range(3):
            page.wait_for_timeout(4000)
            contenido = page.content()
            if TEXTO_SIN_CITAS in contenido or any(
                m in contenido for m in MARCADORES_PAGINA_NORMAL
            ):
                break
            print(f"Intento {intento + 1}: página aún no muestra un estado reconocible, reintentando...")

        ruta_captura = "captura.png"
        try:
            page.screenshot(path=ruta_captura, full_page=True)
        except Exception as e:
            print(f"No se pudo tomar captura: {e}")
            ruta_captura = None

        browser.close()

        return contenido, ruta_captura


def main():
    try:
        contenido, captura = revisar_citas()
    except Exception as e:
        print(f"Error técnico al revisar la página: {e}")
        enviar_telegram(
            f"🔧 El vigía tuvo un error técnico al entrar a la página "
            f"(posible bloqueo o cambio en el sitio):\n\n{e}"
        )
        sys.exit(1)

    pagina_parece_normal = any(m in contenido for m in MARCADORES_PAGINA_NORMAL)

    if TEXTO_SIN_CITAS in contenido:
        print("Sigue sin haber citas disponibles. No se envía alerta.")
    elif not pagina_parece_normal:
        print("La página no tiene la estructura esperada tras varios intentos. Posible bloqueo o cambio en el sitio.")
        mensaje_bloqueo = (
            "⚠️ El vigía no reconoció la página del consulado tras varios "
            "intentos (posible bloqueo temporal o cambio en el sitio). "
            "No se detectó una cita real, pero revisa manualmente si esto se repite."
        )
        if captura:
            enviar_telegram_foto(mensaje_bloqueo, captura)
        else:
            enviar_telegram(mensaje_bloqueo)
    else:
        print("¡Posible cambio detectado! Enviando alertas.")
        mensaje = (
            "⚠️ Posible cita disponible - Pasaporte español CDMX\n\n"
            "El sistema de citas ya no muestra el mensaje de "
            "'No hay horas disponibles'. Entra de inmediato a:\n\n"
            f"{URL}\n\n"
            "Revisa la captura adjunta antes de correr, por si acaso."
        )

        enviar_correo(
            asunto="⚠️ Posible cita disponible - Pasaporte español CDMX",
            cuerpo=mensaje,
        )
        if captura:
            enviar_telegram_foto(mensaje, captura)
        else:
            enviar_telegram(mensaje)


if __name__ == "__main__":
    main()
