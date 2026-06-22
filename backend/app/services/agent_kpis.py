"""
KPI & score d'un agent de sécurité — définitions centralisées et stables.

Définitions (non ambiguës) :
  - « Anomalies »       : toutes les DemandeAnomalie impliquant l'agent
                          (agent_concerne_id), sur la période, non supprimées.
  - « Incidents agent » : sous-ensemble DISCRIMINANT = nature marquée
                          discriminante pour le tenant OU impact_securite=True.
  - « Score »           : 100 − (MALUS_PAR_INCIDENT × nb incidents), borné [0, 100].

Seuls les incidents discriminants affectent le score. Les anomalies non
discriminantes sont comptées dans « Anomalies » uniquement.
"""
from app.models.demande import DemandeAnomalie
from app.models.setting import ReferenceValue

SCORE_BASELINE = 100
MALUS_PER_INCIDENT = 5  # version simple ; pondération par catégorie en évolution future


def discriminant_codes(tenant_id) -> set[str]:
    """Codes de nature marqués discriminants ET actifs pour le tenant."""
    rows = ReferenceValue.query.filter_by(
        tenant_id=tenant_id, family="nature_anomalie",
        is_active=True, is_discriminant=True,
    ).all()
    return {r.code for r in rows if r.code}


def _is_incident(anomalie, disc: set[str]) -> bool:
    nature = anomalie.nature_anomalie.value if anomalie.nature_anomalie else None
    return bool(anomalie.impact_securite) or (nature in disc)


def agent_kpis(tenant_id, agent_id, dt_from, dt_to) -> dict:
    """KPI d'un agent sur la période [dt_from, dt_to]."""
    rows = (
        DemandeAnomalie.query
        .filter(
            DemandeAnomalie.tenant_id == tenant_id,
            DemandeAnomalie.agent_concerne_id == agent_id,
            DemandeAnomalie.is_deleted.is_(False),
            DemandeAnomalie.created_at >= dt_from,
            DemandeAnomalie.created_at <= dt_to,
        )
        .all()
    )
    disc = discriminant_codes(tenant_id)
    incidents = [a for a in rows if _is_incident(a, disc)]

    def _by_status(items):
        out = {}
        for a in items:
            k = a.statut.value if a.statut else "inconnu"
            out[k] = out.get(k, 0) + 1
        return out

    score = max(0, min(SCORE_BASELINE, SCORE_BASELINE - MALUS_PER_INCIDENT * len(incidents)))

    return {
        "agent_id": agent_id,
        "anomalies": len(rows),                 # KPI large
        "incidents": len(incidents),            # KPI discriminant (impacte le score)
        "score": score,
        "anomalies_by_status": _by_status(rows),
        "incidents_by_status": _by_status(incidents),
    }
