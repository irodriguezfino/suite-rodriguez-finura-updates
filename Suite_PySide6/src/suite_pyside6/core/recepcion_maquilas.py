from __future__ import annotations

import csv
from functools import lru_cache
import importlib
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import re
import sys
import unicodedata

import openpyxl

from suite_pyside6.core.paths import LEGACY_SOURCE_DIR, resource_path


CAMPOS_TXT = 7
CENT = Decimal("0.01")
CONFIG_ARTICULOS_INTERNO = "config_articulos.csv"


@dataclass(frozen=True)
class RegistroMaquila:
    archivo: str
    linea: int
    partida: str
    fecha: str
    hora: str
    codigo_fac: str
    precinto: str
    lote: str
    peso: Decimal

    @property
    def fecha_hora(self) -> str:
        return " ".join(parte for parte in (self.fecha, self.hora) if parte).strip()


@dataclass(frozen=True)
class RegistroOficial:
    albaran: str
    codigo_articulo: str
    nombre_producto: str
    lote: str
    precinto: str


@dataclass(frozen=True)
class RangoArticulo:
    codigo_fac: str
    nombre_producto: str
    rango_original: str
    minimo: Decimal | None
    maximo_exclusivo: Decimal | None
    orden: int

    def contiene(self, peso: Decimal) -> bool:
        if self.minimo is not None and peso < self.minimo:
            return False
        if self.maximo_exclusivo is not None and peso >= self.maximo_exclusivo:
            return False
        return True


@dataclass(frozen=True)
class FilaRango:
    lote: str
    etiqueta_rango: str
    producto_corto: str
    piezas: int
    peso_total: Decimal
    peso_medio: Decimal
    codigo_fac: str
    producto_completo: str


@dataclass
class RecepcionResult:
    txt_file: Path | None = None
    seals_file: Path | None = None
    config_file: Path | None = None
    registros_txt: list[RegistroMaquila] = field(default_factory=list)
    registros_oficiales: list[RegistroOficial] = field(default_factory=list)
    filas_rangos: list[FilaRango] = field(default_factory=list)
    solo_txt: list[RegistroMaquila] = field(default_factory=list)
    solo_oficial: list[RegistroOficial] = field(default_factory=list)
    incidencias: list[str] = field(default_factory=list)

    @property
    def partida(self) -> str:
        return valor_mayoritario(registro.partida for registro in self.registros_txt) or "-"

    @property
    def peso_total(self) -> Decimal:
        return sum((registro.peso for registro in self.registros_txt), Decimal("0"))

    def summary_lines(self) -> list[str]:
        return [
            f"TXT: {self.txt_file.name if self.txt_file else '-'}",
            f"SealsReport: {self.seals_file.name if self.seals_file else '-'}",
            f"Partida: {self.partida}",
            f"Registros TXT: {len(self.registros_txt)}",
            f"Precintos albaran: {len(self.registros_oficiales)}",
            f"Peso TXT: {decimal_a_es(self.peso_total, 2)} kg",
            f"Fuera de albaran: {len(self.solo_txt)}",
            f"No recibidos: {len(self.solo_oficial)}",
            f"Filas de rangos: {len(self.filas_rangos)}",
            f"Avisos: {len(self.incidencias)}",
        ]

    def preview_text(self) -> str:
        if not self.registros_txt and not self.registros_oficiales:
            return "Selecciona TXT y SealsReport para empezar."
        lines = self.summary_lines()
        if self.incidencias:
            lines.append("")
            lines.append("Avisos:")
            lines.extend(f"- {item}" for item in self.incidencias[:12])
        if self.filas_rangos:
            lines.append("")
            lines.append("Rangos:")
            for fila in self.filas_rangos[:20]:
                lines.append(
                    f"- {fila.lote} | {fila.etiqueta_rango} | {fila.producto_corto} | "
                    f"{fila.piezas} piezas | {decimal_a_es(fila.peso_total, 2)} kg"
                )
        return "\n".join(lines)


def normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.strip().lower())


def normalizar_precinto(valor: str) -> str:
    return re.sub(r"\D+", "", valor or "")


def decimal_desde_texto(valor: str) -> Decimal:
    texto = (valor or "").strip().replace(".", "").replace(",", ".")
    if not texto:
        raise ValueError("peso vacio")
    try:
        return Decimal(texto)
    except InvalidOperation as exc:
        raise ValueError(f"peso no numerico: {valor}") from exc


def decimal_a_es(valor: Decimal, decimales: int = 2) -> str:
    q = Decimal("1").scaleb(-decimales)
    numero = valor.quantize(q, rounding=ROUND_HALF_UP)
    entero, _, decimal = f"{numero:f}".partition(".")
    grupos: list[str] = []
    while entero:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    return ".".join(grupos or ["0"]) + ("," + decimal if decimales else "")


def leer_texto_lineas(ruta: Path) -> list[str]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return ruta.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return ruta.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def leer_txt_maquila(ruta: Path) -> tuple[list[RegistroMaquila], list[str]]:
    registros: list[RegistroMaquila] = []
    incidencias: list[str] = []
    for numero, linea in enumerate(leer_texto_lineas(ruta), start=1):
        if not linea.strip():
            continue
        try:
            campos = next(csv.reader([linea], delimiter=";", quotechar='"'))
        except csv.Error:
            campos = linea.split(";")
        if campos and campos[-1] == "":
            campos = campos[:-1]
        if len(campos) < CAMPOS_TXT:
            incidencias.append(f"{ruta.name}:{numero} tiene {len(campos)} campos; se esperaban {CAMPOS_TXT}.")
            continue
        try:
            peso = decimal_desde_texto(campos[6])
        except ValueError as exc:
            incidencias.append(f"{ruta.name}:{numero} {exc}.")
            continue
        precinto = normalizar_precinto(campos[4])
        if not re.fullmatch(r"\d{12}", precinto):
            incidencias.append(f"{ruta.name}:{numero} precinto no valido: {campos[4]}.")
        registros.append(
            RegistroMaquila(
                archivo=ruta.name,
                linea=numero,
                partida=campos[0].strip(),
                fecha=campos[1].strip(),
                hora=campos[2].strip(),
                codigo_fac=campos[3].strip(),
                precinto=precinto,
                lote=campos[5].strip(),
                peso=peso,
            )
        )
    return registros, incidencias


def leer_seals_report(ruta: Path) -> list[RegistroOficial]:
    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    try:
        alias = {
            "albaran": "albaran",
            "codigo de articulo": "codigo_articulo",
            "nombre del producto": "nombre_producto",
            "numero de lote": "lote",
            "numero del precinto": "precinto",
        }
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            cabecera_idx = -1
            mapa: dict[str, int] = {}
            for row_index, row in enumerate(rows):
                encontrados: dict[str, int] = {}
                for col_index, value in enumerate(row):
                    clave = alias.get(normalizar_texto(str(value or "")))
                    if clave:
                        encontrados[clave] = col_index
                if {"albaran", "codigo_articulo", "nombre_producto", "lote", "precinto"}.issubset(encontrados):
                    cabecera_idx = row_index
                    mapa = encontrados
                    break
            if cabecera_idx < 0:
                continue
            registros: list[RegistroOficial] = []
            vistos: set[str] = set()
            for row in rows[cabecera_idx + 1:]:
                precinto = normalizar_precinto(str(row[mapa["precinto"]] if mapa["precinto"] < len(row) else ""))
                if not precinto or precinto in vistos:
                    continue
                vistos.add(precinto)
                registros.append(
                    RegistroOficial(
                        albaran=str(row[mapa["albaran"]] if mapa["albaran"] < len(row) else "").strip(),
                        codigo_articulo=str(row[mapa["codigo_articulo"]] if mapa["codigo_articulo"] < len(row) else "").strip(),
                        nombre_producto=str(row[mapa["nombre_producto"]] if mapa["nombre_producto"] < len(row) else "").strip(),
                        lote=str(row[mapa["lote"]] if mapa["lote"] < len(row) else "").strip(),
                        precinto=precinto,
                    )
                )
            return registros
    finally:
        wb.close()
    raise ValueError("No se encontraron las cabeceras esperadas en SealsReport.")


def extraer_rango(nombre: str) -> tuple[Decimal | None, Decimal | None, str]:
    limpio = re.sub(r"\s+W\s*$", "", nombre.strip(), flags=re.IGNORECASE)
    patron_abierto = re.search(r"([<>+])\s*(\d+(?:[,.]\d+)?)\s*$", limpio)
    if patron_abierto:
        simbolo, numero = patron_abierto.groups()
        valor = decimal_desde_texto(numero)
        if simbolo == "<":
            return None, valor, patron_abierto.group(0).strip()
        return valor, None, patron_abierto.group(0).strip()
    patron_cerrado = re.search(r"(\d+(?:[,.]\d+)?)\s*-\s*(\d+(?:[,.]\d+)?)\s*$", limpio)
    if patron_cerrado:
        minimo = decimal_desde_texto(patron_cerrado.group(1))
        maximo = decimal_desde_texto(patron_cerrado.group(2))
        return minimo, maximo, patron_cerrado.group(0).strip()
    raise ValueError(f"No se pudo detectar rango de pesos en '{nombre}'.")


def leer_config_articulos(ruta: Path) -> tuple[dict[str, list[RangoArticulo]], list[str]]:
    rangos: dict[str, list[RangoArticulo]] = defaultdict(list)
    incidencias: list[str] = []
    reader = csv.reader(leer_texto_lineas(ruta), delimiter=";")
    for index, row in enumerate(reader, start=1):
        if index == 1 and row and normalizar_texto(row[0]).startswith("codigo"):
            continue
        if len(row) < 2 or not row[0].strip() or not row[1].strip():
            continue
        codigo = row[0].strip()
        nombre = row[1].strip()
        try:
            minimo, maximo, rango_original = extraer_rango(nombre)
        except ValueError as exc:
            incidencias.append(f"{ruta.name}:{index} {exc}")
            continue
        rangos[codigo].append(RangoArticulo(codigo, nombre, rango_original, minimo, maximo, index))
    for lista in rangos.values():
        lista.sort(key=lambda item: (Decimal("-999") if item.minimo is None else item.minimo, item.orden))
    return dict(rangos), incidencias


def etiqueta_rango(rango: RangoArticulo) -> str:
    if rango.minimo is None and rango.maximo_exclusivo is not None:
        return f"< {decimal_a_es(rango.maximo_exclusivo - CENT, 2)} kg"
    if rango.maximo_exclusivo is None and rango.minimo is not None:
        return f">= {decimal_a_es(rango.minimo, 2)} kg"
    if rango.minimo is not None and rango.maximo_exclusivo is not None:
        return f"{decimal_a_es(rango.minimo, 2)} - {decimal_a_es(rango.maximo_exclusivo - CENT, 2)} kg"
    return "Sin rango"


def producto_corto(nombre: str) -> str:
    normal = normalizar_texto(nombre)
    for clave, etiqueta in (
        ("iberico", "IBERICO"),
        ("duroc", "DUROC"),
        ("serrano", "SERRANO"),
        ("paleta", "PALETA"),
        ("jamon", "JAMON"),
    ):
        if clave in normal:
            return etiqueta
    return nombre.split()[0].upper() if nombre.split() else ""


def agrupar_por_rangos(
    registros: list[RegistroMaquila],
    rangos_por_codigo: dict[str, list[RangoArticulo]],
) -> tuple[list[FilaRango], list[str]]:
    filas: list[FilaRango] = []
    incidencias: list[str] = []
    por_codigo: dict[str, list[RegistroMaquila]] = defaultdict(list)
    for registro in registros:
        por_codigo[registro.codigo_fac].append(registro)
    for codigo in sorted(por_codigo):
        rangos = rangos_por_codigo.get(codigo)
        if not rangos:
            incidencias.append(f"Sin configuracion de rangos para codigo FAC {codigo}.")
            continue
        usados: set[tuple[str, int]] = set()
        for rango in rangos:
            seleccion = [registro for registro in por_codigo[codigo] if rango.contiene(registro.peso)]
            for registro in seleccion:
                usados.add((registro.precinto, registro.linea))
            if not seleccion:
                continue
            por_lote: dict[str, list[RegistroMaquila]] = defaultdict(list)
            for registro in seleccion:
                por_lote[registro.lote or "-"].append(registro)
            for lote_txt in sorted(por_lote):
                seleccion_lote = por_lote[lote_txt]
                peso_total = sum((registro.peso for registro in seleccion_lote), Decimal("0"))
                piezas = len(seleccion_lote)
                filas.append(
                    FilaRango(
                        lote=lote_txt,
                        etiqueta_rango=etiqueta_rango(rango),
                        producto_corto=producto_corto(rango.nombre_producto),
                        piezas=piezas,
                        peso_total=peso_total,
                        peso_medio=peso_total / Decimal(piezas),
                        codigo_fac=codigo,
                        producto_completo=rango.nombre_producto,
                    )
                )
        no_asignados = [registro for registro in por_codigo[codigo] if (registro.precinto, registro.linea) not in usados]
        if no_asignados:
            incidencias.append(f"{len(no_asignados)} piezas del codigo {codigo} no encajan en ningun rango configurado.")
    return filas, incidencias


def valor_mayoritario(valores) -> str:
    conteo: dict[str, int] = defaultdict(int)
    for valor in valores:
        if valor:
            conteo[valor] += 1
    if not conteo:
        return ""
    return sorted(conteo.items(), key=lambda item: (-item[1], item[0]))[0][0]


def process_recepcion_maquilas(
    txt_file: Path,
    seals_file: Path,
    config_file: Path | None = None,
) -> RecepcionResult:
    config_file = config_file or resource_path(CONFIG_ARTICULOS_INTERNO)
    registros_txt, incidencias_txt = leer_txt_maquila(txt_file)
    if not registros_txt:
        raise ValueError("No se encontraron registros validos en el TXT.")
    registros_oficiales = leer_seals_report(seals_file)
    if not registros_oficiales:
        raise ValueError("No se encontraron precintos oficiales en SealsReport.")
    rangos, incidencias_config = leer_config_articulos(config_file)
    filas_rangos, incidencias_rangos = agrupar_por_rangos(registros_txt, rangos)
    oficiales_por_precinto = {registro.precinto: registro for registro in registros_oficiales}
    txt_por_precinto = {registro.precinto: registro for registro in registros_txt if registro.precinto}
    solo_txt = [txt_por_precinto[precinto] for precinto in sorted(set(txt_por_precinto) - set(oficiales_por_precinto))]
    solo_oficial = [oficiales_por_precinto[precinto] for precinto in sorted(set(oficiales_por_precinto) - set(txt_por_precinto))]
    return RecepcionResult(
        txt_file=txt_file,
        seals_file=seals_file,
        config_file=config_file,
        registros_txt=registros_txt,
        registros_oficiales=registros_oficiales,
        filas_rangos=filas_rangos,
        solo_txt=solo_txt,
        solo_oficial=solo_oficial,
        incidencias=incidencias_txt + incidencias_config + incidencias_rangos,
    )


class SimplePdf:
    def __init__(self, title: str) -> None:
        self.title = title
        self.lines: list[str] = []

    def add(self, text: str = "") -> None:
        self.lines.append(str(text))

    def save(self, path: Path) -> None:
        content = ["BT /F1 11 Tf 50 790 Td"]
        first = True
        for line in self.lines[:58]:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if first:
                content.append(f"({escaped}) Tj")
                first = False
            else:
                content.append(f"0 -14 Td ({escaped}) Tj")
        content.append("ET")
        stream = "\n".join(content).encode("cp1252", errors="replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{index} 0 obj\n".encode("ascii"))
            output.extend(obj)
            output.extend(b"\nendobj\n")
        xref = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
        path.write_bytes(bytes(output))


def generar_pdf_diferencias(path: Path, result: RecepcionResult) -> None:
    legacy = _legacy_recepcion_module()
    if legacy is not None:
        legacy.generar_pdf_diferencias(path, result.registros_txt, result.registros_oficiales, result.incidencias)
        return
    pdf = SimplePdf(f"Informe diferencias {result.partida}")
    pdf.add(f"Informe diferencias {result.partida}")
    pdf.add("")
    for line in result.summary_lines():
        pdf.add(line)
    pdf.add("")
    pdf.add("Recibidos fuera de albaran")
    for registro in result.solo_txt[:18]:
        pdf.add(f"{registro.precinto} | {registro.codigo_fac} | {registro.lote} | {decimal_a_es(registro.peso, 2)} kg")
    pdf.add("")
    pdf.add("No recibidos del albaran")
    for registro in result.solo_oficial[:18]:
        pdf.add(f"{registro.precinto} | {registro.albaran} | {registro.codigo_articulo} | {registro.lote}")
    pdf.save(path)


def generar_pdf_rangos(path: Path, result: RecepcionResult, metadata: dict[str, str] | None = None) -> None:
    metadata = metadata or {}
    legacy = _legacy_recepcion_module()
    if legacy is not None:
        legacy.generar_pdf_rangos(
            path,
            result.filas_rangos,
            result.registros_txt,
            result.registros_oficiales,
            metadata,
            result.incidencias,
        )
        return
    pdf = SimplePdf(f"Recepcion Maquilas {result.partida}")
    pdf.add(f"Recepcion Maquilas {result.partida}")
    pdf.add("")
    pdf.add(f"Ganadero: {metadata.get('ganadero') or 'EMBUTIDOS RODRIGUEZ'}")
    pdf.add(f"Origen: {metadata.get('origen') or 'Espana'}")
    pdf.add(f"Peso total: {decimal_a_es(result.peso_total, 2)} kg")
    pdf.add("")
    pdf.add("Clasificacion por rangos")
    for fila in result.filas_rangos[:36]:
        pdf.add(
            f"{fila.lote} | {fila.etiqueta_rango} | {fila.producto_corto} | "
            f"{fila.piezas} | {decimal_a_es(fila.peso_total, 2)} kg | {decimal_a_es(fila.peso_medio, 2)} kg"
        )
    if result.incidencias:
        pdf.add("")
        pdf.add("Avisos")
        for incidencia in result.incidencias[:8]:
            pdf.add(incidencia)
    pdf.save(path)


@lru_cache(maxsize=1)
def _legacy_recepcion_module():
    try:
        legacy_dir = str(LEGACY_SOURCE_DIR)
        if legacy_dir not in sys.path:
            sys.path.insert(0, legacy_dir)
        return importlib.import_module("RecepcionMaquilasGUI")
    except Exception:
        return None
