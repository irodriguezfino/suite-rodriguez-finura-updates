from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppDefinition:
    key: str
    title: str
    description: str
    short_description: str
    category: str
    shortcut: str
    migration_status: str = "pending"


APP_REGISTRY: tuple[AppDefinition, ...] = (
    AppDefinition(
        key="mermas",
        title="Merma Jamones FAC",
        description="Cruza CSV finales con fichero origen y genera el Excel de resultado.",
        short_description="CSV origen a Excel.",
        category="Jamones",
        shortcut="Alt+1",
        migration_status="ported",
    ),
    AppDefinition(
        key="txt_csv",
        title="Procesador TXT a CSV",
        description="Carga TXT, normaliza decimales y guarda el CSV final.",
        short_description="TXT normalizado a CSV.",
        category="Excel / CSV",
        shortcut="Alt+2",
        migration_status="ported",
    ),
    AppDefinition(
        key="palets",
        title="Palets PDA",
        description="Valida codigos de pallet de PDA, permite correcciones y genera Stock01.csv.",
        short_description="Valida palets y Stock01.csv.",
        category="Palets y PDA",
        shortcut="Alt+3",
        migration_status="ported",
    ),
    AppDefinition(
        key="precintos_jamones",
        title="Precintos Jamones",
        description="Valida precintos, GTIN-12 para iberico, duplicados, oficial y correo.",
        short_description="Valida precintos y TXT/CSV.",
        category="Jamones",
        shortcut="Alt+4",
        migration_status="ported",
    ),
    AppDefinition(
        key="precintos_expedicion",
        title="Precintos Expedicion",
        description="Genera el TXT de expedicion de jamones desde Excel de entrada y salida de AX.",
        short_description="Excel entrada/salida a TXT AX.",
        category="Jamones",
        shortcut="Alt+5",
        migration_status="ported",
    ),
    AppDefinition(
        key="exportar_precintos_excel",
        title="Precintos Excel a CSV",
        description="Extrae la columna Identificacion de Excel y genera .csv.",
        short_description="Identificaciones Excel a CSV.",
        category="Excel / CSV",
        shortcut="Alt+6",
        migration_status="ported",
    ),
    AppDefinition(
        key="recepcion_maquilas",
        title="Recepcion Maquilas",
        description="Compara TXT recibido con SealsReport y genera PDFs de diferencias y rangos.",
        short_description="TXT, SealsReport y rangos PDF.",
        category="Jamones",
        shortcut="Alt+7",
        migration_status="ported",
    ),
    AppDefinition(
        key="control_recepcion_maquilas",
        title="Control y Recepcion Maquilas",
        description="Corrige TXT de precintos, genera rangos y envia correo final con adjuntos.",
        short_description="TXT AX, rangos y correo.",
        category="Jamones",
        shortcut="Alt+8",
        migration_status="ported",
    ),
)


def app_by_key(key: str) -> AppDefinition:
    for app in APP_REGISTRY:
        if app.key == key:
            return app
    raise KeyError(f"Aplicacion no registrada: {key}")


def categories() -> tuple[str, ...]:
    result = ["Todas"]
    for app in APP_REGISTRY:
        if app.category not in result:
            result.append(app.category)
    return tuple(result)


def apps_for_category(category: str) -> tuple[AppDefinition, ...]:
    if category == "Todas":
        return APP_REGISTRY
    return tuple(app for app in APP_REGISTRY if app.category == category)
