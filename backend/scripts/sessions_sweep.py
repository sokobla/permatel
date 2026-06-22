#!/usr/bin/env python
"""
Script de maintenance des sessions PERMATEL — exécutable via cron.

Expire les sessions inactives et purge la blocklist des tokens expirés.

Exemples cron (toutes les 10 minutes) :
    */10 * * * * cd /chemin/permatel/backend && /chemin/.venv/bin/python scripts/sessions_sweep.py >> /var/log/permatel/sweep.log 2>&1

Tâche planifiée Windows (équivalent) :
    schtasks /Create /SC MINUTE /MO 10 /TN "PERMATEL Sessions Sweep" ^
      /TR "C:\\chemin\\permatel\\backend\\.venv\\Scripts\\python.exe C:\\chemin\\permatel\\backend\\scripts\\sessions_sweep.py"

Code de sortie : 0 si succès, 1 si erreur.
"""

import os
import sys
from datetime import datetime

# Permet d'importer le package `app` quel que soit le répertoire d'appel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.scripts.session_maintenance import sweep_sessions


def main():
    app = create_app()
    with app.app_context():
        try:
            result = sweep_sessions(db)
        except Exception as exc:  # noqa: BLE001
            print(f"[{datetime.utcnow().isoformat()}] SESSIONS_SWEEP_ERROR | {exc}", file=sys.stderr)
            return 1
        print(
            f"[{datetime.utcnow().isoformat()}] SESSIONS_SWEEP_OK | "
            f"expired={result['expired']} purged={result['purged']}"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
