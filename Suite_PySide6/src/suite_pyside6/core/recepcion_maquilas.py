from __future__ import annotations

import csv
from functools import lru_cache
import importlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
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
A4_PORTRAIT = (595.0, 842.0)
PDF_COLOR_RESET = "0 0 0 rg"
PDF_COLOR_HEADER_BG = "0.94 0.96 0.98 rg"
PDF_COLOR_HEADER_DARK = "0.17 0.22 0.28 rg"
PDF_COLOR_TEXT_DARK = "0.08 0.10 0.13 rg"
PDF_COLOR_TEXT_MUTED = "0.32 0.36 0.41 rg"
PDF_COLOR_TABLE_ALT = "0.96 0.97 0.98 rg"
PDF_COLOR_WHITE = "1 1 1 rg"


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


def unir_valores_unicos(valores) -> str:
    vistos: set[str] = set()
    resultado: list[str] = []
    for valor in valores:
        texto = str(valor or "").strip()
        if texto and texto not in vistos:
            vistos.add(texto)
            resultado.append(texto)
    return ", ".join(resultado)


def formatear_fecha_recepcion(valor: str) -> str:
    texto = str(valor or "").strip()
    if re.fullmatch(r"\d{6}", texto):
        return f"{texto[:2]}/{texto[2:4]}/20{texto[4:]}"
    return texto


def tiene_certificado_welfair(registros: list[RegistroOficial]) -> bool:
    return any((registro.lote or "").strip().upper().endswith("W") for registro in registros)


def resumen_lotes_origen(registros_oficiales: list[RegistroOficial]) -> list[list[str]]:
    conteo: dict[str, int] = defaultdict(int)
    for registro in registros_oficiales:
        lote = registro.lote.strip() if registro.lote else "Sin lote"
        conteo[lote] += 1
    return [[lote, str(piezas)] for lote, piezas in sorted(conteo.items())]


def lotes_origen_en_columnas(lotes_origen: list[list[str]], grupos: int = 3) -> list[list[str]]:
    if not lotes_origen:
        return []
    alto = (len(lotes_origen) + grupos - 1) // grupos
    filas: list[list[str]] = []
    for i in range(alto):
        fila: list[str] = []
        for grupo in range(grupos):
            idx = i + grupo * alto
            if idx < len(lotes_origen):
                fila.extend(lotes_origen[idx])
            else:
                fila.extend(["", ""])
        filas.append(fila)
    return filas


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


class PdfSimple:
    def __init__(self, titulo: str) -> None:
        self.titulo = titulo
        self.ancho, self.alto = A4_PORTRAIT
        self.paginas: list[list[str]] = []
        self.nueva_pagina()

    def nueva_pagina(self) -> None:
        self.paginas.append([])

    @property
    def contenido(self) -> list[str]:
        return self.paginas[-1]

    def y(self, y_top: float) -> float:
        return self.alto - y_top

    def texto(self, x: float, y_top: float, texto: str, size: int = 9, bold: bool = False, color: str | None = None) -> None:
        fuente = "F2" if bold else "F1"
        if color:
            self.contenido.append(color)
        self.contenido.append(f"BT /{fuente} {size} Tf {x:.2f} {self.y(y_top):.2f} Td ({self._esc(texto)}) Tj ET")
        if color:
            self.contenido.append(PDF_COLOR_RESET)

    def linea(self, x1: float, y1_top: float, x2: float, y2_top: float, ancho: float = 0.6) -> None:
        self.contenido.append(f"{ancho:.2f} w {x1:.2f} {self.y(y1_top):.2f} m {x2:.2f} {self.y(y2_top):.2f} l S")

    def rect(self, x: float, y_top: float, w: float, h: float, fill: str | None = None, stroke: bool = True) -> None:
        op = "B" if fill and stroke else ("f" if fill else "S")
        if fill:
            self.contenido.append(fill)
        self.contenido.append(f"{x:.2f} {self.y(y_top + h):.2f} {w:.2f} {h:.2f} re {op}")
        if fill:
            self.contenido.append(PDF_COLOR_RESET)

    def wrap(self, texto: str, ancho: float, size: int) -> list[str]:
        max_chars = max(8, int(ancho / (size * 0.48)))
        palabras = str(texto or "").split()
        if not palabras:
            return [""]
        palabras_partidas: list[str] = []
        for palabra in palabras:
            if len(palabra) <= max_chars:
                palabras_partidas.append(palabra)
            else:
                for i in range(0, len(palabra), max_chars):
                    palabras_partidas.append(palabra[i : i + max_chars])
        lineas: list[str] = []
        actual = ""
        for palabra in palabras_partidas:
            candidato = palabra if not actual else f"{actual} {palabra}"
            if len(candidato) <= max_chars:
                actual = candidato
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        if actual:
            lineas.append(actual)
        return lineas

    def tabla(
        self,
        x: float,
        y_top: float,
        columnas: list[tuple[str, float, str]],
        filas: list[list[str]],
        *,
        size: int = 8,
        header_size: int = 8,
        margen_inferior: float = 44,
        repetir_cabecera: bool = True,
        titulo_continuacion: str | None = None,
    ) -> float:
        y = y_top
        ancho_total = sum(col[1] for col in columnas)

        def cabecera(y_actual: float) -> float:
            self.rect(x, y_actual, ancho_total, 21, fill=PDF_COLOR_HEADER_DARK)
            cx = x
            for titulo, ancho, _align in columnas:
                self.texto(cx + 4, y_actual + 13, titulo, header_size, True, PDF_COLOR_WHITE)
                cx += ancho
            return y_actual + 21

        if y + 24 > self.alto - margen_inferior:
            self.nueva_pagina()
            if titulo_continuacion:
                dibujar_cabecera(self, titulo_continuacion, "Continuacion")
                y = 96
            else:
                y = 34
        y = cabecera(y)
        if not filas:
            filas = [["Sin datos"] + [""] * (len(columnas) - 1)]
        for idx, fila in enumerate(filas):
            lineas_por_col = [self.wrap(fila[i] if i < len(fila) else "", columnas[i][1] - 8, size) for i in range(len(columnas))]
            alto = max(18, 9 + max(len(l) for l in lineas_por_col) * (size + 2))
            if y + alto > self.alto - margen_inferior:
                self.nueva_pagina()
                if titulo_continuacion:
                    dibujar_cabecera(self, titulo_continuacion, "Continuacion")
                    y = 96
                else:
                    y = 34
                if repetir_cabecera:
                    y = cabecera(y)
            if idx % 2 == 1:
                self.rect(x, y, ancho_total, alto, fill=PDF_COLOR_TABLE_ALT, stroke=False)
            cx = x
            for i, (_titulo, ancho, align) in enumerate(columnas):
                self.linea(cx, y, cx, y + alto, 0.25)
                texto_lineas = lineas_por_col[i]
                for j, linea in enumerate(texto_lineas):
                    tx = cx + 4
                    if align == "right":
                        tx = cx + ancho - 4 - min(len(linea) * size * 0.46, ancho - 8)
                    self.texto(tx, y + 12 + j * (size + 2), linea, size)
                cx += ancho
            self.linea(x + ancho_total, y, x + ancho_total, y + alto, 0.25)
            self.linea(x, y + alto, x + ancho_total, y + alto, 0.25)
            y += alto
        return y

    def bloque_info(self, x: float, y_top: float, columnas: list[tuple[str, str]], ancho: float = 539, titulo_continuacion: str | None = None) -> float:
        filas = [[etiqueta, valor] for etiqueta, valor in columnas]
        return self.tabla(
            x,
            y_top,
            [("Dato", 118, "left"), ("Valor", ancho - 118, "left")],
            filas,
            size=8,
            header_size=8,
            repetir_cabecera=False,
            titulo_continuacion=titulo_continuacion,
        )

    def guardar(self, ruta: Path) -> None:
        objetos: list[bytes] = []

        def add(contenido: bytes) -> int:
            objetos.append(contenido)
            return len(objetos)

        catalog_id = add(b"")
        pages_id = add(b"")
        font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        bold_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        page_ids = []
        for pagina in self.paginas:
            stream = "\n".join(pagina).encode("cp1252", errors="replace")
            content_id = add(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
            page = (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {self.ancho:.0f} {self.alto:.0f}] "
                f"/Resources << /Font << /F1 {font_id} 0 R /F2 {bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
            page_ids.append(add(page))
        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objetos[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
        objetos[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")
        salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, obj in enumerate(objetos, start=1):
            offsets.append(len(salida))
            salida.extend(f"{i} 0 obj\n".encode("ascii"))
            salida.extend(obj)
            salida.extend(b"\nendobj\n")
        xref = len(salida)
        salida.extend(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets[1:]:
            salida.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        salida.extend(
            f"trailer << /Size {len(objetos) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
        )
        ruta.write_bytes(bytes(salida))

    @staticmethod
    def _esc(texto: str) -> str:
        return str(texto or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def dibujar_cabecera(pdf: PdfSimple, titulo: str, subtitulo: str = "") -> None:
    pdf.rect(0, 0, pdf.ancho, 82, fill=PDF_COLOR_HEADER_BG, stroke=False)
    pdf.rect(28, 26, 4, 34, fill=PDF_COLOR_HEADER_DARK, stroke=False)
    pdf.texto(40, 30, "EMBUTIDOS RODRIGUEZ", 8, True, PDF_COLOR_HEADER_DARK)
    pdf.texto(40, 49, titulo, 15, True, PDF_COLOR_TEXT_DARK)
    if subtitulo:
        pdf.texto(40, 66, subtitulo, 9, False, PDF_COLOR_TEXT_MUTED)
    pdf.texto(pdf.ancho - 150, 30, datetime.now().strftime("%d/%m/%Y %H:%M"), 8, False, PDF_COLOR_TEXT_MUTED)


def asegurar_espacio(pdf: PdfSimple, y: float, alto: float, titulo: str, subtitulo: str = "Continuacion") -> float:
    if y + alto <= pdf.alto - 44:
        return y
    pdf.nueva_pagina()
    dibujar_cabecera(pdf, titulo, subtitulo)
    return 96


def titulo_seccion(pdf: PdfSimple, y: float, texto: str, titulo_doc: str) -> float:
    y = asegurar_espacio(pdf, y, 26, titulo_doc)
    pdf.texto(28, y, texto, 10, True, PDF_COLOR_HEADER_DARK)
    pdf.linea(28, y + 5, pdf.ancho - 28, y + 5, 0.45)
    return y + 13


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
    _generar_pdf_rangos_profesional(
        path,
        result.filas_rangos,
        result.registros_txt,
        result.registros_oficiales,
        metadata,
        result.incidencias,
    )


def _generar_pdf_rangos_profesional(
    ruta: Path,
    filas: list[FilaRango],
    registros_txt: list[RegistroMaquila],
    registros_oficiales: list[RegistroOficial],
    metadatos: dict[str, str],
    incidencias: list[str],
) -> None:
    partida = valor_mayoritario(r.partida for r in registros_txt) or "-"
    codigo = valor_mayoritario(r.codigo_fac for r in registros_txt)
    lote_txt = valor_mayoritario(r.lote for r in registros_txt)
    fecha_recepcion = unir_valores_unicos(formatear_fecha_recepcion(r.fecha) for r in registros_txt)
    albaran = unir_valores_unicos(r.albaran for r in registros_oficiales)
    lotes_origen = resumen_lotes_origen(registros_oficiales)
    peso_total = sum((fila.peso_total for fila in filas), Decimal("0"))
    piezas_total = sum(fila.piezas for fila in filas)
    medio = peso_total / Decimal(piezas_total) if piezas_total else Decimal("0")

    titulo_doc = f"Recepcion Maquilas {partida}"
    pdf = PdfSimple(titulo_doc)
    dibujar_cabecera(pdf, titulo_doc, "Clasificacion por rangos de peso")
    y = titulo_seccion(pdf, 96, "Datos del informe", titulo_doc)
    info = [
        ("Ganadero", metadatos.get("ganadero") or "EMBUTIDOS RODRIGUEZ"),
        ("Partida", partida),
        ("Albaran", albaran),
        ("Codigo FAC", codigo),
        ("Lote", lote_txt),
        ("Fecha recepcion", fecha_recepcion),
        ("Origen", metadatos.get("origen") or "Espana"),
    ]
    if tiene_certificado_welfair(registros_oficiales):
        info.append(("Certificado Welfair", "Si"))
    if metadatos.get("dac"):
        info.append(("N DAC", metadatos["dac"]))
    if metadatos.get("contrato"):
        info.append(("Contrato", metadatos["contrato"]))
    if metadatos.get("control_temperatura"):
        info.append(("Control de temperatura", metadatos["control_temperatura"]))
    if metadatos.get("ph"):
        info.append(("PH", metadatos["ph"]))
    if metadatos.get("observaciones"):
        info.append(("Observaciones", metadatos["observaciones"]))
    info.append(("Especificacion", metadatos.get("especificacion") or ""))
    y = pdf.bloque_info(28, y, info, 539, titulo_doc)
    y += 16

    y = titulo_seccion(pdf, y, "Lotes origen albaran", titulo_doc)
    y = pdf.tabla(
        28,
        y,
        [
            ("Lote origen", 112, "left"),
            ("Piezas", 56, "right"),
            ("Lote origen", 112, "left"),
            ("Piezas", 56, "right"),
            ("Lote origen", 112, "left"),
            ("Piezas", 91, "right"),
        ],
        lotes_origen_en_columnas(lotes_origen),
        size=8,
        titulo_continuacion=titulo_doc,
    )
    y += 16

    if incidencias:
        y = titulo_seccion(pdf, y, "Avisos", titulo_doc)
        filas_avisos = [[incidencia] for incidencia in incidencias[:8]]
        if len(incidencias) > 8:
            filas_avisos.append([f"... y {len(incidencias) - 8} avisos mas"])
        y = pdf.tabla(28, y, [("Aviso", 539, "left")], filas_avisos, size=8, titulo_continuacion=titulo_doc)
        y += 16

    filas_tabla = [
        [
            fila.lote,
            fila.etiqueta_rango,
            fila.producto_corto,
            str(fila.piezas),
            decimal_a_es(fila.peso_total, 2),
            decimal_a_es(fila.peso_medio, 2),
        ]
        for fila in filas
    ]
    y = titulo_seccion(pdf, y, "Clasificacion por rangos", titulo_doc)
    y = pdf.tabla(
        28,
        y,
        [
            ("Lote", 112, "left"),
            ("Rango", 112, "left"),
            ("Producto", 70, "left"),
            ("Piezas", 65, "right"),
            ("Peso", 90, "right"),
            ("Peso medio", 90, "right"),
        ],
        filas_tabla,
        size=8,
        titulo_continuacion=titulo_doc,
    )
    if y + 28 > pdf.alto - 40:
        pdf.nueva_pagina()
        dibujar_cabecera(pdf, titulo_doc, "Continuacion")
        y = 96
    pdf.rect(28, y + 6, 539, 24, fill=PDF_COLOR_HEADER_DARK, stroke=False)
    pdf.texto(38, y + 21, f"Total piezas: {piezas_total}", 9, True, PDF_COLOR_WHITE)
    pdf.texto(200, y + 21, f"Peso total: {decimal_a_es(peso_total, 2)} kg", 9, True, PDF_COLOR_WHITE)
    pdf.texto(392, y + 21, f"Peso medio: {decimal_a_es(medio, 2)} kg", 9, True, PDF_COLOR_WHITE)
    pdf.guardar(ruta)


@lru_cache(maxsize=1)
def _legacy_recepcion_module():
    try:
        legacy_dir = str(LEGACY_SOURCE_DIR)
        if legacy_dir not in sys.path:
            sys.path.insert(0, legacy_dir)
        return importlib.import_module("RecepcionMaquilasGUI")
    except Exception:
        return None
