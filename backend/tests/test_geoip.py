"""
Géolocalisation IP (14/08) — `lookup_country_code()`. Aucune base .mmdb
fournie/attendue dans l'environnement de test (licence MaxMind, cf.
app/utils/geoip.py) : ces tests couvrent uniquement le mode dégradé
(fichier absent, IP privée/invalide) — jamais d'exception, jamais de
requête réseau.
"""
from app.utils.geoip import lookup_country_code


def test_ip_absente_retourne_none():
    assert lookup_country_code(None) is None
    assert lookup_country_code("") is None


def test_ip_invalide_retourne_none():
    assert lookup_country_code("not-an-ip") is None


def test_ip_privee_retourne_none():
    assert lookup_country_code("192.168.1.1") is None
    assert lookup_country_code("10.0.0.5") is None


def test_ip_loopback_retourne_none():
    assert lookup_country_code("127.0.0.1") is None
    assert lookup_country_code("::1") is None


def test_base_mmdb_absente_degrade_gracieusement():
    """Comportement attendu en environnement de test/dev sans le fichier
    .mmdb (non fourni par ce dépôt) — ne lève jamais, retourne None."""
    assert lookup_country_code("8.8.8.8", db_path="/nonexistent/GeoLite2-Country.mmdb") is None
