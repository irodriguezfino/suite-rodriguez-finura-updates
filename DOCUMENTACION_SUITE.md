# Suite Rodriguez Finura

Documento funcional vivo de la Suite Rodriguez Finura.

Ultima revision: v1.4.2

## Para que sirve

La suite agrupa herramientas internas para preparar, revisar y convertir ficheros usados en procesos de jamones, palets, precintos y trazabilidad. Su objetivo es reducir trabajo manual, detectar errores antes de importar datos y generar salidas compatibles con los flujos habituales de la empresa.

## Menu principal

El menu principal centraliza el acceso a las aplicaciones, muestra el estado de version dentro de Acerca de, permite buscar actualizaciones y mantiene una experiencia visual coherente entre herramientas.

Desde v1.4.0 adopta una interfaz preparada para crecer con mas aplicaciones:

- Navegacion lateral por categorias.
- Buscador rapido por nombre, proceso o palabra clave.
- Accesos favoritos/recientes en tarjetas.
- Vista de lista para trabajar con muchas herramientas sin saturar la pantalla.
- Indicacion visual de aplicaciones abiertas dentro de cada acceso, cambiando Abrir por Traer.
- Logos de Finura y Rodriguez en la parte inferior.
- Detalles rojos discretos en separadores, categoria activa e iconos, manteniendo el azul como color principal.
- Atajos Alt+1 a Alt+5 para las aplicaciones actuales y Ctrl+K para enfocar la busqueda.

Desde v1.4.1 cada acceso permite marcar o quitar favoritos con una estrella. La seleccion se guarda por usuario. El modo compacto funciona como una ventana pequena de lista densa, ocultando lateral, footer y controles no esenciales para maximizar el espacio util.

Desde v1.4.2 el modo compacto ordena primero las aplicaciones favoritas y reduce el tamano de la estrella y del boton de apertura para evitar cortes en ventanas estrechas. Tambien corrige el scroll con la rueda del raton sobre filas, tarjetas, etiquetas o botones, y refina la cabecera y barra de busqueda para una presentacion mas profesional.

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
