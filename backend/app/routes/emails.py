"""
Canal Mail — Phase 1 : envoi sortant vers les contacts enregistrés, avec
pièces jointes.

POST   /api/emails                         envoie (JSON ou multipart data+files)
GET    /api/emails                         liste (filtres direction/contact/demande)
GET    /api/emails/<id>                     détail (+ pièces jointes)
GET    /api/emails/<id>/attachments/<aid>/download
GET    /api/emails/stats                    KPI (tenant, ?from=&to=&user_id=)
"""
import json
import os
import re
import smtplib  # noqa: F401 (utilisé indirectement via mailer)
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid

from flask import Blueprint, jsonify, request, current_app, send_file
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from werkzeug.utils import secure_filename

from app import db
from app.models.email import Email
from app.models.email_attachment import EmailAttachment
from app.models.setting import SmtpSetting
from app.models.contact import Contact
from app.models.demande import Demande
from app.models.interaction import Interaction, TypeInteraction
from app.utils.mailer import send_via_smtp
from app.utils.crypto import encrypt_bytes, decrypt_bytes

emails_bp = Blueprint("emails", __name__, url_prefix="/api/emails")
CORS(emails_bp, supports_credentials=True)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ALLOWED_ATT_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".zip",
}
MAX_ATT_MB = 10


def _tenant_uuid():
    tid = get_jwt().get("tid")
    if not tid:
        return None, (jsonify({"error": "Aucun tenant actif sélectionné."}), 400)
    try:
        return uuid.UUID(tid), None
    except (ValueError, TypeError):
        return None, (jsonify({"error": "Tenant invalide."}), 400)


def _att_dir():
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "email_attachments")
    os.makedirs(folder, exist_ok=True)
    return folder


def _save_attachment(file, tenant_id):
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in ALLOWED_ATT_EXT:
        raise ValueError(f"Type de fichier non autorisé : {ext}")
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_ATT_MB * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux (max {MAX_ATT_MB} Mo) : {file.filename}")
    raw = file.read()
    stored = secure_filename(f"{tenant_id}_{uuid.uuid4().hex}{ext.lower()}")
    path = os.path.join(_att_dir(), stored)
    with open(path, "wb") as fh:
        fh.write(encrypt_bytes(raw))  # chiffré au repos
    return {"filename": file.filename, "content_type": file.content_type,
            "size": size, "storage_path": path, "content": raw}


@emails_bp.post("")
@jwt_required()
def send_email():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    user_id = int(get_jwt_identity())

    # Parse JSON ou multipart (data JSON + fichiers 'attachments')
    files = []
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        try:
            data = json.loads(request.form.get("data") or "{}")
        except json.JSONDecodeError:
            return jsonify({"error": "JSON invalide dans 'data'."}), 400
        files = request.files.getlist("attachments")
    else:
        data = request.get_json(silent=True) or {}

    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()
    demande_id = data.get("demande_id")
    contact_id = data.get("to_contact_id")

    # Cc : liste ou chaîne séparée par virgules/points-virgules
    cc_raw = data.get("cc") or []
    if isinstance(cc_raw, str):
        cc_raw = re.split(r"[,;]", cc_raw)
    cc_list = [c.strip() for c in cc_raw if c and c.strip()]
    invalid_cc = [c for c in cc_list if not EMAIL_RE.match(c)]
    if invalid_cc:
        return jsonify({"error": f"Cc invalide : {', '.join(invalid_cc)}"}), 422

    contact = None
    if contact_id:
        contact = Contact.query.filter_by(id=contact_id, tenant_id=tenant_id).first()
        if not contact:
            return jsonify({"error": "Contact introuvable dans ce tenant."}), 404
        to_address = contact.email
        if not to_address:
            return jsonify({"error": "Ce contact n'a pas d'adresse email."}), 422
    else:
        to_address = (data.get("to") or "").strip()

    if not to_address or not EMAIL_RE.match(to_address):
        return jsonify({"error": "Destinataire invalide."}), 422
    if not subject:
        return jsonify({"error": "L'objet est obligatoire."}), 422
    if not body:
        return jsonify({"error": "Le message est obligatoire."}), 422

    cfg = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()
    if not cfg or not cfg.host or not cfg.from_address:
        return jsonify({"error": "SMTP non configuré pour ce tenant."}), 400

    # Sauvegarde des pièces jointes (avant envoi)
    saved = []
    try:
        for f in files:
            if f and f.filename:
                saved.append(_save_attachment(f, tenant_id))
    except ValueError as e:
        for s in saved:
            try: os.remove(s["storage_path"])
            except OSError: pass
        return jsonify({"error": str(e)}), 422

    # Construction du message
    # Réponse threadée éventuelle
    original = None
    reply_to_id = data.get("reply_to")
    if reply_to_id:
        original = Email.query.filter_by(id=reply_to_id, tenant_id=tenant_id).first()

    msg = EmailMessage()
    msg["From"] = cfg.from_address
    msg["To"] = to_address
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    message_id = make_msgid()
    msg["Message-ID"] = message_id
    if original and original.message_id:
        msg["In-Reply-To"] = original.message_id
        msg["References"] = original.message_id
    msg.set_content(body)
    for s in saved:
        maintype, _, subtype = (s["content_type"] or "application/octet-stream").partition("/")
        msg.add_attachment(s["content"], maintype=maintype or "application",
                           subtype=subtype or "octet-stream", filename=s["filename"])

    record = Email(
        tenant_id=tenant_id, direction="outbound", message_id=message_id,
        from_address=cfg.from_address, to_addresses=to_address,
        cc=", ".join(cc_list) if cc_list else None,
        subject=subject, body_text=body, contact_id=contact.id if contact else None,
        demande_id=demande_id, user_id=user_id, has_attachments=bool(saved),
        in_reply_to=original.message_id if original else None,
        thread_id=(original.thread_id or original.message_id) if original else None,
    )

    try:
        send_via_smtp(cfg, msg)
        record.status = "sent"
        record.sent_at = datetime.utcnow()
    except Exception as exc:  # noqa: BLE001
        record.status = "failed"
        record.error = str(exc)
        db.session.add(record)
        db.session.commit()
        return jsonify({"error": f"Échec de l'envoi : {exc}", "email": record.to_dict()}), 502

    db.session.add(record)
    db.session.flush()  # pour récupérer record.id
    for s in saved:
        db.session.add(EmailAttachment(
            email_id=record.id, tenant_id=tenant_id, filename=s["filename"],
            content_type=s["content_type"], size=s["size"], storage_path=s["storage_path"],
        ))

    if demande_id:
        demande = Demande.query.filter_by(id=demande_id, tenant_id=tenant_id).first()
        if demande:
            db.session.add(Interaction(
                demande_id=demande_id, user_id=user_id, tenant_id=tenant_id,
                contact_id=contact.id if contact else None,
                type_interaction=TypeInteraction.EMAIL,
                contenu=f"[Email] {subject}\n\n{body}",
            ))

    db.session.commit()
    return jsonify(_email_full(record)), 201


def _email_full(email):
    data = email.to_dict()
    data["attachments"] = [
        a.to_dict() for a in EmailAttachment.query.filter_by(email_id=email.id).all()
    ]
    return data


@emails_bp.get("")
@jwt_required()
def list_emails():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    direction = request.args.get("direction", "outbound")
    contact_id = request.args.get("contact_id", type=int)
    demande_id = request.args.get("demande_id", type=int)
    limit = min(request.args.get("limit", default=50, type=int), 200)

    query = Email.query.filter_by(tenant_id=tenant_id)
    if direction:
        query = query.filter_by(direction=direction)
    if contact_id:
        query = query.filter_by(contact_id=contact_id)
    if demande_id:
        query = query.filter_by(demande_id=demande_id)

    rows = query.order_by(Email.created_at.desc()).limit(limit).all()
    return jsonify({"emails": [e.to_dict() for e in rows], "total": len(rows)}), 200


@emails_bp.post("/fetch")
@jwt_required()
def fetch_now():
    """Force une collecte IMAP des nouveaux emails du tenant courant."""
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    cfg = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()
    if not cfg or not cfg.inbound_enabled or not cfg.imap_host:
        return jsonify({"error": "Réception IMAP non configurée ou désactivée."}), 400
    from app.scripts.mail_fetch import fetch_inbound_for_tenant
    try:
        count = fetch_inbound_for_tenant(db, cfg)
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Échec de la collecte : {exc}"}), 502
    return jsonify({"fetched": count}), 200


@emails_bp.get("/<int:email_id>")
@jwt_required()
def get_email(email_id):
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    email = Email.query.filter_by(id=email_id, tenant_id=tenant_id).first()
    if not email:
        return jsonify({"error": "Email introuvable."}), 404
    return jsonify(_email_full(email)), 200


@emails_bp.patch("/<int:email_id>")
@jwt_required()
def patch_email(email_id):
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    email = Email.query.filter_by(id=email_id, tenant_id=tenant_id).first()
    if not email:
        return jsonify({"error": "Email introuvable."}), 404
    data = request.get_json(silent=True) or {}

    allowed = {"non_lu", "lu", "traite", "archive", "spam"}
    if "status" in data:
        st = data["status"]
        if st not in allowed:
            return jsonify({"error": f"Statut invalide : {sorted(allowed)}"}), 422
        email.status = st
    if "demande_id" in data:
        email.demande_id = data["demande_id"] or None

    db.session.commit()
    return jsonify(_email_full(email)), 200


@emails_bp.post("/<int:email_id>/link-demande")
@jwt_required()
def link_email_demande(email_id):
    """
    Rattache un email à une demande (existante ou nouvellement créée côté client)
    et crée une interaction de suivi de type EMAIL. Marque l'email comme traité.
    """
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    user_id = int(get_jwt_identity())
    email = Email.query.filter_by(id=email_id, tenant_id=tenant_id).first()
    if not email:
        return jsonify({"error": "Email introuvable."}), 404

    data = request.get_json(silent=True) or {}
    demande_id = data.get("demande_id")
    if not demande_id:
        return jsonify({"error": "demande_id est requis."}), 422

    demande = Demande.query.filter_by(id=demande_id, tenant_id=tenant_id).first()
    if not demande:
        return jsonify({"error": "Demande introuvable dans ce tenant."}), 404

    email.demande_id = demande_id
    if email.direction == "inbound" and email.status not in ("archive", "spam"):
        email.status = "traite"

    sens = "reçu" if email.direction == "inbound" else "envoyé"
    db.session.add(Interaction(
        demande_id=demande_id, user_id=user_id, tenant_id=tenant_id,
        contact_id=email.contact_id,
        type_interaction=TypeInteraction.EMAIL,
        contenu=f"[Email {sens}] {email.subject or '(sans objet)'}\n\n{email.body_text or ''}".strip(),
    ))
    db.session.commit()
    return jsonify(_email_full(email)), 200


@emails_bp.get("/<int:email_id>/attachments/<int:att_id>/download")
@jwt_required()
def download_attachment(email_id, att_id):
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    att = EmailAttachment.query.filter_by(id=att_id, email_id=email_id, tenant_id=tenant_id).first()
    if not att or not os.path.exists(att.storage_path):
        return jsonify({"error": "Pièce jointe introuvable."}), 404
    from io import BytesIO
    with open(att.storage_path, "rb") as fh:
        raw = decrypt_bytes(fh.read())
    return send_file(
        BytesIO(raw),
        as_attachment=True,
        download_name=att.filename,
        mimetype=att.content_type or "application/octet-stream",
    )


# ── KPI emails (Reports › onglet Email) ──────────────────────────────────────
@emails_bp.get("/stats")
@jwt_required()
def email_stats():
    tenant_id, err = _tenant_uuid()
    if err:
        return err

    now = datetime.utcnow()

    def _parse(s, default):
        if not s:
            return default
        try:
            return datetime.fromisoformat(s.replace("Z", ""))
        except ValueError:
            return default

    dt_from = _parse(request.args.get("from"), now - timedelta(days=30))
    dt_to = _parse(request.args.get("to"), now)
    user_filter = request.args.get("user_id", type=int)

    q = Email.query.filter(
        Email.tenant_id == tenant_id,
        Email.created_at >= dt_from,
        Email.created_at <= dt_to,
    )
    if user_filter:
        q = q.filter(Email.user_id == user_filter)
    rows = q.all()

    # Sortants : respectent le filtre utilisateur
    outbound = [e for e in rows if e.direction == "outbound"]
    sent_ok = [e for e in outbound if e.status == "sent"]
    failed = [e for e in outbound if e.status == "failed"]

    per_day, by_user = {}, {}
    from app.models.user import User
    user_names = {}
    for e in outbound:
        day = (e.sent_at or e.created_at).strftime("%Y-%m-%d")
        per_day[day] = per_day.get(day, 0) + 1
        if e.user_id:
            by_user[e.user_id] = by_user.get(e.user_id, 0) + 1
    if by_user:
        for u in User.query.filter(User.id.in_(by_user.keys())).all():
            user_names[u.id] = u.username

    # Entrants : non filtrés par utilisateur (la réception n'est pas attribuable)
    inbound = Email.query.filter(
        Email.tenant_id == tenant_id, Email.direction == "inbound",
        Email.created_at >= dt_from, Email.created_at <= dt_to,
    ).all()

    # Réponses : map message-id d'origine -> 1ère date d'envoi de la réponse
    replies = Email.query.filter(
        Email.tenant_id == tenant_id, Email.direction == "outbound",
        Email.in_reply_to.isnot(None),
    ).all()
    reply_map = {}
    for r in replies:
        when = r.sent_at or r.created_at
        if r.in_reply_to and (r.in_reply_to not in reply_map or when < reply_map[r.in_reply_to]):
            reply_map[r.in_reply_to] = when

    replied, delays, unanswered, by_status = 0, [], 0, {}
    for e in inbound:
        by_status[e.status] = by_status.get(e.status, 0) + 1
        rep_when = reply_map.get(e.message_id) if e.message_id else None
        if rep_when:
            replied += 1
            if e.received_at and rep_when > e.received_at:
                delays.append((rep_when - e.received_at).total_seconds() / 60)
        elif e.status not in ("archive", "spam", "traite"):
            unanswered += 1

    avg_response = round(sum(delays) / len(delays), 1) if delays else 0
    received_total = len(inbound)

    return jsonify({
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
        "kpi": {
            "sent_total": len(sent_ok),
            "failed_total": len(failed),
            "failure_rate_pct": round(len(failed) / len(outbound) * 100, 1) if outbound else 0,
            "with_attachments": len([e for e in outbound if e.has_attachments]),
            "unique_recipients": len({e.to_addresses for e in outbound if e.to_addresses}),
            "received_total": received_total,
            "response_rate_pct": round(replied / received_total * 100, 1) if received_total else 0,
            "avg_response_minutes": avg_response,
            "unanswered": unanswered,
        },
        "per_day": [{"date": d, "count": c} for d, c in sorted(per_day.items())],
        "by_user": sorted(
            [{"user_id": uid, "username": user_names.get(uid, f"#{uid}"), "count": c}
             for uid, c in by_user.items()],
            key=lambda x: x["count"], reverse=True,
        ),
        "inbound_by_status": by_status,
    }), 200
