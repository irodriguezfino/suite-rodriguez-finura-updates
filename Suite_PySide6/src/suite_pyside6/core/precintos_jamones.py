from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
import os
from pathlib import Path
import re
import smtplib
from difflib import SequenceMatcher

import openpyxl


TIPOS_JAMON = ("Blanco", "Iberico")
CAMPOS_ESPERADOS = 7
SMTP_HOST = "smtp.vallcompanys.es"
SMTP_PORT = 25
SMTP_USER = "envio@smtp.erod.es"
SMTP_USUARIO = SMTP_USER
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or os.environ.get("SUITE_PRECINTOS_SMTP_PASSWORD", "")
SMTP_SECURE = False
SMTP_STARTTLS = SMTP_SECURE
ASUNTO_CORREO_DEFECTO = "Control precintos jamones"
MENSAJE_CORREO_DEFECTO = (
    "Adjunto se envian los ficheros generados por Control Precintos Jamones.\n\n"
    "Tipo: {tipo_jamon}\n"
    "Registros validos: {registros_validos}\n"
    "Incidencias pendientes: {incidencias}\n"
    "Duplicados suprimidos: {duplicados}\n"
)


@dataclass(frozen=True)
class RegistroJamones:
    archivo: str
    linea: int
    campos: list[str]
    orden: int

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
    def codigo_articulo(self) -> str:
        return self.campos[3].strip() if len(self.campos) > 3 else ""

    @property
    def precinto(self) -> str:
        return self.campos[4].strip() if len(self.campos) > 4 else ""

    @property
    def lote(self) -> str:
        return self.campos[5].strip() if len(self.campos) > 5 else ""

    @property
    def peso(self) -> str:
        return self.campos[6].strip() if len(self.campos) > 6 else ""

    def fecha_hora(self) -> datetime | None:
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%y %H:%M:%S"):
            try:
                return datetime.strptime(f"{self.fecha} {self.hora}", fmt)
            except ValueError:
                continue
        return None

    def a_linea(self) -> str:
        campos = list(self.campos[:CAMPOS_ESPERADOS])
        while len(campos) < CAMPOS_ESPERADOS:
            campos.append("")
        return ";".join(campos) + ";"


@dataclass
class PrecintosJamonesResult:
    selected_files: list[Path] = field(default_factory=list)
    tipo_jamon: str = "Blanco"
    validos: list[RegistroJamones] = field(default_factory=list)
    invalidos: list[tuple[RegistroJamones, str]] = field(default_factory=list)
    duplicados: list[RegistroJamones] = field(default_factory=list)
    oficiales: set[str] = field(default_factory=set)

    def differences(self) -> tuple[set[str], set[str]]:
        registros = list(self.validos) + [registro for registro, _motivo in self.invalidos]
        leidos = {registro.precinto for registro in registros if re.fullmatch(r"\d{12}", registro.precinto)}
        return leidos - self.oficiales, self.oficiales - leidos

    def summary_lines(self) -> list[str]:
        lines = [
            f"Tipo: {self.tipo_jamon}",
            f"Archivos: {len(self.selected_files)}",
            f"Registros validos: {len(self.validos)}",
            f"Incidencias: {len(self.invalidos)}",
            f"Duplicados suprimidos: {len(self.duplicados)}",
        ]
        if self.oficiales:
            extra, missing = self.differences()
            lines.extend(
                [
                    f"Precintos oficiales: {len(self.oficiales)}",
                    f"Leidos fuera del oficial: {len(extra)}",
                    f"Oficiales no leidos: {len(missing)}",
                ]
            )
        return lines

    def preview_text(self) -> str:
        lines = self.summary_lines()
        if self.invalidos:
            lines.append("")
            lines.append("Incidencias:")
            for registro, motivo in self.invalidos[:80]:
                lines.append(f"- {registro.archivo}:{registro.linea} {registro.precinto or '(sin precinto)'} | {motivo}")
        if self.duplicados:
            lines.append("")
            lines.append("Duplicados suprimidos:")
            for registro in self.duplicados[:40]:
                lines.append(f"- {registro.precinto} | {registro.fecha} {registro.hora} | {registro.archivo}:{registro.linea}")
        if self.oficiales:
            extra, missing = self.differences()
            if extra:
                lines.append("")
                lines.append("Leidos fuera del Excel oficial:")
                lines.extend(f"- {item}" for item in sorted(extra)[:80])
            if missing:
                lines.append("")
                lines.append("Oficiales no leidos:")
                lines.extend(f"- {item}" for item in sorted(missing)[:80])
        return "\n".join(lines)


def normalizar_precinto(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def gtin12_valido(codigo: str) -> bool:
    if not re.fullmatch(r"\d{12}", codigo):
        return False
    digits = [int(char) for char in codigo]
    total = sum(digits[index] * (3 if index % 2 == 0 else 1) for index in range(11))
    check = (10 - (total % 10)) % 10
    return check == digits[11]


def distancia_digitos(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(1 for x, y in zip(a, b) if x != y)


def es_transposicion_simple(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    diferentes = [index for index, (x, y) in enumerate(zip(a, b)) if x != y]
    return (
        len(diferentes) == 2
        and a[diferentes[0]] == b[diferentes[1]]
        and a[diferentes[1]] == b[diferentes[0]]
    )


def sugerir_precintos(codigo: str, oficiales: set[str], max_sugerencias: int = 3) -> list[str]:
    limpio = normalizar_precinto(codigo)
    if not limpio or not oficiales:
        return []
    candidatos: list[tuple[int, float, str]] = []
    for oficial in oficiales:
        distancia = distancia_digitos(limpio, oficial)
        ratio = SequenceMatcher(None, limpio, oficial).ratio()
        transposicion = es_transposicion_simple(limpio, oficial)
        if distancia <= 2 or transposicion or ratio >= 0.84:
            penalizacion = 0 if transposicion else distancia
            candidatos.append((penalizacion, -ratio, oficial))
    candidatos.sort()
    return [oficial for _penalizacion, _ratio, oficial in candidatos[:max_sugerencias]]


def validar_precinto(codigo: str, tipo_jamon: str) -> tuple[bool, str]:
    limpio = normalizar_precinto(codigo)
    if codigo != limpio:
        return False, "contiene caracteres no numericos"
    if not re.fullmatch(r"\d{12}", codigo):
        return False, "debe tener exactamente 12 digitos numericos"
    if tipo_jamon.lower() == "iberico" and not gtin12_valido(codigo):
        return False, "GTIN-12 incorrecto"
    return True, ""


def valor_mayoritario(values) -> str:
    counter = Counter(value.strip() for value in values if value and value.strip())
    if not counter:
        return ""
    common = counter.most_common(2)
    value, count = common[0]
    if len(common) > 1 and count == common[1][1]:
        return ""
    return value


def sugerir_partida_lote(registros) -> tuple[str, str]:
    records = list(registros)
    partida = valor_mayoritario(record.partida for record in records if re.fullmatch(r"\d{6}", record.partida))
    lote = valor_mayoritario(record.lote for record in records)
    return partida, lote


def validar_registro_completo(
    registro: RegistroJamones,
    tipo_jamon: str,
    partida_sugerida: str = "",
    lote_sugerido: str = "",
) -> list[str]:
    motivos: list[str] = []
    if len(registro.campos) < CAMPOS_ESPERADOS:
        motivos.append(f"faltan campos: {len(registro.campos)} de {CAMPOS_ESPERADOS}")
    if not re.fullmatch(r"\d{6}", registro.partida):
        if partida_sugerida:
            motivos.append(f"partida no valida; sugerida {partida_sugerida}")
        else:
            motivos.append("partida no valida")
    if not registro.lote:
        motivos.append(f"lote vacio; sugerido {lote_sugerido}" if lote_sugerido else "lote vacio")
    ok, motivo = validar_precinto(registro.precinto, tipo_jamon)
    if not ok:
        motivos.append(motivo)
    return motivos


def parsear_peso(valor: str) -> float | None:
    texto = (valor or "").strip().replace(".", "").replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def formatear_peso(valor: float) -> str:
    texto = f"{valor:.3f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def parsear_linea(line: str, archivo: str, numero_linea: int, orden: int) -> RegistroJamones | None:
    if not line.strip():
        return None
    try:
        campos = next(csv.reader([line.strip("\r\n")], delimiter=";", quotechar='"'))
    except csv.Error:
        campos = line.strip("\r\n").split(";")
    if campos and campos[-1] == "":
        campos = campos[:-1]
    return RegistroJamones(archivo=archivo, linea=numero_linea, campos=campos, orden=orden)


def leer_ficheros(paths) -> list[RegistroJamones]:
    registros: list[RegistroJamones] = []
    orden = 0
    for path in paths:
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                lines = Path(path).read_text(encoding=encoding).splitlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            lines = Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines()
        for numero, line in enumerate(lines, start=1):
            orden += 1
            registro = parsear_linea(line, Path(path).name, numero, orden)
            if registro is not None:
                registros.append(registro)
    return registros


def es_mas_reciente(nuevo: RegistroJamones, actual: RegistroJamones) -> bool:
    nueva = nuevo.fecha_hora()
    actual_dt = actual.fecha_hora()
    if nueva and actual_dt and nueva != actual_dt:
        return nueva > actual_dt
    if nueva and not actual_dt:
        return True
    if not nueva and actual_dt:
        return False
    return nuevo.orden > actual.orden


def deduplicar(registros: list[RegistroJamones]) -> tuple[list[RegistroJamones], list[RegistroJamones]]:
    por_precinto: dict[str, RegistroJamones] = {}
    eliminados: list[RegistroJamones] = []
    for registro in registros:
        anterior = por_precinto.get(registro.precinto)
        if anterior is None:
            por_precinto[registro.precinto] = registro
            continue
        if es_mas_reciente(registro, anterior):
            eliminados.append(anterior)
            por_precinto[registro.precinto] = registro
        else:
            eliminados.append(registro)
    return sorted(por_precinto.values(), key=lambda item: item.orden), eliminados


def leer_precintos_excel_oficial(path: Path) -> list[str]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            header_row = -1
            column = -1
            for row_index, row in enumerate(rows):
                for col_index, value in enumerate(row):
                    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
                    if text == "numero del precinto":
                        header_row = row_index
                        column = col_index
                        break
                if column >= 0:
                    break
            if column < 0:
                continue
            precintos: list[str] = []
            seen: set[str] = set()
            for row in rows[header_row + 1:]:
                value = normalizar_precinto(str(row[column] if column < len(row) else ""))
                if re.fullmatch(r"\d{12}", value) and value not in seen:
                    seen.add(value)
                    precintos.append(value)
            return precintos
    finally:
        wb.close()
    raise ValueError("No se encontro la columna 'Numero del precinto' en el Excel oficial.")


def process_precintos_jamones(
    paths: list[Path],
    tipo_jamon: str = "Blanco",
    official_excel: Path | None = None,
) -> PrecintosJamonesResult:
    registros = leer_ficheros(paths)
    partida, lote = sugerir_partida_lote(registros)
    validos_pre: list[RegistroJamones] = []
    invalidos: list[tuple[RegistroJamones, str]] = []
    for registro in registros:
        motivos = validar_registro_completo(registro, tipo_jamon, partida, lote)
        if motivos:
            invalidos.append((registro, "; ".join(motivos)))
        else:
            validos_pre.append(registro)
    validos, duplicados = deduplicar(validos_pre)
    oficiales = set(leer_precintos_excel_oficial(official_excel)) if official_excel is not None else set()
    return PrecintosJamonesResult(list(paths), tipo_jamon, validos, invalidos, duplicados, oficiales)


def correction_text(result: PrecintosJamonesResult) -> str:
    if not result.invalidos:
        return "# Sin incidencias pendientes.\n"
    blocks = ["# Corrige las lineas de datos. Las lineas que empiezan por # se ignoran al revalidar."]
    for registro, motivo in result.invalidos:
        blocks.append(f"# Archivo: {registro.archivo} | linea: {registro.linea} | motivo: {motivo}")
        sugerencias = sugerir_precintos(registro.precinto, result.oficiales)
        if sugerencias:
            blocks.append("# Sugerencias oficiales cercanas: " + ", ".join(sugerencias))
        blocks.append(registro.a_linea())
    return "\n".join(blocks) + "\n"


def revalidate_corrections(result: PrecintosJamonesResult, text: str) -> PrecintosJamonesResult:
    corrected: list[RegistroJamones] = []
    errors: list[tuple[RegistroJamones, str]] = []
    base_order = max((registro.orden for registro in result.validos), default=0) + 100000
    partida, lote = sugerir_partida_lote(result.validos)
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        registro = parsear_linea(stripped, "CORRECCION_MANUAL", index, base_order + index)
        if registro is None:
            continue
        motivos = validar_registro_completo(registro, result.tipo_jamon, partida, lote)
        if motivos:
            errors.append((registro, "; ".join(motivos)))
        else:
            corrected.append(registro)
    validos, duplicados = deduplicar(result.validos + corrected)
    return PrecintosJamonesResult(
        selected_files=list(result.selected_files),
        tipo_jamon=result.tipo_jamon,
        validos=validos,
        invalidos=errors,
        duplicados=list(result.duplicados) + duplicados,
        oficiales=set(result.oficiales),
    )


def weight_filter_text(
    result: PrecintosJamonesResult,
    minimo_texto: str = "",
    maximo_texto: str = "",
) -> tuple[str, str, bool]:
    if result.invalidos:
        raise ValueError("Primero corrige y revalida las incidencias de precintos.")
    minimo = parsear_peso(minimo_texto) if minimo_texto.strip() else None
    maximo = parsear_peso(maximo_texto) if maximo_texto.strip() else None
    if minimo is None and maximo is None:
        raise ValueError("Introduce un peso minimo, un peso maximo o ambos.")
    if minimo_texto.strip() and minimo is None:
        raise ValueError("Peso minimo no valido. Ejemplos: 10, 10,5 o 10.5.")
    if maximo_texto.strip() and maximo is None:
        raise ValueError("Peso maximo no valido. Ejemplos: 16, 16,5 o 16.5.")
    if minimo is not None and maximo is not None and minimo > maximo:
        raise ValueError("El peso minimo no puede ser superior al peso maximo.")

    fuera: list[tuple[RegistroJamones, str]] = []
    pesos_no_validos: list[RegistroJamones] = []
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
            "# Puedes modificar estas lineas y pulsar Revalidar para sustituir el registro original por el corregido.",
            "# Las lineas que empiezan por # se ignoran al revalidar.",
        ]
        for registro, motivo in fuera:
            blocks = [f"# Archivo: {registro.archivo} | linea: {registro.linea} | motivo: {motivo}", registro.a_linea()]
            bloques.extend(blocks)
        for registro in pesos_no_validos:
            bloques.extend(
                [
                    f"# Archivo: {registro.archivo} | linea: {registro.linea} | motivo: peso no numerico o vacio",
                    registro.a_linea(),
                ]
            )
        editor = "\n".join(bloques) + "\n"

    resumen = "\n".join(
        [
            "Filtro de pesos aplicado:",
            f"- Peso minimo: {formatear_peso(minimo) if minimo is not None else '(sin minimo)'}",
            f"- Peso maximo: {formatear_peso(maximo) if maximo is not None else '(sin maximo)'}",
            f"- Registros por debajo del minimo o por encima del maximo: {len(fuera)}",
            f"- Registros con peso no numerico o vacio: {len(pesos_no_validos)}",
        ]
    )
    return editor, resumen, bool(fuera or pesos_no_validos)


def ruta_resumen_para_csv(path: Path) -> Path:
    return path.with_name(f"{path.stem}_resumen.txt")


def formato_importable_ax(codigos) -> str:
    return ",".join(str(codigo).strip() for codigo in codigos if str(codigo).strip())


def save_precintos_txt(path: Path, result: PrecintosJamonesResult) -> Path:
    if result.invalidos:
        raise ValueError("Corrige las incidencias antes de guardar.")
    text = "\r\n".join(registro.a_linea().lstrip("\ufeff") for registro in result.validos)
    path.write_text(text + ("\r\n" if text else ""), encoding="utf-8", newline="")
    return path


def resumen_text(result: PrecintosJamonesResult) -> str:
    return result.preview_text() + "\r\n"


def save_precintos_csv(path: Path, result: PrecintosJamonesResult) -> Path | None:
    if result.invalidos:
        raise ValueError("Corrige las incidencias antes de guardar.")
    if result.tipo_jamon.lower() == "iberico":
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";", lineterminator="\r\n")
            for registro in result.validos:
                writer.writerow([registro.precinto])
        summary = ruta_resumen_para_csv(path)
        summary.write_text(resumen_text(result), encoding="utf-8")
        return summary
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\r\n")
        for registro in result.validos:
            campos = list(registro.campos[:CAMPOS_ESPERADOS])
            while len(campos) < CAMPOS_ESPERADOS:
                campos.append("")
            writer.writerow(campos + [""])
    return None


def send_precintos_email(
    destinatario: str,
    result: PrecintosJamonesResult,
    attachments: list[Path],
    *,
    subject: str = ASUNTO_CORREO_DEFECTO,
    body: str = MENSAJE_CORREO_DEFECTO,
    smtp_host: str = SMTP_HOST,
    smtp_port: int = SMTP_PORT,
    smtp_user: str = SMTP_USER,
    smtp_password: str = SMTP_PASSWORD,
    smtp_starttls: bool = SMTP_SECURE,
) -> EmailMessage:
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", destinatario or ""):
        raise ValueError("Introduce una direccion de correo valida.")
    message = EmailMessage()
    message["From"] = smtp_user
    message["To"] = destinatario
    message["Subject"] = subject.format(tipo_jamon=result.tipo_jamon, registros_validos=len(result.validos))
    message.set_content(
        body.format(
            tipo_jamon=result.tipo_jamon,
            registros_validos=len(result.validos),
            incidencias=len(result.invalidos),
            duplicados=len(result.duplicados),
        )
    )
    for path in attachments:
        subtype = "csv" if path.suffix.lower() == ".csv" else "plain"
        message.add_attachment(path.read_bytes(), maintype="text", subtype=subtype, filename=path.name)
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            if smtp_starttls:
                smtp.starttls()
                smtp.ehlo()
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
    except smtplib.SMTPException as exc:
        raise RuntimeError("No se pudo enviar el correo con el servidor corporativo. Revisa la conexion o las credenciales SMTP.") from exc
    except OSError as exc:
        raise RuntimeError("No se pudo conectar con el servidor de correo corporativo. Revisa la red o la configuracion SMTP.") from exc
    return message
