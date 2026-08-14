"""
Client ERP (Phase 6, ODOO_INTEGRATION_PLAN.md §2.2/§2.3).

Wrapper mince autour de `xmlrpc.client` (stdlib, aucune dépendance tierce
type odoorpc/OdooRPC — cohérent avec la préférence déjà actée du projet
pour la stdlib plutôt qu'une lib tierce, cf. §4.2 "grille custom plutôt
qu'une lib calendrier tierce").

Le client est INJECTÉ par paramètre dans le code appelant, jamais un
singleton module-level — nécessaire pour substituer `FakeErpClient`
(tests/fakes/fake_erp_client.py) en test, aucune instance ERP réelle
n'étant disponible en CI (§2.5).

Topologie : une seule instance ERP partagée entre tenants, scopée par
`company_id` (res.company) — voir §2.3. `company_id` est donc un
paramètre OBLIGATOIRE de execute_kw, jamais un défaut implicite : c'est
la seule barrière empêchant un appel de fuiter des données d'un autre
tenant/société ERP.
"""
import xmlrpc.client
import http.client


class ErpClientError(Exception):
    """Erreur de communication avec l'ERP (réseau, timeout, fault XML-RPC, auth)."""


class _TimeoutTransport(xmlrpc.client.Transport):
    """Transport XML-RPC avec timeout socket (§2.1 : tentative synchrone courte, 2-3s)."""

    def __init__(self, timeout, use_https, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timeout = timeout
        self._use_https = use_https

    def make_connection(self, host):
        conn_cls = http.client.HTTPSConnection if self._use_https else http.client.HTTPConnection
        return conn_cls(host, timeout=self._timeout)


class ErpClient:
    def __init__(self, url: str, db: str, username: str, password: str, timeout: int = 3):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.timeout = timeout
        self._uid = None

    def _transport(self):
        return _TimeoutTransport(self.timeout, self.url.startswith("https"))

    def _common(self):
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", transport=self._transport())

    def _object_proxy(self):
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", transport=self._transport())

    def _authenticate(self) -> int:
        if self._uid is not None:
            return self._uid
        try:
            uid = self._common().authenticate(self.db, self.username, self.password, {})
        except (xmlrpc.client.Fault, OSError, TimeoutError) as exc:
            raise ErpClientError(f"Authentification ERP échouée : {exc}") from exc
        if not uid:
            raise ErpClientError("Authentification ERP refusée (identifiants invalides).")
        self._uid = uid
        return uid

    def execute_kw(self, company_id: int, model: str, method: str, args: list, kwargs: dict | None = None):
        """
        Exécute une méthode ERP (`execute_kw`), scopée à `company_id` via
        `allowed_company_ids`/`company_id` de contexte (§2.3) — jamais
        automatique côté ERP, à injecter explicitement à chaque appel.
        """
        if not company_id:
            raise ValueError("company_id est obligatoire (jamais de défaut implicite, cf. §2.3).")

        uid = self._authenticate()
        call_kwargs = dict(kwargs or {})
        context = dict(call_kwargs.get("context") or {})
        context.setdefault("allowed_company_ids", [company_id])
        context.setdefault("company_id", company_id)
        call_kwargs["context"] = context

        try:
            return self._object_proxy().execute_kw(
                self.db, uid, self.password, model, method, args, call_kwargs,
            )
        except (xmlrpc.client.Fault, OSError, TimeoutError) as exc:
            raise ErpClientError(f"Appel ERP échoué ({model}.{method}) : {exc}") from exc
