"""
Collecte des emails entrants (Phase 2) — relève IMAP par tenant.

Pour chaque tenant ayant `inbound_enabled=True` :
  - connexion IMAP (SSL / STARTTLS / none),
  - relève des messages NON LUS de la boîte de réception,
  - déduplication par Message-ID (puis UID),
  - insertion en `emails(direction='inbound', status='non_lu')`,
  - rattachement automatique au contact (from_address ↔ Contact.email),
  - sauvegarde des pièces jointes,
  - marquage \\Seen sur le serveur.

Utilisable :
  - CLI Flask :   flask mail-fetch
  - cron      :   python backend/scripts/mail_fetch.py
"""
import email
import imaplib
import os
import uuid
from email import policy
from email.utils import parseaddr, parsedate_to_datetime

import click
from flask import current_app
from werkzeug.utils import secure_filename

from app.models.setting import SmtpSetting
from app.models.email import Email
from app.models.email_attachment import EmailAttachment
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.utils.crypto import decrypt_secret, encrypt_bytes


def _connect(cfg):
    security = (cfg.imap_security or "ssl").lower()
    if security == "ssl":
        client = imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port, timeout=20)
    else:
        client = imaplib.IMAP4(cfg.imap_host, cfg.imap_port, timeout=20)
        if security == "starttls":
            client.starttls()
    pwd = decrypt_secret(cfg.imap_password)
    if cfg.imap_username and pwd:
        client.login(cfg.imap_username, pwd)
    return client


def _bodies(msg):
    """Retourne (texte_plain, html). Le texte est dérivé du HTML si absent."""
    import re
    text, html = "", None
    try:
        p_plain = msg.get_body(preferencelist=("plain",))
        if p_plain is not None:
            text = p_plain.get_content()
        p_html = msg.get_body(preferencelist=("html",))
        if p_html is not None:
            html = p_html.get_content()
        if not text and html:
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    except Exception:  # noqa: BLE001
        pass
    return text, html


def _att_dir():
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "email_attachments")
    os.makedirs(folder, exist_ok=True)
    return folder


def fetch_inbound_for_tenant(db, cfg):
    """Relève et insère les nouveaux emails d'un tenant. Retourne le nb inséré."""
    tenant_id = cfg.tenant_id
    inserted = 0
    client = _connect(cfg)
    try:
        client.select("INBOX")
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            return 0
        uids = data[0].split()
        for uid in uids:
            st, msg_data = client.fetch(uid, "(RFC822)")
            if st != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw, policy=policy.default)

            message_id = (msg["message-id"] or "").strip() or None
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)

            # Déduplication
            dup = None
            if message_id:
                dup = Email.query.filter_by(tenant_id=tenant_id, message_id=message_id).first()
            if not dup:
                dup = Email.query.filter_by(tenant_id=tenant_id, imap_uid=uid_str, direction="inbound").first()
            if dup:
                client.store(uid, "+FLAGS", "\\Seen")
                continue

            from_address = parseaddr(msg["from"] or "")[1] or None
            try:
                received_at = parsedate_to_datetime(msg["date"]) if msg["date"] else None
            except Exception:  # noqa: BLE001
                received_at = None
            in_reply_to = (msg["in-reply-to"] or "").strip() or None
            _body, _html = _bodies(msg)

            # Matching contact
            contact = None
            if from_address:
                contact = Contact.query.filter(
                    Contact.tenant_id == tenant_id,
                    Contact.email.ilike(from_address),
                ).first()

            record = Email(
                tenant_id=tenant_id,
                direction="inbound",
                status="non_lu",
                message_id=message_id,
                in_reply_to=in_reply_to,
                thread_id=in_reply_to or message_id,
                from_address=from_address,
                to_addresses=msg["to"],
                cc=msg["cc"],
                subject=msg["subject"],
                body_text=_body,
                body_html=_html,
                contact_id=contact.id if contact else None,
                imap_uid=uid_str,
                received_at=received_at,
            )
            db.session.add(record)
            db.session.flush()

            # Pièces jointes
            saved = 0
            for part in msg.iter_attachments():
                fname = part.get_filename()
                if not fname:
                    continue
                payload = part.get_payload(decode=True) or b""
                _, ext = os.path.splitext(fname)
                stored = secure_filename(f"{tenant_id}_{uuid.uuid4().hex}{ext.lower()}")
                path = os.path.join(_att_dir(), stored)
                with open(path, "wb") as fh:
                    fh.write(encrypt_bytes(payload))  # chiffré au repos
                db.session.add(EmailAttachment(
                    email_id=record.id, tenant_id=tenant_id, filename=fname,
                    content_type=part.get_content_type(), size=len(payload), storage_path=path,
                ))
                saved += 1
            if saved:
                record.has_attachments = True

            client.store(uid, "+FLAGS", "\\Seen")
            inserted += 1

        db.session.commit()
    finally:
        try:
            client.logout()
        except Exception:  # noqa: BLE001
            pass
    return inserted


def fetch_all(db):
    """Relève tous les tenants dont la réception IMAP est activée."""
    configs = SmtpSetting.query.filter(
        SmtpSetting.inbound_enabled.is_(True),
        SmtpSetting.imap_host.isnot(None),
    ).all()

    summary = {}
    for cfg in configs:
        tenant = Tenant.query.get(cfg.tenant_id)
        label = tenant.code if tenant else str(cfg.tenant_id)
        try:
            summary[label] = fetch_inbound_for_tenant(db, cfg)
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            summary[label] = f"ERREUR: {exc}"
    return summary
