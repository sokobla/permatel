"""API des prises de service (vacations agents).

Cycle ouvert/fermé :
  - POST /api/prises-de-service/start   → débute une vacation (date_debut = now)
  - POST /api/prises-de-service/end     → termine la vacation EN COURS d'un agent
  - POST /api/prises-de-service/<id>/end→ termine une vacation précise (action de ligne)
  - GET  /api/prises-de-service         → liste filtrable
  - GET  /api/prises-de-service/stats   → indicateurs (rapports)
"""
from datetime import datetime

from flask import Blueprint, jsonify, request, g

from app import db
from app.models.prise_de_service import PriseDeService
from app.models.agent_securite import AgentSecurite
from app.models.client import Client
from app.models.site import Site
from app.utils.decorators import tenant_required

prises_de_service_bp = Blueprint("prises_de_service", __name__, url_prefix="/api/prises-de-service")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            pass
    return None


def _enrich(rows):
    """Sérialise une liste de prises de service en résolvant les libellés (batch)."""
    tid = g.tenant_id
    agent_ids = {r.agent_id for r in rows}
    client_ids = {r.client_id for r in rows if r.client_id}
    site_ids = {r.site_id for r in rows if r.site_id}

    agents = {a.id: a for a in AgentSecurite.query.filter(
        AgentSecurite.tenant_id == tid, AgentSecurite.id.in_(agent_ids or {0})).all()}
    clients = {c.id: c.nom for c in Client.query.filter(
        Client.tenant_id == tid, Client.id.in_(client_ids or {0})).all()}
    sites = {s.id: s.nom for s in Site.query.filter(
        Site.tenant_id == tid, Site.id.in_(site_ids or {0})).all()}

    return [
        r.to_dict(agent=agents.get(r.agent_id),
                  client_nom=clients.get(r.client_id),
                  site_nom=sites.get(r.site_id))
        for r in rows
    ]


# ── Liste ────────────────────────────────────────────────────────────────────

@prises_de_service_bp.get("")
@tenant_required
def list_prises():
    q = PriseDeService.query.filter_by(tenant_id=g.tenant_id)

    if agent_id := request.args.get("agent_id", type=int):
        q = q.filter(PriseDeService.agent_id == agent_id)
    if client_id := request.args.get("client_id", type=int):
        q = q.filter(PriseDeService.client_id == client_id)
    if site_id := request.args.get("site_id", type=int):
        q = q.filter(PriseDeService.site_id == site_id)
    if (statut := request.args.get("statut")) in ("en_cours", "terminee"):
        q = q.filter(PriseDeService.date_fin.is_(None) if statut == "en_cours"
                     else PriseDeService.date_fin.isnot(None))
    if (d := _parse_date(request.args.get("date"))):
        q = q.filter(PriseDeService.date_debut >= d)

    rows = q.order_by(PriseDeService.date_debut.desc()).all()
    return jsonify(_enrich(rows)), 200


# ── Débuter une vacation ─────────────────────────────────────────────────────

@prises_de_service_bp.post("/start")
@tenant_required
def start_prise():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    client_id = data.get("client_id")
    site_id = data.get("site_id")

    if not agent_id or not client_id:
        return jsonify({"error": "Les champs agent et client sont requis."}), 400

    agent = AgentSecurite.query.filter_by(id=agent_id, tenant_id=g.tenant_id).first()
    if not agent:
        return jsonify({"error": "Agent introuvable."}), 404
    if not Client.query.filter_by(id=client_id, tenant_id=g.tenant_id).first():
        return jsonify({"error": "Client introuvable."}), 404
    if site_id and not Site.query.filter_by(id=site_id, tenant_id=g.tenant_id).first():
        return jsonify({"error": "Site introuvable."}), 404

    # Règle métier : un agent ne peut avoir qu'une vacation en cours à la fois.
    open_existing = PriseDeService.query.filter_by(
        tenant_id=g.tenant_id, agent_id=agent_id, date_fin=None).first()
    if open_existing:
        return jsonify({"error": "Cet agent a déjà une vacation en cours."}), 409

    pds = PriseDeService(
        tenant_id=g.tenant_id,
        agent_id=agent_id,
        client_id=client_id,
        site_id=site_id,
        date_debut=datetime.utcnow(),
        created_by_id=getattr(g.user, "id", None),
    )
    db.session.add(pds)
    db.session.commit()
    return jsonify(_enrich([pds])[0]), 201


# ── Terminer la vacation en cours d'un agent ─────────────────────────────────

@prises_de_service_bp.post("/end")
@tenant_required
def end_current_prise():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    if not agent_id:
        return jsonify({"error": "Le champ agent est requis."}), 400

    pds = PriseDeService.query.filter_by(
        tenant_id=g.tenant_id, agent_id=agent_id, date_fin=None).first()
    if not pds:
        return jsonify({"error": "Aucune vacation en cours pour cet agent."}), 404

    pds.date_fin = datetime.utcnow()
    db.session.commit()
    return jsonify(_enrich([pds])[0]), 200


# ── Terminer une vacation précise (action de ligne) ──────────────────────────

@prises_de_service_bp.post("/<int:pds_id>/end")
@tenant_required
def end_prise(pds_id):
    pds = PriseDeService.query.filter_by(id=pds_id, tenant_id=g.tenant_id).first()
    if not pds:
        return jsonify({"error": "Prise de service introuvable."}), 404
    if pds.date_fin is not None:
        return jsonify({"error": "Cette vacation est déjà terminée."}), 409

    pds.date_fin = datetime.utcnow()
    db.session.commit()
    return jsonify(_enrich([pds])[0]), 200


# ── Statistiques (rapports) ──────────────────────────────────────────────────

@prises_de_service_bp.get("/stats")
@tenant_required
def stats_prises():
    q = PriseDeService.query.filter_by(tenant_id=g.tenant_id)
    if client_id := request.args.get("client_id", type=int):
        q = q.filter(PriseDeService.client_id == client_id)
    if (d := _parse_date(request.args.get("from"))):
        q = q.filter(PriseDeService.date_debut >= d)
    if (d := _parse_date(request.args.get("to"))):
        q = q.filter(PriseDeService.date_debut <= d)

    rows = q.all()
    total = len(rows)
    en_cours = sum(1 for r in rows if r.date_fin is None)
    terminees = total - en_cours

    durations = [r.duree_minutes for r in rows if r.date_fin is not None]
    duree_moyenne_min = round(sum(durations) / len(durations)) if durations else 0

    # Répartition par client (libellés résolus)
    client_ids = {r.client_id for r in rows if r.client_id}
    clients = {c.id: c.nom for c in Client.query.filter(
        Client.tenant_id == g.tenant_id, Client.id.in_(client_ids or {0})).all()}
    by_client = {}
    for r in rows:
        name = clients.get(r.client_id) or f"Client #{r.client_id}"
        by_client[name] = by_client.get(name, 0) + 1

    return jsonify({
        "total": total,
        "en_cours": en_cours,
        "terminees": terminees,
        "duree_moyenne_min": duree_moyenne_min,
        "by_client": [{"label": k, "count": v} for k, v in
                      sorted(by_client.items(), key=lambda x: -x[1])],
    }), 200
