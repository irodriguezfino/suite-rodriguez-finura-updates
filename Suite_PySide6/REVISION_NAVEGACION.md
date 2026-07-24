# Revisión de navegación

## Arquitectura revisada

- La Suite es una aplicación de escritorio PySide6: no usa rutas web, WebViews, iframes, Electron ni Tauri.
- El shell (barra lateral, cabecera, fondo y `QStackedWidget`) se crea una vez y permanece estable.
- Las diez herramientas se resuelven con `app_windows.py`, que ya tenía un registro perezoso de clases.
- Cada página abierta se conserva en el `QStackedWidget`; al volver a ella se reutilizan sus filtros, selección y resultados temporales.
- Los modales son `QDialog`/`QMessageBox` nativos. No hay paneles laterales independientes que requieran una transición adicional.

## Medición

| Flujo | Medición |
| --- | ---: |
| Importación perezosa inicial de Merma Jamones | ~7,0 s |
| Importación perezosa inicial de Precintos Jamones | ~4,0 s |
| Construcción de Merma una vez importada | ~75 ms |
| Construcción de Precintos Jamones una vez importada | ~36 ms |
| Respuesta de `open_app()` con página de preparación | ~2–7 ms |

La causa de lag real era la importación inicial de módulos pesados, no la construcción de los widgets ni el cambio del `QStackedWidget`.

## Corrección de parpadeo

La causa del parpadeo inicial eran dos cambios visuales encadenados: la página nueva se hacía visible en el `QStackedWidget` y, después, recibía un efecto de opacidad de 0,82; además, la página de preparación se mostraba incluso si la carga terminaba en el siguiente ciclo de eventos. Esto producía un cambio de brillo y un fallback de duración mínima.

- La entrada de vista es ahora estable: no se instala ningún efecto de opacidad después de mostrarla.
- La página de preparación tiene un umbral de 120 ms. Antes de ese límite se conserva la vista previa y solo cambia el estado activo de la navegación.
- Si el módulo sigue cargando tras el umbral, el skeleton se muestra dentro del mismo shell y permanece hasta que la vista está preparada.
- Al cerrar la Suite se invalida cualquier apertura pendiente; una carga obsoleta no puede volver a mostrar una página.

## Correcciones

- `preload_window_class()` importa las clases de ventana en segundo plano al situar el puntero o el foco en un acceso de aplicación.
- El primer clic cambia de inmediato el estado activo. La página estructural de preparación solo aparece tras 120 ms, dentro del shell estable; no hay pantalla blanca ni spinner global ni skeleton fugaz.
- Mientras una importación está pendiente, se ignoran solicitudes repetidas de la misma aplicación. Si el usuario elige otra, solo se materializa la última solicitada.
- Las páginas ya abiertas se activan al instante y nunca se recrean.
- `reveal_view()` mantiene la página a opacidad estable. Se retiró el efecto de opacidad que se instalaba después del cambio de `QStackedWidget`, porque producía un frame de brillo distinto. Con movimiento reducido conserva el mismo comportamiento estable.
- Los avisos por trabajo pendiente no cambian: cambiar de aplicación conserva la página actual; cerrar una pestaña o la Suite continúa pasando por el guard central.

## Inventario de aplicaciones

Se revisaron Merma Jamones FAC, Procesador TXT a CSV, Palets PDA, Precintos Jamones, Precintos Expedición, Precintos Excel a CSV, Control y Recepción Precintos, Precintos TXT a CSV AX, Pesos y Reparto de Merma por Precintos. Ninguna carga ni procesa archivos durante su constructor: esa lógica se activa después mediante sus acciones explícitas.
