"""
Géolocalisation IP -> pays (drapeau, Rapports > Sessions, 14/08).

Base MaxMind GeoLite2-Country locale (`maxminddb`, lookup 100% offline —
aucune IP transmise à un service tiers, choix explicite pour une app de
sécurité). Le fichier `.mmdb` lui-même n'est PAS fourni par ce dépôt (licence
MaxMind interdisant sa redistribution publique) : à obtenir via un compte
MaxMind gratuit et à placer au chemin `GEOIP_DB_PATH` (config, cf.
app/config.py). En son absence, dégradation gracieuse — aucune erreur,
aucun drapeau affiché — même motif que `_get_redis()`
(app/routes/telephony.py) pour Redis.
"""
import ipaddress
import logging

logger = logging.getLogger(__name__)

try:
    import maxminddb
except ImportError:  # pragma: no cover - maxminddb toujours présent en prod (requirements.txt)
    maxminddb = None

_reader = None
_reader_checked = False


def _get_reader(db_path):
    global _reader, _reader_checked
    if _reader_checked:
        return _reader
    _reader_checked = True
    if maxminddb is None or not db_path:
        return None
    try:
        _reader = maxminddb.open_database(db_path)
    except (FileNotFoundError, OSError) as exc:
        logger.info("Base GeoIP introuvable (%s) — drapeaux pays désactivés : %s", db_path, exc)
        _reader = None
    return _reader


def lookup_country_code(ip_address, db_path=None):
    """Code pays ISO 3166-1 alpha-2 (ex. "MA", "FR") pour une IP, ou `None`
    si indisponible pour quelque raison que ce soit (base absente, IP privée/
    locale, IP invalide, pays non résolu) — ne lève jamais."""
    if not ip_address:
        return None
    try:
        ip_obj = ipaddress.ip_address(ip_address)
    except ValueError:
        return None
    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
        return None

    reader = _get_reader(db_path)
    if reader is None:
        return None
    try:
        result = reader.get(ip_address)
    except Exception:  # noqa: BLE001 - ne doit jamais faire échouer l'appelant
        logger.exception("Échec du lookup GeoIP pour %s", ip_address)
        return None
    if not result:
        return None
    return (result.get("country") or {}).get("iso_code")
