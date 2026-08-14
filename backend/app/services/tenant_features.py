"""
Dérivation centralisée des disponibilités fonctionnelles d'un tenant.

C'est l'UNIQUE endroit où les règles d'activation sont définies. Le frontend
ne recalcule rien : il consomme le map retourné ici.

Règles :
  - SMTP             : toujours actif (envoi système : invitations, support…).
  - IMAP (section)   : disponible ssi canal email activé.
  - Onglet MAIL      : visible ssi canal email ET SMTP+IMAP configurés.
  - Onglet CHAT      : visible ssi canal chat (disponibilité simple).
  - Intégrations     : disponible ssi canal chat OU téléphonie OU erp.
    - Slack          : ssi canal chat.
    - Téléphonie     : ssi canal téléphonie activé sur le tenant — le bouton
                        « Configurer » (Intégrations) ne dépend plus de
                        `telephony_configured` (Phase 13) : un admin doit
                        pouvoir ouvrir le panneau de configuration avant
                        d'avoir créé son premier connecteur, pas seulement
                        après. `telephony_configured` reste exposé dans
                        `config_state` pour ce qui en dépend réellement
                        (ex. onglet Supervision > Téléphonie, qui a besoin
                        de données pour être utile).
    - ERP            : même motif que téléphonie — ssi canal `channel_erp`
                        activé (admin global), indépendamment de
                        `erp_configured` (Phase 6, ODOO_INTEGRATION_PLAN.md).
"""
from app.models.setting import SmtpSetting
from app.models.pbx import PbxConnector
from app.models.erp import ErpConfig


def tenant_features(tenant) -> dict:
    ch = {
        "telephonie": bool(tenant.channel_telephonie),
        "email": bool(tenant.channel_email),
        "chat": bool(tenant.channel_chat),
        "erp": bool(tenant.channel_erp),
    }

    cfg = SmtpSetting.query.filter_by(tenant_id=tenant.id).first()
    smtp_configured = bool(cfg and cfg.host and cfg.from_address)
    imap_configured = bool(cfg and cfg.imap_host and cfg.inbound_enabled)
    mail_ready = ch["email"] and smtp_configured and imap_configured

    telephony_configured = bool(
        PbxConnector.query.filter_by(tenant_id=tenant.id, is_active=True).first()
    )

    erp_cfg = ErpConfig.query.filter_by(tenant_id=tenant.id).first()
    erp_configured = bool(erp_cfg and erp_cfg.company_id)

    return {
        "channels": ch,
        "config_state": {
            "smtp_configured": smtp_configured,
            "imap_configured": imap_configured,
            "telephony_configured": telephony_configured,
            "erp_configured": erp_configured,
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
            "integrations": ch["chat"] or ch["telephonie"] or ch["erp"],
        },
        "integrations": {
            "slack": ch["chat"],
            "telephony": ch["telephonie"],
            "erp": ch["erp"],
        },
    }
