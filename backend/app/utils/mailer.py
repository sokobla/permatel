"""Envoi d'emails via la configuration SMTP d'un tenant."""
import smtplib

from app.utils.crypto import decrypt_secret


def send_via_smtp(cfg, msg):
    """
    Envoie un email.message.EmailMessage via la config SMTP fournie
    (objet SmtpSetting ; mot de passe chiffré, déchiffré ici).
    Lève une exception en cas d'échec (à gérer par l'appelant).
    """
    security = (cfg.security or "tls").lower()
    if security == "ssl":
        server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=15)
    else:
        server = smtplib.SMTP(cfg.host, cfg.port, timeout=15)
        server.ehlo()
        if security == "tls":
            server.starttls()
            server.ehlo()
    pwd = decrypt_secret(cfg.password)
    if cfg.username and pwd:
        server.login(cfg.username, pwd)
    server.send_message(msg)
    server.quit()
