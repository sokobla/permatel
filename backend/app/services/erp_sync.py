"""
Dispatch de la file de retry ERP (Phase 6, ODOO_INTEGRATION_PLAN.md §2.1/§2.4).

Rejoue les lignes `erp_sync_queue` en attente après un échec/timeout de la
tentative synchrone initiale. Motif calqué sur `dispatch_emails()`
(app/services/notifications.py), avec en plus le verrouillage court
`locked_at`/`locked_until` (§2.4) pour qu'un run qui prend du retard ne se
fasse pas doubler par le suivant.

Aucun flux réel n'écrit encore dans `erp_sync_queue` à ce stade (Phase 6 =
fondations transverses ; les premiers flux réels — `erp_partners` —
arrivent en Phase 7) : cette fonction est un squelette opérationnel,
testable avec des lignes insérées manuellement, prêt à recevoir la
logique de rejeu (search-then-write par `x_permatel_ref`, §2.4) une fois
les premiers flux branchés.
"""
from datetime import timedelta
from app.utils.time import utcnow

from app.models.erp import ErpSyncQueue

LOCK_DURATION_SECONDS = 60
MAX_ATTEMPTS = 5


def dispatch_erp_sync(db, limit=100) -> dict:
    """Traite les entrées `pending`/`failed` (sous le seuil de tentatives)
    non verrouillées. Pour le cron `flask erp-sync-dispatch`."""
    now = utcnow()
    rows = (
        ErpSyncQueue.query
        .filter(ErpSyncQueue.status.in_(["pending", "failed"]))
        .filter(ErpSyncQueue.attempts < MAX_ATTEMPTS)
        .filter((ErpSyncQueue.locked_until.is_(None)) | (ErpSyncQueue.locked_until < now))
        .limit(limit)
        .all()
    )

    processed = failed = 0
    for row in rows:
        row.status = "in_flight"
        row.locked_at = now
        row.locked_until = now + timedelta(seconds=LOCK_DURATION_SECONDS)
        db.session.flush()

        try:
            # Aucun flux réel implémenté en Phase 6 (cf. docstring) — une
            # ligne insérée manuellement reste donc "in_flight" jusqu'à ce
            # que la logique de rejeu par flux soit branchée (Phase 7+).
            # Le verrouillage/déverrouillage est déjà testable tel quel.
            raise NotImplementedError(
                f"Rejeu du flux '{row.flux}' non encore implémenté (Phase 7+)."
            )
        except NotImplementedError as exc:
            row.attempts += 1
            row.error = str(exc)
            row.status = "failed"
            row.locked_at = None
            row.locked_until = None
            failed += 1

    db.session.commit()
    return {"processed": processed, "failed": failed}
