"""
Logger structuré pour PERMATEL.
En développement : format lisible.
En production : format JSON exploitable par ELK / Datadog / Loki.
"""
import json
import logging
import os
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Formateur JSON pour les logs de production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str = "permatel") -> logging.Logger:
    """
    Retourne un logger configuré selon l'environnement.
    FLASK_ENV=production → JSON, sinon → texte lisible.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Déjà configuré

    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()

    if os.environ.get("FLASK_ENV") == "production":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    logger.addHandler(handler)
    return logger


# Logger auth dédié — importé directement dans auth.py
auth_logger = get_logger("permatel.auth")
tenant_logger = get_logger("permatel.tenant")
client_logger = get_logger("permatel.client")