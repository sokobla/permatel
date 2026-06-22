"""
Dérivation centralisée des disponibilités fonctionnelles d'un tenant.

C'est l'UNIQUE endroit où les règles d'activation sont définies. Le frontend
ne recalcule rien : il consomme le map retourné ici.

Règles :
  - SMTP             : toujours actif (envoi système : invitations, support…).
  - IMAP (section)   : disponible ssi canal email activé.
  - Onglet MAIL      : visible ssi canal email ET SMTP+IMAP configurés.
  - Onglet CHAT      : visible ssi canal chat (disponibilité simple).
  - Intégrations     : disponible ssi canal chat OU téléphonie.
    - Slack          : ssi canal chat.
    - Téléphonie     : ssi canal téléphonie.
"""
from app.models.setting import SmtpSetting


def tenant_features(tenant) -> dict:
    ch = {
        "telephonie": bool(tenant.channel_telephonie),
        "email": bool(tenant.channel_email),
        "chat": bool(tenant.channel_chat),
    }

    cfg = SmtpSetting.query.filter_by(tenant_id=tenant.id).first()
    smtp_configured = bool(cfg and cfg.host and cfg.from_address)
    imap_configured = bool(cfg and cfg.imap_host and cfg.inbound_enabled)
    mail_ready = ch["email"] and smtp_configured and imap_configured

    return {
        "channels": ch,
        "config_state": {
            "smtp_configured": smtp_configured,
            "imap_configured": imap_configured,
        },
        "workspace_tabs": {
            "workspace": True,
            "mail": mail_ready,
            "chat": ch["chat"],
        },
        "settings_sections": {
            "general": True,
            "smtp": True,            # toujours actif
            "imap": ch["email"],
            "reference": True,
            "integrations": ch["chat"] or ch["telephonie"],
        },
        "integrations": {
            "slack": ch["chat"],
            "telephony": ch["telephonie"],
        },
    }
