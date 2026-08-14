from datetime import datetime
from app.utils.time import utcnow

from sqlalchemy import Column, Integer, DateTime, ForeignKey, ForeignKeyConstraint, Index
from sqlalchemy.dialects.postgresql import UUID

from app import db

Base = db.Model


class PriseDeService(Base):
    """Prise de service (vacation) d'un agent sur un site/client.

    Cycle de vie :
      - création  : `date_debut` renseignée (= now), `date_fin` NULL  → vacation EN COURS
      - clôture   : `date_fin` renseignée (= now)                     → vacation TERMINÉE

    Modèle dédié (et non une spécialisation de `Demande`) : il s'agit d'un
    enregistrement de temps de travail au cycle ouvert/fermé, sans titre,
    priorité, SLA ni workflow de statut propre aux tickets.
    """
    __tablename__ = "prises_de_service"
    __table_args__ = (
        Index("ix_pds_tenant_agent_open", "tenant_id", "agent_id", "date_fin"),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"], ["clients.tenant_id", "clients.id"],
            name="fk_prises_de_service_client_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], ["sites.tenant_id", "sites.id"],
            name="fk_prises_de_service_site_tenant",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents_securite.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, nullable=False, index=True)
    site_id = Column(Integer, nullable=True, index=True)

    date_debut = Column(DateTime, nullable=False, default=utcnow)
    date_fin = Column(DateTime, nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ended_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    @property
    def statut(self) -> str:
        return "en_cours" if self.date_fin is None else "terminee"

    @property
    def duree_minutes(self) -> int:
        fin = self.date_fin or utcnow()
        return max(0, int((fin - self.date_debut).total_seconds() // 60))

    def to_dict(self, *, agent=None, client_nom=None, site_nom=None,
                created_by_name=None, ended_by_name=None) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "agent_nom": (f"{agent.prenom or ''} {agent.nom or ''}".strip() if agent else None),
            "agent_matricule": (agent.matricule if agent else None),
            "agent_type": (agent.type_agent if agent else None),
            "client_id": self.client_id,
            "client_nom": client_nom,
            "site_id": self.site_id,
            "site_nom": site_nom,
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "duree_minutes": self.duree_minutes,
            "statut": self.statut,
            "created_by_id": self.created_by_id,
            # Nom/prénom PERMATEL de l'utilisateur ayant déclaré le début/la
            # fin de la vacation (14/08, rapport détaillé) — résolus en batch
            # par l'appelant (`_enrich()`, app/routes/prises_de_service.py),
            # pas de requête ici.
            "created_by_name": created_by_name,
            "ended_by_id": self.ended_by_id,
            "ended_by_name": ended_by_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<PriseDeService #{self.id} agent={self.agent_id} statut={self.statut}>"
