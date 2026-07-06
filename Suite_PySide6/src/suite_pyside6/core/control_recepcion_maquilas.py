from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
import csv
import re
import smtplib
import tempfile

from suite_pyside6.core.recepcion_maquilas import (
    RecepcionResult,
    RegistroMaquila,
    decimal_a_es,
    decimal_desde_texto,
    generar_pdf_rangos,
    leer_config_articulos,
    process_recepcion_maquilas,
    valor_mayoritario,
)
from suite_pyside6.core.precintos_jamones import (
    gtin12_valido,
    parsear_peso,
    formatear_peso,
    sugerir_partida_lote,
)


SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USUARIO = "irodriguez@grupovall.com"
SMTP_PASSWORD = ""
ASUNTO_DEFECTO = "Recepcion maquilas - documentacion"
MENSAJE_DEFECTO = (
    "Buenos dias,\n\n"
    "Adjuntamos la documentacion correspondiente a la recepcion.\n\n"
    "Un saludo,"
)


@dataclass(frozen=True)
class ResultadoTipo:
    tipo: str
    total: int
    gtin_validos: int
    articulos_ibericos: int = 0


@dataclass(frozen=True)
class RegistroControlRecepcion:
    archivo: str
    linea: int
    campos: list[str]

    @property
    def partida(self) -> str:
        return self.campos[0].strip() if len(self.campos) > 0 else ""

    @property
    def fecha(self) -> str:
        return self.campos[1].strip() if len(self.campos) > 1 else ""

    @property
    def hora(self) -> str:
        return self.campos[2].strip() if len(self.campos) > 2 else ""

    @property
    def codigo_fac(self) -> str:
        return self.campos[3].strip() if len(self.campos) > 3 else ""

    @property
    def precinto(self) -> str:
        return re.sub(r"\D+", "", self.campos[4] if len(self.campos) > 4 else "")

    @property
    def lote(self) -> str:
        return self.campos[5].strip() if len(self.campos) > 5 else ""

    @property
    def peso(self) -> str:
        return self.campos[6].strip() if len(self.campos) > 6 else ""

    def to_maquila(self) -> RegistroMaquila:
        return RegistroMaquila(
            archivo=self.archivo,
            linea=self.linea,
            partida=self.partida,
            fecha=self.fecha,
            hora=self.hora,
            codigo_fac=self.codigo_fac,
            precinto=self.precinto,
            lote=self.lote,
            peso=decimal_desde_texto(self.peso),
        )

    def to_line(self) -> str:
        campos = list(self.campos[:7])
        while len(campos) < 7:
            campos.append("")
        return ";".join(campos) + ";"


@dataclass
class ControlRecepcionResult:
    source_files: list[Path] = field(default_factory=list)
    validos: list[RegistroControlRecepcion] = field(default_factory=list)
    invalidos: list[tuple[RegistroControlRecepcion, str]] = field(default_factory=list)
    duplicados: list[RegistroControlRecepcion] = field(default_factory=list)
    recepcion: RecepcionResult | None = None
    txt_ax: Path | None = None
    pdf_rangos: Path | None = None
    txt_modified: bool = False
    tipo: ResultadoTipo = field(default_factory=lambda: ResultadoTipo("Pendiente", 0, 0, 0))
    partida_sugerida: str = ""
    lote_sugerido: str = ""

    def summary_lines(self) -> list[str]:
        peso_total = sum((registro.to_maquila().peso for registro in self.validos), decimal_desde_texto("0"))
        lines = [
            f"TXT cargados: {len(self.source_files)}",
            f"Registros validos: {len(self.validos)}",
            f"Incidencias: {len(self.invalidos)}",
            f"Duplicados suprimidos: {len(self.duplicados)}",
            f"Peso secaderos: {decimal_a_es(peso_total, 2)} kg",
            f"Tipo detectado: {self.tipo.tipo}",
        ]
        if self.recepcion is not None:
            lines.extend(
                [
                    f"Precintos albaran: {len(self.recepcion.registros_oficiales)}",
                    f"Fuera de albaran: {len(self.recepcion.solo_txt)}",
                    f"No recibidos: {len(self.recepcion.solo_oficial)}",
                    f"Filas rangos: {len(self.recepcion.filas_rangos)}",
                ]
            )
        if self.txt_ax:
            lines.append(f"TXT AX: {self.txt_ax}")
        elif self.validos and not self.txt_modified:
            lines.append("TXT AX: no necesario; el TXT original es valido")
        if self.pdf_rangos:
            lines.append(f"PDF rangos: {self.pdf_rangos}")
        return lines

    def preview_text(self) -> str:
        lines = self.summary_lines()
        if self.invalidos:
            lines.append("")
            lines.append("Incidencias:")
            lines.extend(f"- {registro.archivo}:{registro.linea} {motivo}" for registro, motivo in self.invalidos[:40])
        if self.recepcion is not None:
            lines.append("")
            lines.append(self.recepcion.preview_text())
        return "\n".join(lines)


def parse_control_line(line: str, archivo: str, numero: int) -> RegistroControlRecepcion | None:
    if not line.strip():
        return None
    try:
        campos = next(csv.reader([line], delimiter=";", quotechar='"'))
    except csv.Error:
        campos = line.split(";")
    if campos and campos[-1] == "":
        campos = campos[:-1]
    return RegistroControlRecepcion(archivo=archivo, linea=numero, campos=campos)


def producto_parece_iberico(nombre: str) -> bool:
    texto = (nombre or "").upper()
    return any(marca in texto for marca in ("IBER", "BELLOTA", "CEBO"))


def codigos_ibericos_desde_config(rangos_por_codigo: dict) -> set[str]:
    codigos: set[str] = set()
    for codigo, rangos in (rangos_por_codigo or {}).items():
        if any(producto_parece_iberico(getattr(rango, "nombre_producto", "")) for rango in rangos):
            codigos.add(str(codigo).strip())
    return codigos


def detectar_tipo_jamon(
    registros: list[RegistroControlRecepcion],
    codigos_ibericos: set[str] | None = None,
) -> ResultadoTipo:
    precintos = [registro.precinto for registro in registros if re.fullmatch(r"\d{12}", registro.precinto or "")]
    gtin_validos = sum(1 for codigo in precintos if gtin12_valido(codigo))
    total = len(precintos)
    codigos_ibericos = codigos_ibericos or set()
    articulos_ibericos = sum(1 for registro in registros if registro.codigo_fac in codigos_ibericos)
    if articulos_ibericos:
        return ResultadoTipo("Iberico", total, gtin_validos, articulos_ibericos)
    if total and gtin_validos >= max(1, (total + 1) // 2):
        return ResultadoTipo("Iberico", total, gtin_validos, articulos_ibericos)
    return ResultadoTipo("Blanco", total, gtin_validos, articulos_ibericos)


def _codigos_ibericos_config(config_file: Path | None) -> tuple[set[str], list[str]]:
    config = config_file or Path()
    if not config:
        return set(), []
    try:
        rangos, incidencias = leer_config_articulos(config)
    except Exception:
        return set(), []
    return codigos_ibericos_desde_config(rangos), incidencias


def validate_control_record(
    registro: RegistroControlRecepcion,
    tipo_jamon: str = "Blanco",
    partida_sugerida: str = "",
    lote_sugerido: str = "",
) -> list[str]:
    motivos: list[str] = []
    if len(registro.campos) < 7:
        motivos.append(f"tiene {len(registro.campos)} campos; se esperaban 7")
    if not re.fullmatch(r"\d{6}", registro.partida):
        if partida_sugerida:
            motivos.append(f"partida no valida; sugerida {partida_sugerida}")
        else:
            motivos.append("partida no valida")
    if not re.fullmatch(r"\d{12}", registro.precinto):
        motivos.append("debe tener exactamente 12 digitos numericos")
    elif tipo_jamon.lower() == "iberico" and not gtin12_valido(registro.precinto):
        motivos.append("GTIN-12 incorrecto")
    if not registro.codigo_fac:
        motivos.append("codigo FAC vacio")
    if not registro.lote:
        motivos.append(f"lote vacio; sugerido {lote_sugerido}" if lote_sugerido else "lote vacio")
    try:
        decimal_desde_texto(registro.peso)
    except Exception:
        motivos.append("peso no valido")
    return motivos


def leer_control_txt(paths: list[Path]) -> list[RegistroControlRecepcion]:
    registros: list[RegistroControlRecepcion] = []
    for path in paths:
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                lines = path.read_text(encoding=encoding).splitlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        for numero, line in enumerate(lines, start=1):
            registro = parse_control_line(line, path.name, numero)
            if registro is not None:
                registros.append(registro)
    return registros


def dedupe_records(registros: list[RegistroControlRecepcion]) -> tuple[list[RegistroControlRecepcion], list[RegistroControlRecepcion]]:
    vistos: set[str] = set()
    validos: list[RegistroControlRecepcion] = []
    duplicados: list[RegistroControlRecepcion] = []
    for registro in registros:
        if registro.precinto in vistos:
            duplicados.append(registro)
            continue
        vistos.add(registro.precinto)
        validos.append(registro)
    return validos, duplicados


def process_control_txt(paths: list[Path], config_file: Path | None = None) -> ControlRecepcionResult:
    registros = leer_control_txt(paths)
    codigos_ibericos, _incidencias_config = _codigos_ibericos_config(config_file)
    tipo = detectar_tipo_jamon(registros, codigos_ibericos)
    partida, lote = sugerir_partida_lote(registros)
    validos_pre: list[RegistroControlRecepcion] = []
    invalidos: list[tuple[RegistroControlRecepcion, str]] = []
    for registro in registros:
        motivos = validate_control_record(registro, tipo.tipo, partida, lote)
        if motivos:
            invalidos.append((registro, "; ".join(motivos)))
        else:
            validos_pre.append(registro)
    validos, duplicados = dedupe_records(validos_pre)
    return ControlRecepcionResult(
        source_files=list(paths),
        validos=validos,
        invalidos=invalidos,
        duplicados=duplicados,
        txt_modified=bool(invalidos or duplicados),
        tipo=tipo,
        partida_sugerida=partida,
        lote_sugerido=lote,
    )


def correction_text(result: ControlRecepcionResult) -> str:
    if not result.invalidos:
        return "# Sin incidencias pendientes.\n"
    blocks = ["# Corrige las lineas de datos. Las lineas que empiezan por # se ignoran al revalidar."]
    for registro, motivo in result.invalidos:
        blocks.append(f"# Archivo: {registro.archivo} | linea: {registro.linea} | motivo: {motivo}")
        blocks.append(registro.to_line())
    return "\n".join(blocks) + "\n"


def revalidate_corrections(result: ControlRecepcionResult, text: str) -> ControlRecepcionResult:
    corrected: list[RegistroControlRecepcion] = []
    errors: list[tuple[RegistroControlRecepcion, str]] = []
    partida, lote = sugerir_partida_lote(result.validos)
    partida = partida or result.partida_sugerida
    lote = lote or result.lote_sugerido
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        registro = parse_control_line(stripped, "CORRECCION_MANUAL", index)
        if registro is None:
            continue
        motivos = validate_control_record(registro, result.tipo.tipo, partida, lote)
        if motivos:
            errors.append((registro, "; ".join(motivos)))
        else:
            corrected.append(registro)
    validos, duplicados = dedupe_records(result.validos + corrected)
    return ControlRecepcionResult(
        source_files=list(result.source_files),
        validos=validos,
        invalidos=errors,
        duplicados=list(result.duplicados) + duplicados,
        recepcion=None,
        txt_ax=None,
        pdf_rangos=None,
        txt_modified=True,
        tipo=result.tipo,
        partida_sugerida=partida,
        lote_sugerido=lote,
    )


def weight_filter_text(
    result: ControlRecepcionResult,
    minimo_texto: str = "",
    maximo_texto: str = "",
) -> tuple[str, str, bool]:
    minimo = parsear_peso(minimo_texto) if minimo_texto.strip() else None
    maximo = parsear_peso(maximo_texto) if maximo_texto.strip() else None
    if minimo is None and maximo is None:
        raise ValueError("Introduce peso minimo, maximo o ambos.")
    if minimo_texto.strip() and minimo is None:
        raise ValueError("Peso minimo no valido. Ejemplos: 10, 10,5 o 10.5.")
    if maximo_texto.strip() and maximo is None:
        raise ValueError("Peso maximo no valido. Ejemplos: 16, 16,5 o 16.5.")
    if minimo is not None and maximo is not None and minimo > maximo:
        raise ValueError("El peso minimo no puede ser superior al maximo.")

    fuera: list[tuple[RegistroControlRecepcion, str]] = []
    pesos_no_validos: list[RegistroControlRecepcion] = []
    for registro in result.validos:
        peso = parsear_peso(registro.peso)
        if peso is None:
            pesos_no_validos.append(registro)
            continue
        if minimo is not None and peso < minimo:
            fuera.append((registro, f"peso {registro.peso} inferior al minimo {formatear_peso(minimo)}"))
        elif maximo is not None and peso > maximo:
            fuera.append((registro, f"peso {registro.peso} superior al maximo {formatear_peso(maximo)}"))

    if not fuera and not pesos_no_validos:
        editor = "# No hay registros fuera del rango de peso indicado.\n"
    else:
        bloques = [
            "# Registros filtrados por peso.",
            "# Modifica estas lineas y pulsa Revalidar para sustituir el registro original.",
            "# Las lineas que empiezan por # se ignoran al revalidar.",
        ]
        for registro, motivo in fuera:
            bloques.append(f"# Archivo: {registro.archivo} | linea: {registro.linea} | motivo: {motivo}")
            bloques.append(registro.to_line())
        for registro in pesos_no_validos:
            bloques.append(f"# Archivo: {registro.archivo} | linea: {registro.linea} | motivo: peso no numerico o vacio")
            bloques.append(registro.to_line())
        editor = "\n".join(bloques) + "\n"

    resumen = "\n".join(
        [
            "Filtro de pesos aplicado:",
            f"- Peso minimo: {formatear_peso(minimo) if minimo is not None else '(sin minimo)'}",
            f"- Peso maximo: {formatear_peso(maximo) if maximo is not None else '(sin maximo)'}",
            f"- Fuera de rango: {len(fuera)}",
            f"- Peso no numerico/vacio: {len(pesos_no_validos)}",
        ]
    )
    return editor, resumen, bool(fuera or pesos_no_validos)


def save_txt_ax(path: Path, result: ControlRecepcionResult) -> Path:
    if result.invalidos:
        raise ValueError("Corrige las incidencias antes de guardar el TXT AX.")
    text = "\r\n".join(registro.to_line() for registro in result.validos)
    path.write_text(text + ("\r\n" if text else ""), encoding="cp1252", newline="")
    result.txt_ax = path
    result.txt_modified = False
    return path


def txt_for_recepcion(result: ControlRecepcionResult) -> Path:
    if result.invalidos:
        raise ValueError("Corrige las incidencias antes de cruzar con SealsReport.")
    if result.txt_ax is not None:
        return result.txt_ax
    if not result.txt_modified and len(result.source_files) == 1 and result.source_files[0].exists():
        return result.source_files[0]
    raise ValueError("Guarda primero el TXT AX corregido.")


def run_recepcion_with_seals(
    result: ControlRecepcionResult,
    seals_file: Path,
    config_file: Path | None = None,
) -> RecepcionResult:
    temp_txt = txt_for_recepcion(result)
    recepcion = process_recepcion_maquilas(temp_txt, seals_file, config_file)
    result.recepcion = recepcion
    return recepcion


def save_pdf_rangos(path: Path, result: ControlRecepcionResult, metadata: dict[str, str] | None = None) -> Path:
    if result.recepcion is None:
        raise ValueError("Procesa primero SealsReport.")
    generar_pdf_rangos(path, result.recepcion, metadata)
    result.pdf_rangos = path
    return path


def write_detail_txt(path: Path, result: ControlRecepcionResult) -> Path:
    path.write_text(detalle_diferencias_text(result), encoding="utf-8", newline="")
    return path


def parsear_destinatarios(texto: str) -> list[str]:
    candidatos = [part.strip() for part in re.split(r"[;,\s]+", texto or "") if part.strip()]
    vistos: set[str] = set()
    resultado: list[str] = []
    for correo in candidatos:
        clave = correo.lower()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(correo)
    return resultado


def validar_destinatarios(destinatarios: list[str]) -> list[str]:
    return [correo for correo in destinatarios if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo)]


def detalle_diferencias_text(result: ControlRecepcionResult) -> str:
    lines = result.summary_lines()
    if result.recepcion is not None:
        lines.append("")
        lines.append("Recibidos fuera de albaran:")
        lines.extend(registro.precinto for registro in result.recepcion.solo_txt)
        lines.append("")
        lines.append("No recibidos del albaran:")
        lines.extend(registro.precinto for registro in result.recepcion.solo_oficial)
    return "\r\n".join(lines) + "\r\n"


def send_control_email(
    destinatarios_texto: str,
    result: ControlRecepcionResult,
    *,
    subject: str = ASUNTO_DEFECTO,
    body: str = MENSAJE_DEFECTO,
    metadata: dict[str, str] | None = None,
    smtp_host: str = SMTP_HOST,
    smtp_port: int = SMTP_PORT,
    smtp_user: str = SMTP_USUARIO,
    smtp_password: str = SMTP_PASSWORD,
) -> EmailMessage:
    destinatarios = parsear_destinatarios(destinatarios_texto)
    if not destinatarios:
        raise ValueError("Introduce al menos una direccion de correo.")
    invalidos = validar_destinatarios(destinatarios)
    if invalidos:
        raise ValueError("Direcciones no validas: " + ", ".join(invalidos))
    if result.recepcion is None:
        raise ValueError("Cruza primero con SealsReport.")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = subject.format(
        partida=valor_mayoritario(registro.partida for registro in result.validos),
        registros_validos=len(result.validos),
    )
    msg.set_content(body)

    with tempfile.TemporaryDirectory(prefix="control_recepcion_correo_") as tmp:
        tmp_path = Path(tmp)
        detail = write_detail_txt(tmp_path / "detalle_diferencias.txt", result)
        pdf = result.pdf_rangos if result.pdf_rangos and result.pdf_rangos.exists() else tmp_path / "Informe rangos recepcion.pdf"
        if not pdf.exists():
            save_pdf_rangos(pdf, result, metadata)
        for path in (detail, pdf):
            subtype = "pdf" if path.suffix.lower() == ".pdf" else "plain"
            maintype = "application" if subtype == "pdf" else "text"
            msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
            if smtp_user:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
    return msg
