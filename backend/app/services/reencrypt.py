"""
Re-chiffrement des données au repos : ancienne clé → clé courante.

À lancer APRÈS avoir mis la NOUVELLE valeur de SETTINGS_ENCRYPTION_KEY en place
(env + redémarrage). On passe l'ANCIENNE clé en argument : chaque secret est
déchiffré avec l'ancienne puis ré-chiffré avec la clé courante.

Couvre : mots de passe SMTP/IMAP, contenu des emails (objet/corps/HTML),
pièces jointes chiffrées sur disque.
"""
import os

from sqlalchemy import text

from app.utils.crypto import (
    fernet_from_secret, decrypt_secret_with, encrypt_secret,
    decrypt_bytes_with, encrypt_bytes,
)


def reencrypt_all(db, old_key: str) -> dict:
    from app.models.setting import SmtpSetting
    from app.models.email import Email
    from app.models.email_attachment import EmailAttachment

    old = fernet_from_secret(old_key)
    counts = {"smtp": 0, "imap": 0, "emails": 0, "attachments": 0}

    # ── SMTP / IMAP (colonnes String, préfixe enc::) ──────────────────────────
    for cfg in SmtpSetting.query.all():
        if cfg.password and cfg.password.startswith("enc::"):
            pt = decrypt_secret_with(cfg.password, old)
            if pt is not None:
                cfg.password = encrypt_secret(pt)
                counts["smtp"] += 1
        if cfg.imap_password and cfg.imap_password.startswith("enc::"):
            pt = decrypt_secret_with(cfg.imap_password, old)
            if pt is not None:
                cfg.imap_password = encrypt_secret(pt)
                counts["imap"] += 1

    # ── Emails (colonnes EncryptedText) ───────────────────────────────────────
    # On lit le BRUT (SQL) car le type déchiffrerait avec la clé COURANTE (échec).
    # On réaffecte le clair sur l'ORM : ré-chiffré avec la clé courante au commit.
    raw = {
        r[0]: (r[1], r[2], r[3])
        for r in db.session.execute(
            text("SELECT id, subject, body_text, body_html FROM emails")
        ).fetchall()
    }
    for e in Email.query.all():
        s, bt, bh = raw.get(e.id, (None, None, None))
        e.subject = decrypt_secret_with(s, old) if s else s
        e.body_text = decrypt_secret_with(bt, old) if bt else bt
        e.body_html = decrypt_secret_with(bh, old) if bh else bh
        counts["emails"] += 1

    db.session.commit()  # déclenche le ré-chiffrement EncryptedText avec la clé courante

    # ── Pièces jointes sur disque (préfixe ENC1) ──────────────────────────────
    for att in EmailAttachment.query.all():
        p = att.storage_path
        if not p or not os.path.exists(p):
            continue
        with open(p, "rb") as fh:
            data = fh.read()
        if data.startswith(b"ENC1"):
            plain = decrypt_bytes_with(data, old)
            with open(p, "wb") as fh:
                fh.write(encrypt_bytes(plain))
            counts["attachments"] += 1

    return counts
