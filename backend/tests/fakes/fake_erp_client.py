"""
Client ERP factice en mémoire (ODOO_INTEGRATION_PLAN.md §2.5).

Aucune instance ERP réelle disponible en CI — ce faux client permet de
tester la logique PERMATEL (mapping/idempotence, routes /settings/erp)
sans XML-RPC réel. Même signature que `app.services.erp_client.ErpClient`
(`execute_kw(company_id, model, method, args, kwargs=None)`), pour être
substituable partout où un `ErpClient` est injecté par paramètre.
"""


class FakeErpClient:
    def __init__(self):
        # {model: {id: {field: value}}}
        self.data = {}
        self._next_id = {}
        self.calls = []  # historique des appels, pour assertions de test

    def _next(self, model):
        self._next_id[model] = self._next_id.get(model, 0) + 1
        return self._next_id[model]

    def execute_kw(self, company_id: int, model: str, method: str, args: list, kwargs: dict | None = None):
        if not company_id:
            raise ValueError("company_id est obligatoire.")
        self.calls.append((company_id, model, method, args, kwargs or {}))

        records = self.data.setdefault(model, {})

        if method == "create":
            values = args[0]
            new_id = self._next(model)
            records[new_id] = dict(values)
            return new_id

        if method == "write":
            ids, values = args[0], args[1]
            for rid in ids:
                records.setdefault(rid, {}).update(values)
            return True

        if method == "search_read":
            domain = args[0] if args else []
            fields = (args[1] if len(args) > 1 else None) or (kwargs or {}).get("fields")
            results = []
            for rid, rec in records.items():
                if self._matches(rec, domain):
                    row = {"id": rid, **({f: rec.get(f) for f in fields} if fields else rec)}
                    results.append(row)
            return results

        if method == "read":
            ids = args[0]
            fields = args[1] if len(args) > 1 else None
            return [
                {"id": rid, **({f: records.get(rid, {}).get(f) for f in fields} if fields else records.get(rid, {}))}
                for rid in ids
            ]

        raise NotImplementedError(f"FakeErpClient ne supporte pas '{method}'.")

    @staticmethod
    def _matches(record: dict, domain: list) -> bool:
        """Filtre de domaine minimal : liste de triplets (field, '=', value), combinés en ET."""
        for clause in domain:
            if not isinstance(clause, (list, tuple)) or len(clause) != 3:
                continue
            field, op, value = clause
            if op == "=" and record.get(field) != value:
                return False
        return True
