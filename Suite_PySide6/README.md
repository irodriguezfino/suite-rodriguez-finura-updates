# Suite Rodriguez Finura PySide6

Proyecto paralelo para portar la suite a PySide6 sin tocar la version Tkinter
estable.

## Objetivo de esta fase

- Mantener intacta la suite actual.
- Separar logica funcional reutilizable de la interfaz Tkinter.
- Preparar una base donde la UI PySide6 pueda crecer por modulos.

## Fuente de referencia

La primera referencia funcional se toma de:

`../outputs/worktree_1_4_27/build_1_4_43`

Esa carpeta no se modifica desde este proyecto. Se usa como comparador y como
fuente para extraer comportamiento probado.

## Estructura

- `src/suite_pyside6/core`: logica sin GUI.
- `src/suite_pyside6/ui`: futura capa visual PySide6.
- `tools`: verificaciones y utilidades de migracion.

## Primer modulo extraido

`suite_pyside6.core.precintos_excel` contiene la lectura de precintos desde
archivos XLSX/XLSM, separada de Tkinter. Es la primera pieza para portar la app
"Exportar Precintos Excel a CSV".

## Ejecutar el menu PySide6

Entorno local preparado:

`../qtv/Scripts/python.exe -m suite_pyside6.main`

Verificaciones:

`../qtv/Scripts/python.exe tools/verify_phase2.py`

`../qtv/Scripts/python.exe tools/verify_phase3.py`

`../qtv/Scripts/python.exe tools/verify_phase4.py`

`../qtv/Scripts/python.exe tools/verify_phase5.py`

`../qtv/Scripts/python.exe tools/verify_phase6.py`

`../qtv/Scripts/python.exe tools/verify_phase7.py`

`../qtv/Scripts/python.exe tools/verify_phase8.py`

`../qtv/Scripts/python.exe tools/verify_phase9.py`

`../qtv/Scripts/python.exe tools/verify_phase10.py`

La suite Tkinter actual sigue intacta. El menu nuevo puede lanzar apps legacy
como procesos separados mientras se portan una a una.

## Primera app portada

`Precintos Excel a CSV` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.precintos_excel_window.PrecintosExcelWindow`

El menu PySide6 abre esta version nueva. El resto de apps siguen preparadas para
abrirse como legacy mientras se portan.

## Segunda app portada

`Procesador TXT a CSV` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.txt_csv_window.TxtCsvWindow`

El core separado vive en:

`suite_pyside6.core.txt_csv`

## Tercera app portada

`Palets PDA a CSV` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.palets_window.PaletsWindow`

El core separado vive en:

`suite_pyside6.core.palets`

## Cuarta app portada

`Merma Jamones FAC` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.mermas_window.MermasWindow`

El core separado vive en:

`suite_pyside6.core.mermas`

## Quinta app portada

`Precintos Expedicion` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.precintos_expedicion_window.PrecintosExpedicionWindow`

El core separado vive en:

`suite_pyside6.core.precintos_expedicion`

## Sexta app portada

`Recepcion Maquilas` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.recepcion_maquilas_window.RecepcionMaquilasWindow`

El core separado vive en:

`suite_pyside6.core.recepcion_maquilas`

## Septima app portada

`Control y Recepcion Maquilas` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.control_recepcion_maquilas_window.ControlRecepcionMaquilasWindow`

El core separado vive en:

`suite_pyside6.core.control_recepcion_maquilas`

## Octava app portada

`Precintos Jamones` ya tiene ventana PySide6 propia:

`suite_pyside6.ui.precintos_jamones_window.PrecintosJamonesWindow`

El core separado vive en:

`suite_pyside6.core.precintos_jamones`

Con esta fase, las 8 apps del menu estan marcadas como portadas en PySide6.

## Pasada de paridad visual y funcional

Se ha reforzado el tema global PySide6 con la identidad azul/rojo de Rodriguez:

- Cabecera azul con acento rojo.
- Botones primarios rojos y foco/seleccion azul.
- Tablas, campos, estados y tarjetas con estilos comunes.
- Logo Rodriguez visible en el menu principal.
- Logo Finura visible junto a Rodriguez en el menu principal.
- Foco visible reforzado, contraste AA en colores principales y objetivos de
  accion mas grandes.
- Barras de pasos por aplicacion para indicar el flujo principal sin depender
  de memoria del usuario.
- Panel lateral de categorias y metricas del menu principal para mejorar
  orientacion y visibilidad del estado.
- Segunda pasada profesional sobre WCAG 2.2 AA + heuristicas de Nielsen:
  cabecera en tarjeta blanca con doble marca, acentos azul/rojo mas sobrios,
  paneles con sombras sutiles, tarjetas de aplicaciones con indicador lateral,
  categorias con conteo, botones con iconos nativos y tooltips, y estados mas
  escaneables sin cambiar la secuencia funcional.
- Tercera pasada de producto: se elimina el lenguaje tecnico de migracion del
  menu, se presenta la suite como panel operativo, se sustituyen estados
  "legacy/PySide6" por disponibilidad real, se refinan tarjetas, tablas,
  toolbars y textos de accion para que cada ventana se lea como una aplicacion
  profesional y no como un formulario tecnico.
- Cuarta pasada de interfaz: modo claro/oscuro persistente, logos Rodriguez y
  Finura en las aplicaciones, selector de tema en menu y ventanas, stepper
  visual comun, sombras mas suaves, tablas sin rejilla dura y atajos
  consistentes con tooltips para cargar, procesar, guardar y limpiar.
- Actualizacion de auditoria UI: se eliminan atajos duplicados por ventana, se
  asignan nombres accesibles a botones, campos, combos, tablas y areas de
  resultados, se evita reconstruir el menu en cada resize menor y se hace mas
  fiable el color alterno de tablas en Qt.
- Bloque A de mejoras funcionales de interfaz: panel de contexto por
  aplicacion con estado/siguiente accion/avisos, banners inline para avisos,
  errores y confirmaciones, y tooltips explicativos en botones deshabilitados.
- Bloque B de continuidad operativa: dialogos de abrir/guardar con memoria de
  carpeta por accion, historial reciente de archivos y exportaciones, y base
  comun de sesion con `QSettings` para no repetir navegacion manual.
- Bloque C de uso diario: arrastre de archivos sobre las ventanas portadas,
  stepper dinamico segun estado real, vistas Favoritos/Recientes en el menu y
  marcado de procesos favoritos desde cada tarjeta.
- Primera pasada de paridad funcional con legacy: Recepcion Maquilas y Control
  y Recepcion Maquilas recuperan los metadatos completos del PDF de rangos
  (`N DAC`, contrato, control de temperatura, PH, observaciones y
  especificacion); Control y Recepcion puede continuar con el TXT original si
  no hubo incidencias ni duplicados, genera el PDF temporal al enviar correo
  si no se guardo antes y adjunta detalle + PDF como en el flujo estable.
- Ajuste de Precintos Jamones: `formato_importable_ax` vuelve a generar los
  codigos separados por comas, igual que la aplicacion original.

Tambien se han recuperado pasos de flujo que no estaban suficientemente fieles
al legacy:

- `Precintos Jamones`: correccion editable de incidencias y revalidacion antes
  de guardar TXT/CSV.
- `Control y Recepcion Maquilas`: correccion editable de incidencias y
  revalidacion antes de guardar TXT AX y continuar con SealsReport.
- `Recepcion Maquilas`: los PDFs intentan usar el generador legacy original
  para mantener formato y contenido mas cercano a la version estable.

## Pasada de paridad funcional avanzada

Se han cerrado diferencias detectadas en la auditoria de clonacion frente a las
apps legacy:

- `Control y Recepcion Maquilas`: deteccion de jamon iberico/blanco por GTIN y
  por codigos FAC configurados como ibericos; validacion GTIN-12 estricta para
  iberico; partida de 6 digitos; sugerencias de partida/lote; filtro de pesos
  fuera de rango con correccion y revalidacion; limpieza de correcciones y
  plantilla de correo persistente.
- `Precintos Jamones`: sugerencias oficiales cercanas por distancia de digitos,
  transposicion simple y similitud; comparacion oficial incluyendo precintos de
  12 digitos aunque tengan incidencia; filtro de pesos fuera de rango con
  correccion y revalidacion; plantilla de correo persistente con variables.
- `Recepcion Maquilas`: accion para generar en una sola operacion el PDF de
  diferencias y el PDF de rangos, como en la aplicacion estable.
- `Precintos Expedicion`: validacion previa de nombres TXT pendientes,
  duplicados y caracteres no permitidos antes de guardar.

Las verificaciones `verify_phase1.py` a `verify_phase10.py` pasan tras esta
pasada.

## Bloque UI-A: accesibilidad y seguridad de uso

Primera tanda de mejoras de interfaz tras cerrar la paridad funcional:

- Modo oscuro: colores de texto para estados `success` y `warning` ajustados
  para cumplir contraste WCAG AA sobre sus fondos.
- Badges de pasos: contraste revisado en estados completado/aviso para modo
  oscuro.
- Botones deshabilitados: ademas del tooltip visible, se define descripcion
  accesible con el motivo por el que la accion no esta disponible.
- Orden de tabulacion: se aplica una secuencia de foco consistente a campos,
  combos, botones, areas de texto y tablas.
- Proteccion ante perdida de trabajo: las ventanas confirman al limpiar o
  cerrar cuando hay archivos, correcciones o resultados en pantalla.
- Las confirmaciones se desactivan automaticamente en verificaciones
  `offscreen`, para no bloquear las pruebas automatizadas.

## Bloque UI-B: toolbars y paneles profesionales

Segunda tanda de mejoras de interfaz centrada en reducir ruido visual y mejorar
la secuencia de uso:

- Se anaden estilos comunes para grupos de acciones (`Entrada`, `Revision`,
  `Cruce`, `Proceso`, `Salida`) y campos compactos.
- `Control y Recepcion Maquilas`: la barra de acciones se divide por etapas y
  los campos de peso dejan de forzar anchura excesiva.
- `Precintos Jamones`: se separan tipo/carga, revision/filtros y salidas.
- `Recepcion Maquilas`: se separan carga/configuracion, procesamiento y
  generacion de PDFs.
- Los paneles de correo se muestran como panel secundario diferenciado.
- Los metadatos de informes en Recepcion y Control Recepcion se marcan como
  panel de formulario, no como tarjeta generica.

### Ajuste UI-B adicional

Se ha aplicado una pasada adicional sobre todas las toolbars:

- Se eliminan los iconos automaticos de botones porque daban una lectura visual
  irregular y poco profesional.
- Los botones de toolbar usan etiquetas compactas, manteniendo el texto completo
  en tooltip y nombre accesible.
- Los anchos minimos de botones en toolbars se reducen para evitar cortes de
  texto.
- El stepper dinamico usa textos mas cortos y conectores simples.
- El modo oscuro se suaviza con fondos menos negros, superficies azul grisaceas
  y acentos menos agresivos, manteniendo contraste WCAG AA.
