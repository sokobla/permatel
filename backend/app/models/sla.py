"""
Politique SLA par tenant.

Cible (délais de prise en charge + résolution) résolue par spécificité décroissante :
  (priorité + type + client)  >  (priorité + client)  >  (priorité + type)  >  (priorité seule)
Les lignes « priorité seule » (type/client NULL) sont les valeurs par défaut amorcées
à la création d'un tenant ; elles restent paramétrables.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app import db


class SlaPolicy(db.Model):
    __tablename__ = "sla_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "priorite", "type_demande", "client_id",
                         name="uq_sla_policy_scope"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    priorite = Column(String(20), nullable=False)        # basse | normale | haute | urgente
    type_demande = Column(String(20), nullable=True)     # anomalie | commande | planning | admin | NULL (tous)
    client_id = Column(Integer, nullable=True)           # NULL = tous les clients
    response_minutes = Column(Integer, nullable=False)   # cible de prise en charge
    resolution_minutes = Column(Integer, nullable=False) # cible de résolution
    warning_pct = Column(Integer, nullable=False, default=80)   # seuil "à risque"
    pause_on_waiting = Column(Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "priorite": self.priorite,
            "type_demande": self.type_demande,
            "client_id": self.client_id,
            "response_minutes": self.response_minutes,
            "resolution_minutes": self.resolution_minutes,
            "warning_pct": self.warning_pct,
            "pause_on_waiting": self.pause_on_waiting,
        }
