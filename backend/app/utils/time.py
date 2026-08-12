"""
Remplacement non-déprécié de `datetime.utcnow()` (audit du 12/08 — 67 appels
directs + ~38 références nues en `default=`/`onupdate=` de colonnes
SQLAlchemy, sur toute la base de code).

`datetime.utcnow()` reste dépréciée depuis Python 3.12 mais tout le schéma
existant stocke des datetimes NAÏFS en UTC (convention établie, jamais
`DateTime(timezone=True)`) — passer à `datetime.now(timezone.utc)` tel quel
produirait des valeurs *aware*, incompatibles en comparaison directe avec
les valeurs naïves déjà en base et cassant potentiellement des comparaisons
Python (`TypeError: can't compare offset-naive and offset-aware datetimes`).
`utcnow()` ci-dessous reproduit exactement l'ancien comportement (naïf, UTC)
via l'API non-dépréciée — migration mécanique, zéro changement de
sémantique de stockage.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Datetime UTC naïf (sans tzinfo) — remplacement direct de
    `datetime.utcnow()`, utilisable aussi bien en appel (`utcnow()`) qu'en
    référence nue pour `Column(default=utcnow)`/`onupdate=utcnow`."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcfromtimestamp(ts) -> datetime:
    """Datetime UTC naïf à partir d'un timestamp epoch — remplacement
    direct de `datetime.utcfromtimestamp(ts)`, même convention naïve que
    `utcnow()` ci-dessus."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
