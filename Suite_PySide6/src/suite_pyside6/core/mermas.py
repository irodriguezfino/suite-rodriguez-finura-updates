from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd


FilterMode = Literal["SI", "NO", "TODOS"]


BASE_COLUMNS = [
    "Fichero FAC",
    "Fecha",
    "Hora",
    "Precinto",
    "Peso Origen",
    "Peso Final",
    "Merma",
    "Cumple",
]


@dataclass
class MermasSummary:
    archivos_cargados: int = 0
    filas_leidas: int = 0
    precintos_unicos: int = 0
    duplicados_detectados: int = 0
    total_piezas_si: int = 0
    total_piezas_no: int = 0
    piezas_resultado_final: int = 0
    lotes_origen_vacios: int = 0
    lotes_origen_informados: int = 0

    def lines(self) -> list[str]:
        return [
            f"Archivos cargados: {self.archivos_cargados}",
            f"Filas leidas: {self.filas_leidas}",
            f"Precintos unicos: {self.precintos_unicos}",
            f"Duplicados detectados: {self.duplicados_detectados}",
            f"Total piezas SI: {self.total_piezas_si}",
            f"Total piezas NO: {self.total_piezas_no}",
            f"Piezas resultado final: {self.piezas_resultado_final}",
            f"Lotes origen informados: {self.lotes_origen_informados}",
            f"Lotes origen vacios: {self.lotes_origen_vacios}",
        ]


@dataclass
class MermasResult:
    final_files: list[Path] = field(default_factory=list)
    origin_file: Path | None = None
    filter_mode: FilterMode = "SI"
    dataframe: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: MermasSummary = field(default_factory=MermasSummary)

    def preview_text(self, limit: int = 100) -> str:
        if self.dataframe.empty:
            return "No hay resultados para mostrar."
        return self.dataframe.head(limit).to_string(index=False)


def clean_valid_lines(path: Path) -> list[str]:
    lines: list[str] = []
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            if text.replace(";", "") == "":
                continue
            if "\ufffd" in text:
                raise ValueError(f"El archivo contiene caracteres no legibles en la linea: {text[:120]}")
            lines.append(text)
    return lines


def normalize_time(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    parts = text.split(":")
    if len(parts) != 3:
        return text
    try:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    except Exception:
        return text


def normalize_date(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def _read_final_files(paths: list[Path]) -> pd.DataFrame:
    rows: list[list[str]] = []
    for path in paths:
        for line in clean_valid_lines(path):
            try:
                columns = next(csv.reader([line], delimiter=";", quotechar='"'))
            except csv.Error:
                columns = line.split(";")
            rows.append(columns)
    if not rows:
        raise ValueError("No hay datos validos en los ficheros finales.")
    max_columns = max(len(row) for row in rows)
    normalized = [row + [""] * (max_columns - len(row)) for row in rows]
    if max_columns <= len(BASE_COLUMNS):
        columns = BASE_COLUMNS[:max_columns]
    else:
        columns = BASE_COLUMNS + [f"Columna_{index + 1}" for index in range(len(BASE_COLUMNS), max_columns)]
    return pd.DataFrame(normalized, columns=columns)


def _read_origin(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, sep=";", header=None, dtype=str, encoding="utf-8", engine="python")
    return pd.read_excel(path, header=None, dtype=str)


def process_mermas(final_files: list[Path], origin_file: Path, filter_mode: FilterMode = "SI") -> MermasResult:
    df_final = _read_final_files(final_files)
    df_base = df_final.copy()
    filas_leidas = len(df_final)

    if "Fecha" in df_final.columns:
        df_final["Fecha"] = df_final["Fecha"].apply(normalize_date)
        df_base["Fecha"] = df_base["Fecha"].apply(normalize_date)
    if "Hora" in df_final.columns:
        df_final["Hora"] = df_final["Hora"].apply(normalize_time)
        df_base["Hora"] = df_base["Hora"].apply(normalize_time)
    for column in ["Peso Origen", "Peso Final", "Merma"]:
        if column in df_final.columns:
            df_final[column] = df_final[column].astype(str).str.replace(".", ",", regex=False)
            df_base[column] = df_base[column].astype(str).str.replace(".", ",", regex=False)

    if "Precinto" not in df_final.columns:
        raise ValueError("No se ha encontrado la columna 'Precinto' en los ficheros finales.")

    df_base["Precinto"] = df_base["Precinto"].astype(str).str.strip()
    precintos_unicos = int(df_base["Precinto"].nunique())
    duplicados_detectados = int(filas_leidas - precintos_unicos)

    df_final["Precinto"] = df_final["Precinto"].astype(str).str.strip()
    df_final = df_final.drop_duplicates(subset=["Precinto"], keep="last").copy()

    total_piezas_si = 0
    total_piezas_no = 0
    if "Cumple" in df_final.columns:
        cumple = df_final["Cumple"].astype(str).str.strip().str.upper()
        total_piezas_si = int(cumple.eq("SI").sum())
        total_piezas_no = int(cumple.eq("NO").sum())
        if filter_mode in ("SI", "NO"):
            df_final = df_final[cumple.eq(filter_mode)].copy()

    df_origin = _read_origin(origin_file).fillna("")
    if df_origin.shape[1] < 6:
        raise ValueError("El fichero origen no tiene al menos 6 columnas.")

    origin_map = (
        df_origin.iloc[:, [4, 5]]
        .astype(str)
        .apply(lambda col: col.str.strip())
        .drop_duplicates(subset=df_origin.columns[4], keep="first")
        .set_index(df_origin.columns[4])[df_origin.columns[5]]
        .to_dict()
    )
    df_final = df_final.fillna("")
    df_final["LOTE ORIGEN"] = df_final["Precinto"].astype(str).str.strip().map(lambda value: origin_map.get(value, ""))

    lotes_vacios = int(df_final["LOTE ORIGEN"].astype(str).str.strip().eq("").sum())
    lotes_informados = int(len(df_final) - lotes_vacios)
    summary = MermasSummary(
        archivos_cargados=len(final_files),
        filas_leidas=filas_leidas,
        precintos_unicos=precintos_unicos,
        duplicados_detectados=duplicados_detectados,
        total_piezas_si=total_piezas_si,
        total_piezas_no=total_piezas_no,
        piezas_resultado_final=len(df_final),
        lotes_origen_vacios=lotes_vacios,
        lotes_origen_informados=lotes_informados,
    )
    return MermasResult(list(final_files), origin_file, filter_mode, df_final, summary)


def save_mermas_excel(path: Path, result: MermasResult) -> None:
    df_export = result.dataframe.copy()
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Resultado")
        ws = writer.sheets["Resultado"]
        ws.freeze_panes = "A2"
        for column_index, column_name in enumerate(df_export.columns, start=1):
            max_len = len(str(column_name))
            for row_index in range(2, min(len(df_export) + 2, 300)):
                value = ws.cell(row=row_index, column=column_index).value
                if value is not None:
                    max_len = max(max_len, len(str(value)))
            ws.column_dimensions[ws.cell(row=1, column=column_index).column_letter].width = min(max_len + 2, 22)

        start_column = len(df_export.columns) + 3
        ws.cell(row=2, column=start_column, value="RESUMEN")
        for offset, line in enumerate(result.summary.lines(), start=3):
            label, _, value = line.partition(": ")
            ws.cell(row=offset, column=start_column, value=label)
            ws.cell(row=offset, column=start_column + 1, value=value)

