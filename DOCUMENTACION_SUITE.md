# Suite Rodriguez Finura

Documento funcional vivo de la Suite Rodriguez Finura.

Ultima revision: v1.4.15

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
