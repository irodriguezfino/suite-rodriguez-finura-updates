# Suite Rodriguez Finura

Documento funcional vivo de la Suite Rodriguez Finura.

Ultima revision: v1.4.28

## Para que sirve

La suite agrupa herramientas internas para preparar, revisar y convertir ficheros usados en procesos de jamones, palets, precintos y trazabilidad. Su objetivo es reducir trabajo manual, detectar errores antes de importar datos y generar salidas compatibles con los flujos habituales de la empresa.

## Menu principal

El menu principal centraliza el acceso a las aplicaciones, muestra el estado de version dentro de Acerca de, permite buscar actualizaciones y mantiene una experiencia visual coherente entre herramientas.

Desde v1.4.7 el menu principal usa componentes redondeados basados en Canvas para cabecera, panel lateral, panel central, tarjetas, filas e items de categoria.

Desde v1.4.8 mantiene Canvas en todos esos componentes, pero cambia el motor visual del menu: categorias, secciones, tarjetas y filas se cachean y se actualizan de forma incremental en vez de destruirse y recrearse.

Desde v1.4.9 el modo oscuro actualiza tambien los Canvas persistentes del menu principal. La capa comun de estilo incorpora un panel Canvas reutilizable aplicado a los bloques principales de las aplicaciones internas.

Desde v1.4.10 el rojo se reserva al foco de teclado en paneles Canvas, mientras que hover y click de raton usan bordes suaves azul-gris. Tambien se modernizan las barras de scroll ttk con un estilo plano, sin flechas clasicas visibles y adaptado al modo claro/oscuro.

Desde v1.4.11 el hover de Canvas evita parpadeos usando deteccion por coordenadas y limpieza retardada del estado. Los contenedores principales quedan estables y el hover decorativo se limita para reducir ruido visual y repintados, manteniendo foco de teclado accesible y el flujo principal sin cambios.

Desde v1.4.12 se refuerza la ergonomia diaria: las aplicaciones recuerdan la ultima carpeta usada para abrir o guardar archivos, se ordena mejor la navegacion por teclado y las acciones cortas bloquean temporalmente sus botones para evitar dobles ejecuciones accidentales.

Desde v1.4.13 el menu mejora la fluidez visual: se construye oculto hasta completar el primer layout, evita renders completos al abrir o cerrar aplicaciones y cambia categoria/busqueda sin vaciar el panel central entre repintados.

Desde v1.4.14 la apertura de menu y aplicaciones usa una rutina comun que prepara las ventanas invisibles y las muestra solo tras aplicar layout, maximizado e icono. Tambien se refuerza el icono de Windows con AppUserModelID, iconbitmap e iconphoto para la barra de tareas.

Desde v1.4.15 la barra nativa superior de Windows se sincroniza con el tema claro u oscuro activo, y las ventanas incorporan una animacion breve de entrada para una apertura mas fluida sin cambiar la logica funcional.

Desde v1.4.16 la animacion de apertura se coordina con el menu: la aplicacion aparece sobre el menu sin simular minimizacion, y al cerrar se desvanece dejando el menu visible detras. Los cierres desde la X de Windows y desde botones internos pasan por la misma salida visual.

Desde v1.4.17 la sincronizacion de la barra nativa de Windows aplica DWM al HWND de Tk y a sus wrappers padre, fuerza refresco del marco y reintenta tras el montaje de la decoracion nativa.

Desde v1.4.18 se corrigen bugs de refactor visual: el scroll global del modo compacto deja de borrar bindings de otras ventanas, Acerca de usa un tamano propio, el estado inferior vuelve a ser visible sin mostrar el listado de aplicaciones abiertas y el layout se mantiene estable al abrir herramientas. Tambien se estabilizan los minimos de paneles Canvas, tarjetas, filas y botones para evitar reescalados al cambiar entre Abrir y Traer.

Desde v1.4.19 se corrige la regresion visual de v1.4.18 que hacia crecer demasiado la cabecera, el panel lateral y algunas categorias al abrir el menu. Los paneles Canvas redondeados parten de un tamano minimo real y despues crecen hasta su contenido.

Desde v1.4.20 se corrige la regresion visual de v1.4.19 que dejaba botones, tarjetas y categorias sin altura visible. Los Canvas recuperan su tamano inicial natural y despues sincronizan su tamano exacto con el contenido medido.

Desde v1.4.22 se incorpora Precintos Expedicion, una herramienta para generar el TXT de expedicion de jamones desde los Excel de entrada y salida de AX, con deteccion automatica de archivos y validacion estricta de unidades y kilos.

Desde v1.4.23 Precintos Expedicion sustituye el filtro manual de articulo y peso por seleccion multiple de pallets de entrada, anade flujo visual de cuatro pasos y muestra una tabla resumen tipo dinamica en la validacion.

Desde v1.4.24 Precintos Expedicion corrige la reactivacion de botones al limpiar o finalizar acciones, guarda el TXT sin BOM para importacion limpia en AX y reemplaza el selector primitivo por una tabla ttk seleccionable adaptada al modo oscuro.

Desde v1.4.25 Precintos Expedicion admite una entrada con varias salidas en la misma sesion, mantiene la seleccion acumulativa de Excel, sugiere automaticamente los pallets que cuadran con las unidades totales y genera un TXT independiente por cada salida.

Desde v1.4.26 Precintos Expedicion solo genera nombre TXT automatico si el Excel de salida contiene un bloque exacto de 6 digitos; en caso contrario obliga al operario a escribir el nombre. La sugerencia de pallets se recalcula automaticamente al cargar o anadir Excel, sin boton visible.

Desde v1.4.27 se incorpora Recepcion Maquilas, una herramienta para comparar el TXT recibido de FAC con el Excel oficial SealsReport y generar informes PDF de diferencias y rangos de peso.

Desde v1.4.28 Recepcion Maquilas genera los PDF en A4 vertical, carga siempre la configuracion interna `config_articulos.csv`, toma albaran y lote origen desde SealsReport y muestra en la tabla de rangos el lote real del TXT.

## Aplicaciones incluidas

### Merma jamones FAC embutidos Rodriguez

Cruza ficheros CSV finales con un fichero origen para revisar estados de merma. Permite filtrar resultados, previsualizar datos y exportar el resultado a Excel.

### Procesador de TXT a CSV

Convierte uno o varios ficheros TXT a CSV. Esta pensado para preparar ficheros de texto estructurado para su uso posterior en hojas de calculo o importaciones.

### Palets PDA a CSV

Procesa TXT procedentes de PDA, valida codigos de palet, muestra incidencias corregibles, permite revalidar datos y genera un CSV final con los codigos aceptados.

### Control Precintos Jamones

Carga TXT de lecturas de precintos de jamon, valida partida, lote, articulo, precinto, fecha y hora, diferencia incidencias reales de duplicados, permite corregir registros en un area de trabajo editable y genera salidas TXT/CSV.

Tambien permite comparar con Excel oficial cuando aplica, mostrar diferencias y preparar listados importables en AX. Desde v1.3.41 incluye envio por correo de los ficheros generados y desde v1.3.42 permite personalizar asunto y mensaje del correo.


### Precintos Expedicion

Genera el TXT de expedicion de jamones para AX a partir de un Excel de entrada y uno o varios Excel de salida. Detecta automaticamente cada tipo de archivo por sus columnas, ignora lineas sin precinto y permite seleccionar uno o varios Id de pallet de entrada sin consultar rangos de peso en AX.

La pantalla guia al operario con cuatro pasos: adjuntar Excel, seleccionar pallet/s, comprobar y guardar. El boton Seleccionar Excel acumula archivos para poder cargar primero la entrada y anadir salidas despues sin limpiar. El selector de pallets usa una tabla ttk con marca de seleccion, cuenta de precintos, peso neto y una ayuda de coincidencia con las salidas cargadas.

La aplicacion sugiere automaticamente el pallet o combinacion de pallets cuya cuenta de precintos coincide con las unidades totales requeridas, pero mantiene la revision manual antes de comprobar. La validacion muestra cada salida con sus jumbos, unidades, kilos, nombre TXT previsto y estado.

Para cada jumbo reparte los kilos en milesimas entre sus unidades, cuadrando la suma exacta antes de permitir guardar. Genera un TXT independiente por cada Excel de salida con el formato `partida;fecha;hora;codigo_articulo;precinto;lote;peso;`, fecha/hora secuencial desde el momento de generacion y codificacion Windows sin BOM para evitar caracteres iniciales al importar en AX. Si la salida contiene un bloque exacto de 6 digitos, usa automaticamente `SCxxxxxx.TXT`; si no lo contiene, solicita el nombre TXT antes de guardar.

### Recepcion Maquilas

Genera informes PDF en A4 vertical a partir del TXT recibido de FAC, el Excel oficial SealsReport y el CSV interno de configuracion de articulos. El informe de diferencias muestra precintos recibidos que no aparecen en el oficial y precintos oficiales no recibidos.

El informe de rangos agrupa las piezas por codigo FAC, lote real del TXT y rango de peso, mostrando lote, rango ajustado, piezas, peso total y peso medio. Los rangos se calculan con maximo exclusivo para evitar doble conteo: un rango `10,5-12` cuenta desde `10,50` hasta `11,99`, de modo que una pieza de `12,00` entra solo en el rango siguiente.

La pantalla permite completar ganadero, origen, DAC, contrato y especificacion antes de emitir el PDF de rangos. El albaran y lote origen salen siempre de SealsReport; la cabecera mantiene `Lote:` para el lote del TXT.

### Precintos Excel a CSV

Extrae la columna de identificacion desde anexos Excel de trazabilidad y genera un CSV de una unica columna, preparado para importacion.

## Actualizaciones

La suite consulta el canal remoto de GitHub al arrancar. Si existe una version superior, muestra una ventana con la version instalada, la version disponible y las mejoras de esa version.

El texto de mejoras debe mantenerse en el `CHANGELOG_vX.Y.Z.txt` de cada version. El generador de paquetes copia ese contenido al campo `notes` de `version.json`, que es lo que lee la ventana de solicitud de actualizacion.

## Criterios de mantenimiento

- Cada nueva version debe tener su `CHANGELOG_vX.Y.Z.txt`.
- El `version.json` debe apuntar al ZIP publicado, con SHA-256 correcto.
- Este documento debe actualizarse cuando se anada una aplicacion, cambie una aplicacion o cambie un flujo importante.
- El README del repositorio debe describir el canal de actualizaciones; este documento describe la suite.
