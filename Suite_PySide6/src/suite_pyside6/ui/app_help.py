from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from suite_pyside6.core.apps import AppDefinition


@dataclass(frozen=True)
class AppHelp:
    purpose: str
    benefit: str
    input_hint: str
    steps: tuple[str, ...]
    output_hint: str
    tip: str


# The copy deliberately uses the same names as the controls in each window.
# It is a short operational guide, not a replacement for the working screens.
APP_HELP: dict[str, AppHelp] = {
    "mermas": AppHelp(
        "Cruza los CSV finales de jamones con el fichero de origen para calcular y revisar la merma.",
        "Sirve para detectar el cumplimiento de cada registro y obtener un Excel listo para revisar o compartir.",
        "Ten a mano uno o varios CSV finales y el CSV de origen correspondiente.",
        ("Carga los CSVs finales.", "Carga el fichero de origen.", "Pulsa Procesar cruce y revisa la tabla.", "Guarda el Excel cuando el resultado sea correcto."),
        "Un Excel con el cruce y el estado de merma.",
        "Si falta información, vuelve a cargar el archivo de origen antes de guardar.",
    ),
    "txt_csv": AppHelp(
        "Convierte archivos TXT operativos en un CSV uniforme.",
        "Sirve para preparar datos de texto para Excel, AX u otras importaciones sin ajustar decimales a mano.",
        "Selecciona uno o varios TXT con registros separados por punto y coma.",
        ("Carga los TXT.", "Pulsa Procesar archivos.", "Comprueba la vista previa y los avisos.", "Guarda el CSV final."),
        "Un único CSV con los decimales normalizados.",
        "Las líneas vacías se ignoran; revisa los archivos que aparezcan como error.",
    ),
    "palets": AppHelp(
        "Valida lecturas de palets tomadas con PDA y prepara Stock01.csv.",
        "Evita importar códigos incompletos, corrige incidencias y elimina duplicados de forma segura.",
        "Carga los TXT procedentes de la PDA.",
        ("Carga los TXT.", "Pulsa Procesar palets.", "Corrige solo las lecturas señaladas y pulsa Revalidar.", "Guarda Stock01.csv cuando no queden incidencias."),
        "Stock01.csv con códigos de palet aceptados y sin duplicados.",
        "Un código válido tiene 20 dígitos, empieza por 00 y se guarda sin ese prefijo.",
    ),
    "precintos_jamones": AppHelp(
        "Controla los precintos de jamón y detecta errores, duplicados y diferencias con el listado oficial.",
        "Sirve para depurar un lote antes de generar los ficheros de trabajo o importación.",
        "Carga el TXT o CSV de lecturas; el Excel oficial es opcional, pero recomendable para contrastar.",
        ("Carga TXT/CSV y, si aplica, el Excel oficial.", "Pulsa Procesar control.", "Corrige incidencias, usa Filtrar pesos si hace falta y Revalidar.", "Guarda TXT o CSV al quedar el lote validado."),
        "TXT depurado y/o CSV compatible con AX, más un resumen de control.",
        "No se puede generar CSV de un lote mixto: revisa el tipo de jamón indicado por cada fila.",
    ),
    "precintos_expedicion": AppHelp(
        "Genera los TXT de expedición para AX a partir de Excel de entrada y de salida.",
        "Sirve para asignar los precintos y kilos de los pallets correctos a cada expedición.",
        "Añade el Excel de entrada y uno o varios Excel de salida; la aplicación los identifica por sus columnas.",
        ("Carga todos los Excel.", "Marca los pallets de entrada o usa Sugerir pallets.", "Pulsa Comprobar salida y revisa cada destino.", "Guarda los TXT cuando todas las salidas estén correctas."),
        "Un TXT por Excel de salida, preparado para AX.",
        "La sugerencia de pallets agiliza el trabajo, pero confirma siempre la selección antes de guardar.",
    ),
    "exportar_precintos_excel": AppHelp(
        "Extrae los valores de la columna Identificación de los Excel de trazabilidad.",
        "Sirve para crear rápidamente un CSV de precintos que Dynamics puede importar.",
        "Selecciona uno o varios archivos Excel que incluyan la columna Identificación.",
        ("Carga los Excel.", "Pulsa Procesar Excel.", "Revisa el número de precintos y la vista previa.", "Guarda el CSV."),
        "Un CSV de una columna con los precintos extraídos.",
        "Si un archivo no contiene la columna esperada, aparecerá como incidencia y no se mezclará silenciosamente.",
    ),
    "control_recepcion_precintos": AppHelp(
        "Valida un TXT FAC de precintos, lo cruza con SealsReport y prepara la documentación de recepción.",
        "Centraliza en un único flujo la corrección, la salida AX, los rangos PDF y el correo final.",
        "Necesitas el TXT FAC; añade SealsReport cuando vayas a realizar el cruce de albarán.",
        ("Carga el TXT FAC y revisa las incidencias.", "Corrige las líneas necesarias y pulsa Revalidar.", "Guarda el TXT AX y carga SealsReport para Cruzar albarán.", "Completa los datos del informe, genera el PDF o envía el correo."),
        "TXT AX, cruce de recepción, PDF de rangos y correo con sus adjuntos.",
        "Guarda primero el TXT AX: es el paso que habilita el cruce posterior con el albarán.",
    ),
    "precintos_txt_ax": AppHelp(
        "Extrae los precintos escritos a la derecha de una flecha en un TXT.",
        "Sirve para convertir rápidamente un listado de texto en un CSV de una columna para AX.",
        "Selecciona un TXT que contenga líneas con el separador -> o →.",
        ("Selecciona el TXT.", "Revisa el resumen de valores extraídos e ignorados.", "Pulsa Convertir a CSV y elige dónde guardarlo."),
        "Un CSV de una columna con los precintos únicos extraídos.",
        "Las líneas sin flecha o sin valor se muestran como ignoradas para que puedas comprobarlas.",
    ),
    "pesos": AppHelp(
        "Prepara Excel de pesos: renombra la primera hoja visible a Hoja1 y, si eliges vaciado, ajusta pesoBruto y pesoNeto.",
        "Sirve para dejar los libros listos para el flujo posterior sin modificar otros datos o formatos.",
        "Carga archivos XLSX, XLSM o XLS. Para vaciado, deben existir las columnas pesoBruto y pesoNeto.",
        ("Carga los Excel.", "Marca Vaciado normal o completo solo en los lotes que lo necesiten.", "Pulsa Procesar lote.", "Revisa el resultado por archivo antes de cerrar."),
        "Los mismos Excel actualizados, con la hoja Hoja1 y los pesos ajustados cuando se haya indicado.",
        "El vaciado normal descuenta el 1,1 %; el completo añade además 2,9 kg de descuento.",
    ),
    "reparto_merma_precintos": AppHelp(
        "Prepara un CSV para AX de precintos deshuesados desde PDA o FAC.",
        "Sirve para repartir el peso final entre precintos (PDA) o consolidar las filas seleccionadas de FAC.",
        "Elige PDA si partes de mensajes/lecturas; elige FAC si ya dispones de CSV de deshuesado.",
        ("Elige el modo PDA o FAC.", "Carga el fichero o los CSV correspondientes.", "En PDA indica el peso final; en FAC confirma las filas marcadas como SI y la orden.", "Revisa el reparto y guarda el CSV AX."),
        "CSV AX con orden de trabajo, precinto y peso.",
        "En modo FAC solo se exportan las filas marcadas como SI; no se recalcula su merma.",
    ),
    "file_compare": AppHelp(
        "Compara dos archivos o carpetas para saber si son iguales y localizar sus diferencias.",
        "Sirve para verificar entregas, detectar cambios en listados y generar un informe de comparación.",
        "Elige un archivo o carpeta A y otro B; usa el mismo tipo de ruta en ambos lados cuando sea posible.",
        ("Selecciona las dos rutas.", "Elige Estricto, Semántico o Automático y, si quieres, ajusta las opciones de texto.", "Pulsa Comparar.", "Lee el resumen y guarda o copia el informe si lo necesitas."),
        "Un resultado visual y un informe exportable en texto, JSON o HTML.",
        "El modo estricto compara bytes; el semántico ayuda con JSON, XML y CSV cuando el orden o formato no es lo importante.",
    ),
    "numerador_etiquetas": AppHelp(
        "Crea una secuencia de códigos, diseña la etiqueta e imprime las unidades consecutivas.",
        "Sirve para evitar saltos o repeticiones al numerar etiquetas y conservar diseños reutilizables.",
        "Indica el primer código y la cantidad; puedes partir del último código confirmado.",
        ("Define primer código y cantidad.", "Elige o ajusta un diseño y comprueba la vista previa.", "Pulsa Enviar a impresora.", "Confirma impresión solo cuando haya terminado correctamente."),
        "Etiquetas impresas y el último código confirmado guardado para la próxima secuencia.",
        "Confirmar impresión actualiza el contador; si la impresión falla, usa Descartar pendiente para no avanzar el número.",
    ),
}


def help_for(app: AppDefinition) -> AppHelp:
    return APP_HELP.get(
        app.key,
        AppHelp(app.description, "Te guía para completar el proceso con seguridad.", "Prepara los archivos necesarios.", ("Carga la información.", "Revisa el resultado.", "Guarda la salida."), "Una salida revisada.", "Sigue siempre la siguiente acción indicada por la aplicación."),
    )


class AppHelpDialog(QDialog):
    """Visual, short and contextual help available from every embedded app."""

    def __init__(self, app: AppDefinition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        guide = help_for(app)
        self.setObjectName("AppHelpDialog")
        self.setWindowTitle(f"Guía rápida · {app.title}")
        self.setAccessibleName(f"Guía de ayuda de {app.title}")
        self.resize(740, 680)
        self.setMinimumSize(580, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        scroll = QScrollArea()
        scroll.setObjectName("AppHelpScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Windows may render a transparent scroll viewport with its native
        # fallback colour.  Give both layers an explicit themed canvas.
        scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        content = QWidget()
        content.setObjectName("AppHelpContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 10, 4)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("HelpHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(5)
        eyebrow = QLabel("GUÍA RÁPIDA")
        eyebrow.setObjectName("HelpOverline")
        title = QLabel(app.title)
        title.setObjectName("HelpTitle")
        title.setWordWrap(True)
        purpose = QLabel(guide.purpose)
        purpose.setObjectName("HelpLead")
        purpose.setWordWrap(True)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(purpose)
        layout.addWidget(hero)

        benefit = self._info_card("¿Para qué sirve?", guide.benefit, "HelpBenefitCard")
        layout.addWidget(benefit)

        flow_title = QLabel("Cómo usarla")
        flow_title.setObjectName("HelpSectionTitle")
        layout.addWidget(flow_title)
        for index, step in enumerate(guide.steps, start=1):
            layout.addWidget(self._step_card(index, step))

        io_row = QHBoxLayout()
        io_row.setSpacing(10)
        io_row.addWidget(self._info_card("Antes de empezar", guide.input_hint, "HelpInputCard"), 1)
        io_row.addWidget(self._info_card("Obtendrás", guide.output_hint, "HelpOutputCard"), 1)
        layout.addLayout(io_row)

        tip = self._info_card("Consejo", guide.tip, "HelpTipCard")
        layout.addWidget(tip)
        layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        close_button = QPushButton("Entendido")
        close_button.setObjectName("HelpCloseButton")
        close_button.setProperty("primary", True)
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        root.addWidget(close_button, 0, Qt.AlignRight)

    @staticmethod
    def _info_card(title: str, text: str, object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setAccessibleName(title)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("HelpCardTitle")
        body = QLabel(text)
        body.setObjectName("HelpCardBody")
        body.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(body)
        return card

    @staticmethod
    def _step_card(index: int, text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("HelpStepCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(10)
        number = QLabel(str(index))
        number.setObjectName("HelpStepNumber")
        number.setAlignment(Qt.AlignCenter)
        number.setFixedSize(28, 28)
        description = QLabel(text)
        description.setObjectName("HelpStepText")
        description.setWordWrap(True)
        layout.addWidget(number, 0, Qt.AlignTop)
        layout.addWidget(description, 1)
        return card
