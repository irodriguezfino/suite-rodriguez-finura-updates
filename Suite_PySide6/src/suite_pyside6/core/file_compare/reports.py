from __future__ import annotations

import html
import json
from pathlib import Path

from .models import ComparisonResult


def as_text(result: ComparisonResult) -> str:
    state = "IGUALES" if result.strict_equal else "DIFERENTES"
    lines = [
        f"Resultado: {state}",
        f"Archivos: {result.left_path} <> {result.right_path}",
        f"Tipo: {result.detected_type}; metodo: {result.method}",
        f"Tamano: {result.left_size} / {result.right_size}; SHA-256: {result.left_sha256} / {result.right_sha256}",
        f"Diferencias: {result.total_differences}{' (resultado truncado)' if result.truncated else ''}",
    ]
    for difference in result.differences:
        lines.append(f"- [{difference.kind}] {difference.location}: {difference.left!r} -> {difference.right!r} {difference.detail}")
    lines.extend(f"Aviso: {warning}" for warning in result.warnings)
    lines.extend(f"Error: {error}" for error in result.errors)
    return "\n".join(lines)


def as_json(result: ComparisonResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str)


def as_html(result: ComparisonResult) -> str:
    title = "Iguales" if result.strict_equal else "Diferentes"
    rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in (item.kind, item.location, item.left, item.right, item.detail)) + "</tr>"
        for item in result.differences
    )
    warnings = "".join(f"<li>{html.escape(value)}</li>" for value in result.warnings + result.errors)
    return f"""<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>Comparacion: {title}</title>
<style>body{{font-family:system-ui;margin:2rem;color:#172033}} .equal{{color:#117a3d}} .different{{color:#b42318}} table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd3df;padding:.45rem;text-align:left;vertical-align:top;white-space:pre-wrap}}th{{background:#eef2f7}}</style></head>
<body><h1 class=\"{'equal' if result.strict_equal else 'different'}\">{title}</h1><p>{html.escape(result.left_path)}<br>{html.escape(result.right_path)}</p>
<dl><dt>Tipo</dt><dd>{html.escape(result.detected_type)}</dd><dt>Metodo</dt><dd>{html.escape(result.method)}</dd><dt>Diferencias</dt><dd>{result.total_differences}</dd></dl>
<h2>Diferencias</h2><table><thead><tr><th>Tipo</th><th>Ubicacion</th><th>Izquierda</th><th>Derecha</th><th>Detalle</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Avisos y errores</h2><ul>{warnings}</ul></body></html>"""


def write_report(result: ComparisonResult, path: str | Path, output_format: str) -> Path:
    target = Path(path)
    content = {"text": as_text, "json": as_json, "html": as_html}[output_format](result)
    target.write_text(content, encoding="utf-8")
    return target
