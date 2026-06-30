import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_REMITENTE = "noreply@retache.com.mx"


def enviar_email(destinatario: str, asunto: str, contenido_html: str) -> bool:
    try:
        mensaje = Mail(
            from_email=EMAIL_REMITENTE,
            to_emails=destinatario,
            subject=asunto,
            html_content=contenido_html,
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(mensaje)
        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False


def email_verificacion(destinatario: str, nombre: str, token: str, tipo: str):
    base_url = "https://retache.com.mx"
    url = f"{base_url}/verificar-email/{token}"
    html = f"""
    <div style="font-family:-apple-system,sans-serif; max-width:520px; margin:0 auto; padding:32px;">
      <div style="text-align:center; margin-bottom:24px;">
        <h1 style="color:#0E6BB8; font-size:28px; margin:0;">🚛 RETACHE</h1>
        <p style="color:#6B6B68; margin-top:4px;">Logística inversa para México</p>
      </div>
      <div style="background:#F7F7F5; border-radius:12px; padding:24px; margin-bottom:24px;">
        <h2 style="font-size:20px; margin-bottom:8px;">Hola, {nombre} 👋</h2>
        <p style="color:#6B6B68; line-height:1.6;">Gracias por registrarte en RETACHE. Confirma tu correo electrónico para activar tu cuenta.</p>
        <div style="text-align:center; margin:24px 0;">
          <a href="{url}" style="background:#0E6BB8; color:white; padding:14px 32px; border-radius:8px; text-decoration:none; font-weight:600; font-size:16px;">
            Verificar mi email →
          </a>
        </div>
        <p style="color:#6B6B68; font-size:13px; text-align:center;">Este enlace expira en 24 horas.</p>
      </div>
      <p style="color:#6B6B68; font-size:12px; text-align:center;">Si no creaste una cuenta en RETACHE, ignora este mensaje.</p>
    </div>
    """
    return enviar_email(destinatario, "Verifica tu email — RETACHE", html)


def email_recuperar_contrasena(destinatario: str, nombre: str, token: str):
    base_url = "https://retache.com.mx"
    url = f"{base_url}/restablecer-contrasena/{token}"
    html = f"""
    <div style="font-family:-apple-system,sans-serif; max-width:520px; margin:0 auto; padding:32px;">
      <div style="text-align:center; margin-bottom:24px;">
        <h1 style="color:#0E6BB8; font-size:28px; margin:0;">🚛 RETACHE</h1>
        <p style="color:#6B6B68; margin-top:4px;">Logística inversa para México</p>
      </div>
      <div style="background:#F7F7F5; border-radius:12px; padding:24px; margin-bottom:24px;">
        <h2 style="font-size:20px; margin-bottom:8px;">Hola, {nombre} 👋</h2>
        <p style="color:#6B6B68; line-height:1.6;">Recibimos una solicitud para restablecer tu contraseña. Si no fuiste tú, ignora este mensaje.</p>
        <div style="text-align:center; margin:24px 0;">
          <a href="{url}" style="background:#0E6BB8; color:white; padding:14px 32px; border-radius:8px; text-decoration:none; font-weight:600; font-size:16px;">
            Restablecer contraseña →
          </a>
        </div>
        <p style="color:#6B6B68; font-size:13px; text-align:center;">Este enlace expira en 1 hora.</p>
      </div>
      <p style="color:#6B6B68; font-size:12px; text-align:center;">Si no solicitaste restablecer tu contraseña, ignora este mensaje.</p>
    </div>
    """
    return enviar_email(destinatario, "Restablece tu contraseña — RETACHE", html)