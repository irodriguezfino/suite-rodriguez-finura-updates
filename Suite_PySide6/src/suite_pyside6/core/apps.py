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
        description="Valida códigos de pallet de PDA, permite correcciones y genera Stock01.csv.",
        short_description="Valida palets y Stock01.csv.",
        category="Palets y PDA",
        shortcut="Alt+3",
        migration_status="ported",
    ),
    AppDefinition(
        key="precintos_jamones",
        title="Precintos Jamones",
        description="Valida precintos, GTIN-12 para ibérico, duplicados, oficial y correo.",
        short_description="Valida precintos y TXT/CSV.",
        category="Jamones",
        shortcut="Alt+4",
        migration_status="ported",
    ),
    AppDefinition(
        key="precintos_expedicion",
        title="Precintos Expedición",
        description="Genera el TXT de expedición de jamones desde Excel de entrada y salida de AX.",
        short_description="Excel entrada/salida a TXT AX.",
        category="Jamones",
        shortcut="Alt+5",
        migration_status="ported",
    ),
    AppDefinition(
        key="exportar_precintos_excel",
        title="Precintos Excel a CSV",
        description="Extrae la columna Identificación de Excel y genera .csv.",
        short_description="Identificaciones Excel a CSV.",
        category="Excel / CSV",
        shortcut="Alt+6",
        migration_status="ported",
    ),
    AppDefinition(
        key="control_recepcion_precintos",
        title="Control y Recepción Precintos",
        description="Corrige TXT de precintos, genera rangos y envía correo final con adjuntos.",
        short_description="TXT AX, rangos y correo.",
        category="Jamones",
        shortcut="Alt+8",
        migration_status="ported",
    ),
    AppDefinition(
        key="precintos_txt_ax",
        title="Precintos TXT a CSV AX",
        description="Extrae los precintos a la derecha de -> y genera un CSV de una columna para AX.",
        short_description="TXT de flechas a CSV AX.",
        category="Excel / CSV",
        shortcut="Alt+P",
        migration_status="ported",
    ),
    AppDefinition(
        key="pesos",
        title="Pesos",
        description="Renombra la primera hoja visible de varios Excel a Hoja1 sin cambiar datos.",
        short_description="Excel de pesos con hoja Hoja1.",
        category="Pesos",
        shortcut="Alt+9",
        migration_status="ported",
    ),
    AppDefinition(
        key="reparto_merma_precintos",
        title="Precintos Deshuesado",
        description="Elige PDA para repartir la merma o FAC para consolidar CSV de deshuesado en AX.",
        short_description="PDA/FAC a CSV AX.",
        category="Pesos",
        shortcut="Alt+0",
        migration_status="ported",
    ),
)


# Las claves antiguas quedan resueltas para favoritos, historial y accesos
# programáticos guardados en versiones previas. No se publican como apps.
APP_KEY_ALIASES: dict[str, str] = {
    "control_recepcion_maquilas": "control_recepcion_precintos",
    "recepcion_maquilas": "control_recepcion_precintos",
}


def resolve_app_key(key: str) -> str:
    return APP_KEY_ALIASES.get(key, key)


def app_by_key(key: str) -> AppDefinition:
    key = resolve_app_key(key)
    for app in APP_REGISTRY:
        if app.key == key:
            return app
    raise KeyError(f"Aplicación no registrada: {key}")


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
