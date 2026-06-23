"""
Service notifications — émission (in-app + file email) et dispatch.

`notify()` est NON BLOQUANT pour le métier : toute erreur est avalée (log), elle
ne doit jamais faire échouer la transaction appelante. L'appelant committe.
"""
from datetime import datetime
from email.message import EmailMessage

from flask import current_app

from app import db
from app.models.notification import Notification, NotificationPreference, EmailOutbox
from app.models.tenant_user import TenantUser, MEMBERSHIP_ADMIN
from app.models.user import User
from app.models.setting import SmtpSetting
from app.utils.mailer import send_via_smtp

# Email activé par défaut uniquement pour les notifications "high".
EMAIL_DEFAULT_SEVERITIES = {"high"}


def tenant_members(tenant_id, roles=None, membership_admin=False):
    """Membres actifs d'un tenant (option : filtrer par rôle global, ou admins de tenant)."""
    q = (TenantUser.query.filter_by(tenant_id=tenant_id, is_active=True)
         .join(User, TenantUser.user_id == User.id)
         .filter(User.is_active.is_(True)))
    out = []
    for m in q.all():
        u = m.user
        if roles and (not u.role or u.role.value not in roles):
            # garder aussi les admins de tenant si demandé
            if not (membership_admin and m.membership_role == MEMBERSHIP_ADMIN):
                continue
        out.append(u)
    # dédoublonnage
    return list({u.id: u for u in out}.values())


def _resolve_pref(tenant_id, user_id, type_, severity):
    p = NotificationPreference.query.filter_by(tenant_id=tenant_id, user_id=user_id, type=type_).first()
    if p:
        return p.in_app, p.email
    return True, (severity in EMAIL_DEFAULT_SEVERITIES)


def _smtp_ready(tenant_id):
    cfg = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()
    return bool(cfg and cfg.host and cfg.from_address)


def notify(tenant_id, users, type_, *, title, body=None, severity="normal",
           entity_type=None, entity_id=None):
    """Crée les notifs in-app + met en file les emails selon les préférences."""
    smtp_ok = None
    for u in users:
        try:
            in_app, email = _resolve_pref(tenant_id, u.id, type_, severity)
            if in_app:
                db.session.add(Notification(
                    tenant_id=tenant_id, user_id=u.id, type=type_, severity=severity,
                    title=title, body=body, entity_type=entity_type, entity_id=entity_id,
                ))
            if email and u.email:
                if smtp_ok is None:
                    smtp_ok = _smtp_ready(tenant_id)
                if smtp_ok:
                    db.session.add(EmailOutbox(
                        tenant_id=tenant_id, to_address=u.email,
                        subject=f"[PERMATEL] {title}", body_text=body or title,
                    ))
        except Exception as exc:  # noqa: BLE001 — ne jamais casser le métier
            current_app.logger.warning(f"notify() échec pour user={getattr(u,'id',None)} : {exc}")
    try:
        db.session.flush()
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning(f"notify() flush échec : {exc}")


def dispatch_emails(db, limit=100) -> dict:
    """Envoie les emails en file via le SMTP du tenant. Pour le cron."""
    rows = EmailOutbox.query.filter_by(status="pending").limit(limit).all()
    sent = failed = 0
    for r in rows:
        cfg = SmtpSetting.query.filter_by(tenant_id=r.tenant_id).first()
        if not cfg or not cfg.host or not cfg.from_address:
            r.status, r.error = "failed", "SMTP non configuré"
            failed += 1
            continue
        try:
            msg = EmailMessage()
            msg["From"] = cfg.from_address
            msg["To"] = r.to_address
            msg["Subject"] = r.subject
            msg.set_content(r.body_text or r.subject)
            send_via_smtp(cfg, msg)
            r.status, r.sent_at = "sent", datetime.utcnow()
            sent += 1
        except Exception as exc:  # noqa: BLE001
            r.attempts += 1
            r.error = str(exc)
            r.status = "failed" if r.attempts >= 3 else "pending"
            failed += 1
    db.session.commit()
    return {"sent": sent, "failed": failed}
