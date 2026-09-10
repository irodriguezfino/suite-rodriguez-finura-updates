from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import re
import smtplib

from suite_pyside6.core.control_recepcion_maquilas import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_SECURE, SMTP_USER


DEFAULT_SUBJECT = "Etiquetas impresas: último código {ultimo_codigo}"
DEFAULT_BODY = (
    "Buenos días,\n\n"
    "Se ha confirmado la impresión de {cantidad} etiqueta(s).\n\n"
    "Último código impreso: {ultimo_codigo}\n"
    "Siguiente código sugerido: {siguiente_codigo}\n\n"
    "Un saludo,"
)
MAX_LABELS_PER_JOB = 5_000


class SequenceFormatError(ValueError):
    """El identificador no contiene un bloque decimal que pueda incrementarse."""


@dataclass(frozen=True)
class LabelLayout:
    """Configuración física de una etiqueta con un único campo imprimible."""

    width_mm: float = 50.0
    height_mm: float = 120.0
    x_mm: float = 5.0
    y_mm: float = 42.0
    zone_width_mm: float = 40.0
    zone_height_mm: float = 36.0
    font_family: str = "Arial"
    font_size_pt: float = 48.0
    alignment: str = "center"
    bold: bool = True

    def normalized(self) -> "LabelLayout":
        width = max(10.0, float(self.width_mm))
        height = max(10.0, float(self.height_mm))
        zone_width = min(max(2.0, float(self.zone_width_mm)), width)
        zone_height = min(max(2.0, float(self.zone_height_mm)), height)
        return LabelLayout(
            width_mm=width,
            height_mm=height,
            x_mm=min(max(0.0, float(self.x_mm)), width - zone_width),
            y_mm=min(max(0.0, float(self.y_mm)), height - zone_height),
            zone_width_mm=zone_width,
            zone_height_mm=zone_height,
            font_family=str(self.font_family or "Arial"),
            font_size_pt=min(max(6.0, float(self.font_size_pt)), 288.0),
            alignment=self.alignment if self.alignment in {"left", "center", "right"} else "center",
            bold=bool(self.bold),
        )


_COUNTER_SEGMENT = re.compile(r"^(.*?)(\d+)(\D*)$")


def increment_code(value: str, amount: int = 1) -> str:
    """Incrementa el último tramo numérico y conserva prefijo, sufijo y ceros."""
    match = _COUNTER_SEGMENT.fullmatch(str(value or "").strip())
    if match is None:
        raise SequenceFormatError("El código inicial debe incluir al menos un bloque numérico.")
    if amount < 0:
        raise ValueError("El incremento no puede ser negativo.")
    prefix, number, suffix = match.groups()
    return f"{prefix}{int(number) + amount:0{len(number)}d}{suffix}"


def sequence_values(first_code: str, quantity: int) -> tuple[str, ...]:
    if quantity < 1:
        raise ValueError("La cantidad debe ser al menos una etiqueta.")
    if quantity > MAX_LABELS_PER_JOB:
        raise ValueError(f"Para mantener estable la impresión, el lote no puede superar {MAX_LABELS_PER_JOB:,} etiquetas.")
    increment_code(first_code)
    return tuple(increment_code(first_code, offset) for offset in range(quantity))


def parse_recipients(value: str) -> list[str]:
    result: list[str] = []
    for item in re.split(r"[;,\n]+", str(value or "")):
        address = item.strip()
        if address and address.lower() not in {saved.lower() for saved in result}:
            result.append(address)
    return result


def invalid_recipients(recipients: list[str]) -> list[str]:
    return [item for item in recipients if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", item)]


def render_mail_template(text: str, values: dict[str, str]) -> str:
    try:
        return str(text).format(**values)
    except (KeyError, ValueError):
        return str(text)


def send_label_status_email(recipients_text: str, *, subject: str, body: str) -> EmailMessage:
    recipients = parse_recipients(recipients_text)
    if not recipients:
        raise ValueError("Introduce al menos una dirección de correo.")
    if invalid_recipients(recipients):
        raise ValueError("Revisa las direcciones de correo indicadas.")
    message = EmailMessage()
    message["From"] = SMTP_USER
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            if SMTP_SECURE:
                smtp.starttls()
                smtp.ehlo()
            if SMTP_USER and SMTP_PASSWORD:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    except smtplib.SMTPException as exc:
        raise RuntimeError("No se pudo enviar el correo con el servidor corporativo.") from exc
    except OSError as exc:
        raise RuntimeError("No se pudo conectar con el servidor de correo corporativo.") from exc
    return message
