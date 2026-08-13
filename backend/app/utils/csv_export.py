"""Construction de réponses CSV pour les exports de données brutes (module
Rapports). Motif extrait de `app/routes/telephony.py::export_calls_csv`."""
import csv
import io

from flask import Response

MAX_EXPORT_ROWS = 10_000


def build_csv_response(header: list[str], rows: list[list], filename: str) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for r in rows:
        writer.writerow(r)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
