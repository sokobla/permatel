"""
Service SLA — calcul des échéances et du statut (temps calendaire).

Deux horloges : prise en charge (response) + résolution (resolution).
Cible résolue par spécificité (priorité × type × client). Pause optionnelle en
statut « en_attente ». Pas de surcharge manuelle des échéances.
"""
from datetime import datetime, timedelta

from app.models.sla import SlaPolicy
from app.models.demande import StatutDemande

# Défauts (minutes) — amorcés par tenant, puis paramétrables.
DEFAULT_SLA = {
    "urgente": {"response": 30,  "resolution": 240},
    "haute":   {"response": 60,  "resolution": 480},
    "normale": {"response": 240, "resolution": 1440},
    "basse":   {"response": 480, "resolution": 4320},
}
DEFAULT_WARNING_PCT = 80


def _val(x):
    return x.value if hasattr(x, "value") else x


def seed_sla_policies(db, tenant_id) -> int:
    """Amorce les cibles par défaut (priorité seule) pour un tenant. Idempotent."""
    created = 0
    for prio, d in DEFAULT_SLA.items():
        exists = SlaPolicy.query.filter_by(
            tenant_id=tenant_id, priorite=prio, type_demande=None, client_id=None
        ).first()
        if not exists:
            db.session.add(SlaPolicy(
                tenant_id=tenant_id, priorite=prio,
                response_minutes=d["response"], resolution_minutes=d["resolution"],
                warning_pct=DEFAULT_WARNING_PCT, pause_on_waiting=True,
            ))
            created += 1
    db.session.flush()
    return created


def backfill_all(db) -> dict:
    """
    Backfill des tenants existants :
      - amorce les politiques SLA par défaut (priorité) manquantes, par tenant ;
      - recalcule les échéances des demandes ACTIVES dépourvues de SLA
        (statut nouvelle/en_cours/en_attente, non supprimées).
    Les demandes terminées sans échéance restent en l'état (statut SLA = n/a),
    on ne reconstruit pas de date de prise en charge/résolution rétroactive.
    """
    from app.models.tenant import Tenant
    from app.models.demande import Demande, StatutDemande

    tenants = Tenant.query.all()
    policies_created = 0
    for t in tenants:
        policies_created += seed_sla_policies(db, t.id)

    open_states = [StatutDemande.NOUVELLE, StatutDemande.EN_COURS, StatutDemande.EN_ATTENTE]
    actives = (Demande.query
               .filter(Demande.sla_deadline.is_(None),
                       Demande.statut.in_(open_states),
                       Demande.is_deleted.is_(False))
               .all())
    for d in actives:
        apply_sla(d)

    db.session.commit()
    return {"tenants": len(tenants), "policies_created": policies_created,
            "demandes_recomputed": len(actives)}


def _sla_recipients(d):
    """Destinataires des alertes SLA : managers + admins de tenant + assigné."""
    from app.models.user import User, UserRole
    from app.services.notifications import tenant_members
    recips = tenant_members(d.tenant_id, roles={UserRole.MANAGER.value}, membership_admin=True)
    if d.permanencier_id:
        u = User.query.get(d.permanencier_id)
        if u and all(u.id != r.id for r in recips):
            recips.append(u)
    return recips


def sla_sweep(db) -> dict:
    """
    Balaye les demandes ouvertes et émet les alertes SLA de résolution
    (idempotent via sla_warning_notified / sla_breach_notified). Pour le cron.
    """
    from app.models.demande import Demande, StatutDemande
    from app.services.notifications import notify

    open_states = [StatutDemande.NOUVELLE, StatutDemande.EN_COURS, StatutDemande.EN_ATTENTE]
    rows = (Demande.query
            .filter(Demande.statut.in_(open_states),
                    Demande.is_deleted.is_(False),
                    Demande.sla_deadline.isnot(None))
            .all())
    warnings = breaches = 0
    for d in rows:
        status = sla_state(d)["resolution"]["status"]
        if status == "breached" and not d.sla_breach_notified:
            notify(d.tenant_id, _sla_recipients(d), "sla.breach",
                   title=f"SLA dépassé — {d.numero_ticket}",
                   body=f"La demande « {d.titre} » a dépassé son échéance de résolution.",
                   severity="high", entity_type="demande", entity_id=d.id)
            d.sla_breach_notified = True
            d.sla_warning_notified = True
            breaches += 1
        elif status == "at_risk" and not d.sla_warning_notified:
            notify(d.tenant_id, _sla_recipients(d), "sla.warning",
                   title=f"SLA bientôt dépassé — {d.numero_ticket}",
                   body=f"La demande « {d.titre} » approche de son échéance de résolution.",
                   severity="normal", entity_type="demande", entity_id=d.id)
            d.sla_warning_notified = True
            warnings += 1
    db.session.commit()
    return {"warnings": warnings, "breaches": breaches}


def resolve_policy(tenant_id, priorite, type_demande, client_id):
    """Politique la plus spécifique pour (priorité, type, client) ; défaut sinon."""
    prio, td = _val(priorite), _val(type_demande)
    rows = SlaPolicy.query.filter_by(tenant_id=tenant_id, priorite=prio).all()
    best, best_score = None, -1
    for r in rows:
        if r.type_demande not in (None, td):
            continue
        if r.client_id not in (None, client_id):
            continue
        score = (2 if r.client_id is not None else 0) + (1 if r.type_demande is not None else 0)
        if score > best_score:
            best, best_score = r, score
    if best:
        return best
    d = DEFAULT_SLA.get(prio, DEFAULT_SLA["normale"])
    return SlaPolicy(tenant_id=tenant_id, priorite=prio,
                     response_minutes=d["response"], resolution_minutes=d["resolution"],
                     warning_pct=DEFAULT_WARNING_PCT, pause_on_waiting=True)


def apply_sla(demande):
    """(Re)calcule les deux échéances à partir de created_at et de la politique."""
    base = demande.created_at or datetime.utcnow()
    p = resolve_policy(demande.tenant_id, demande.priorite, demande.type_demande, demande.client_id)
    demande.sla_response_deadline = base + timedelta(minutes=p.response_minutes)
    demande.sla_deadline = base + timedelta(minutes=p.resolution_minutes)


def on_status_change(demande, new_statut):
    """Pose les horodatages de cycle de vie (prise en charge / résolution / clôture)."""
    now = datetime.utcnow()
    if new_statut != StatutDemande.NOUVELLE and not demande.prise_en_charge_at:
        demande.prise_en_charge_at = now
    if new_statut == StatutDemande.RESOLUE and not demande.date_resolution:
        demande.date_resolution = now
    if new_statut == StatutDemande.CLOTUREE and not demande.closed_at:
        demande.closed_at = now


def _clock(deadline, base, end, now, warning_pct, paused):
    if not deadline:
        return {"status": "n/a"}
    out = {"deadline": deadline.isoformat()}
    if end:  # horloge arrêtée
        out["status"] = "met" if end <= deadline else "missed"
        return out
    if paused:
        out["status"] = "paused"
        return out
    remaining = (deadline - now).total_seconds()
    if remaining < 0:
        out["status"] = "breached"
        out["overdue_seconds"] = int(-remaining)
        return out
    total = (deadline - base).total_seconds() if base else 0
    pct = (1 - remaining / total) * 100 if total > 0 else 0
    out["status"] = "at_risk" if pct >= warning_pct else "on_time"
    out["remaining_seconds"] = int(remaining)
    return out


def sla_state(demande) -> dict:
    """État des deux SLA pour l'affichage (sans persistance)."""
    if demande.statut == StatutDemande.ANNULEE:
        return {"response": {"status": "n/a"}, "resolution": {"status": "n/a"}}
    now = datetime.utcnow()
    base = demande.created_at
    p = resolve_policy(demande.tenant_id, demande.priorite, demande.type_demande, demande.client_id)
    waiting = bool(p.pause_on_waiting and demande.statut == StatutDemande.EN_ATTENTE)
    res_end = demande.date_resolution or demande.closed_at
    return {
        "response": _clock(demande.sla_response_deadline, base, demande.prise_en_charge_at,
                           now, p.warning_pct, waiting and not demande.prise_en_charge_at),
        "resolution": _clock(demande.sla_deadline, base, res_end,
                             now, p.warning_pct, waiting and not res_end),
    }
