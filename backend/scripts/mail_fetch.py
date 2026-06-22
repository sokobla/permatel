#!/usr/bin/env python
"""
Collecte des emails entrants PERMATEL — exécutable via cron.

Relève par IMAP les nouveaux emails des tenants à réception activée.

Exemple cron (toutes les 5 minutes) :
    */5 * * * * cd /chemin/permatel/backend && /chemin/.venv/bin/python scripts/mail_fetch.py >> /var/log/permatel/mail.log 2>&1

Tâche planifiée Windows :
    schtasks /Create /SC MINUTE /MO 5 /TN "PERMATEL Mail Fetch" ^
      /TR "C:\\chemin\\permatel\\backend\\.venv\\Scripts\\python.exe C:\\chemin\\permatel\\backend\\scripts\\mail_fetch.py"
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.scripts.mail_fetch import fetch_all


def main():
    app = create_app()
    with app.app_context():
        try:
            summary = fetch_all(db)
        except Exception as exc:  # noqa: BLE001
            print(f"[{datetime.utcnow().isoformat()}] MAIL_FETCH_ERROR | {exc}", file=sys.stderr)
            return 1
        total = sum(v for v in summary.values() if isinstance(v, int))
        print(f"[{datetime.utcnow().isoformat()}] MAIL_FETCH_OK | total={total} | {summary}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
