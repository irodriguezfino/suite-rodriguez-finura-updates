# Revisión de selectores y cierres

## Inventario de aplicaciones

| Aplicación | Selector o menú | Revisión de cierre |
| --- | --- | --- |
| Merma Jamones FAC | Filtro `Cumple` con `ModernSelect` | Resultado pendiente hasta exportar Excel. |
| Procesador TXT a CSV | Sin selector de valores | Resultado pendiente hasta guardar CSV. |
| Palets PDA | Sin selector de valores | Resultado/correcciones pendientes hasta guardar CSV. |
| Precintos Jamones | Sin selector manual de tipo | Resultado, correcciones o filtro de peso pendientes hasta salida. |
| Precintos Expedición | Selección múltiple de pallets mediante tabla | TXT generados pendientes hasta guardarlos. |
| Precintos Excel a CSV | Sin selector de valores | Precintos procesados pendientes hasta guardar CSV. |
| Control y Recepción Precintos | Sin selector de valores | Correcciones/TXT/PDF pendientes hasta salida correspondiente. |
| Precintos TXT a CSV AX | Sin selector de valores | Precintos extraídos pendientes hasta guardar CSV. |
| Pesos | Sin selector de valores | Operación de renombrado se finaliza en el propio proceso; no se avisa tras completarla. |
| Reparto de Merma por Precintos | Sin selector de valores | Reparto calculado pendiente hasta exportar CSV AX. |

## Componentes compartidos

- `ModernSelect`: selección única para listas cortas, popup nativo, foco y opciones deshabilitadas.
- `SearchableComboBox`: búsqueda por texto para procesos de la organización; informa cuando no hay coincidencias.
- `ActionMenuButton`: menú de acciones de categorías, separado de los selectores de valores.
- `QMenu` de tablas: menú contextual común con el mismo tema visual.

No hay otras instancias visibles de `QComboBox` fuera de estos usos. La selección múltiple de pallets se mantiene como tabla, porque requiere revisar unidades y peso antes de operar.

## Affordance y diseño de apertura

- Todos los selectores de valores usan el mismo chevron dibujado por `ModernSelect`: permanece visible con placeholder, valor, foco, error o estado deshabilitado.
- El chevron ocupa una zona fija a la derecha y se orienta hacia arriba mientras el popup está abierto; el borde y el fondo también cambian para no depender solo del icono.
- `SearchableComboBox` conserva el área de texto y su botón nativo de limpieza, pero el chevron sigue reservado a la apertura. El cursor de texto se limita al campo editable; el selector simple usa cursor de mano.
- El filtro de Merma Jamones se identifica semánticamente como filtro y mantiene el mismo patrón de apertura.
- `ActionMenuButton` usa exclusivamente el indicador de tres puntos para sus acciones. Se ocultó el indicador nativo secundario para que no se confunda con un selector de valores.
- No existen selectores de fecha, formato, columna o tipo adicionales en las demás aplicaciones. Tampoco hay un multiselector desplegable: la selección múltiple de expedición es una tabla con filas verificables.

## Criterio único de cierre

`close_risk_reason()` centraliza la decisión. Un archivo simplemente seleccionado no genera aviso. Se solicita confirmación sólo cuando hay datos procesados sin salida, correcciones pendientes o una operación con `operationActive`.

Al guardar una salida final, `show_inline_message()` registra una firma del trabajo. El mismo resultado se puede cerrar sin repetir el aviso; si se procesa o edita de nuevo, la firma cambia y vuelve a existir riesgo. Cada ventana instala un único guard de cierre mediante `polish_window()`, por lo que el contenedor de la Suite no duplica la confirmación de la aplicación hija.
