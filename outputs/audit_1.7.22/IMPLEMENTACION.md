# Interfaz de la suite — v1.7.22

Se han aplicado los 20 puntos de la auditoría estética, siguiendo sus tres grupos de prioridad. Los cambios afectan a presentación, distribución y controles de interfaz; no a los motores de las aplicaciones.

## Cambios aplicados

| Auditoría | Implementación |
|---|---|
| 1. Alineación de tarjetas | `ModuleRow` usa un bloque común para Opciones y Abrir, separado de título, descripción y metadatos. El bloque pasa completo a una fila inferior cuando falta espacio. |
| 2. Botones consistentes | Altura lógica común, ajustable a la fuente, y radio compartido para botones normales y menús de acciones. |
| 3. Casillas inequívocas | Marca explícita, raya para selección parcial y foco visible. Se conservan los estados y eventos nativos de Qt. |
| 4. Cabeceras compactas | Título y acciones comparten fila; descripción, estado y búsqueda disponen de filas propias. Las cabeceras de aplicaciones de la muestra miden 113 px, frente a unos 170 px anteriores. |
| 5. Personalización secundaria | Editar/restaurar descripción se agrupan en Opciones. Se conserva el texto privado y la confirmación de restauración; restaurar se desactiva cuando no hay personalización. |
| 6. Orientación sin repeticiones | Se retiran de la vista los bloques que repetían el nombre del botón recomendado, conservando los datos internos de contexto. |
| 7. Formularios coherentes | Comparador y Numerador usan desplegables y controles numéricos compartidos. Se conservan valores por defecto, límites, decimales, pasos, sufijos y la protección frente a la rueda del Numerador. El selector especializado de fuentes sigue siendo nativo. |
| 8. Menos profundidad visual | Se eliminan sombras en tarjetas de catálogo y paneles operativos internos. Se mantienen superficies sobrias y separadores. |
| 9. Densidad compacta útil | La primera tarjeta pasa de 89 a 63 px de alto sin eliminar la descripción. Las acciones permanecen iguales en las dos densidades. |
| 10. Metadatos del catálogo | Se deja de repetir categoría y Disponible en cada tarjeta. La información sigue en la descripción accesible; el atajo se conserva y los estados distintos de Disponible siguen visibles. |
| 11. Bandeja ordenada | Se elimina el segundo enlace al catálogo de Herramientas frecuentes. La tarjeta Retomar solo aparece cuando existe actividad. Se mantiene el acceso principal Ver procesos y la navegación lateral. |
| 12. Estados vacíos | Pesos muestra una explicación de carga dentro de la tabla, sin métricas ni resúmenes de ceros. La recuperación de lotes sigue accesible. Las tablas virtuales comparten un mensaje vacío y muestran métricas/detalles al tener datos. |
| 13. Elección PDA/FAC | Dos tarjetas con título, explicación y botón Abrir. Se conserva cada destino, su estado y su foco de entrada. |
| 14. Escala visual | Se introducen constantes compartidas de dimensiones y tipografía, usadas en controles, estilos y paneles. Se conserva Segoe UI y la paleta corporativa. |
| 15. Tablas | Las columnas de vaciado de Pesos reservan el espacio necesario para texto/selección, dejando más anchura a archivo y detalle. Se conservan rutas completas en la ayuda, desplazamiento y selección por clave. |
| 16. Nombres y navegación | Los trabajos abiertos usan el nombre de catálogo, abreviado por espacio mediante puntos suspensivos, con nombre completo accesible y en ayuda. Se añade desplazamiento en esa lista para no comprimir o perder trabajos cuando hay muchos abiertos. |
| 17. Iconos | Catálogo y tarjetas frecuentes comparten pictogramas vectoriales sencillos según función; no dependen de fuentes de símbolos ni de QtSvg. El logotipo se adapta al ancho y al factor de escala. |
| 18. Foco y estados | Botones y menús mantienen geometría al recibir foco. Se comprueban teclado, estado parcial/desactivado de casillas y menús. Los colores y textos de error existentes se conservan. |
| 19. Progreso estable | Se conserva el indicador persistente y el cálculo de progreso real. Solo se flexibiliza la anchura visual de la barra; no cambia el avance, cancelación ni finalización. |
| 20. Regresión visual | Nuevo verificador reproducible y nueve pruebas de contrato: acciones, personalización, teclado, fuentes mayores, controles, valores por defecto, estado vacío, destinos PDA/FAC y cabecera. |

## Validación

- Suite automática: **215 pruebas, 214 superadas y una integración opcional con Excel omitida**, en 25,424 segundos. Los mensajes de errores de fondo que aparecen durante la suite corresponden a pruebas de fallos simulados.
- Renderizado real de Qt con preferencias temporales: **12 aplicaciones, claro/oscuro y escalas 100 %, 125 %, 150 % y 200 %**.
- Catálogo en anchos 1360, 1000 y 960 px lógicos, con la ventana mínima de 960 × 620 incluida; ambas densidades.
- **576 mediciones de tarjetas: desfase máximo 0 px** entre los centros de Opciones y Abrir; alturas iguales. Pruebas adicionales de fila estrecha independiente, descripción larga y fuente aumentada.
- **164 capturas** de interfaz, incluyendo progreso en aplicaciones representativas. El porcentaje mostrado en esas capturas de progreso es una simulación de eventos, no un lote real.
- Se comprueba que las 12 aplicaciones solo muestran la barra común al simular una operación, sin recuperar barras anteriores.
- Combinaciones de contraste seleccionadas: mínimo **4,63:1**. No equivale a una certificación integral de accesibilidad.
- Los **35 archivos de motor `.py`/`.ps1`** comparados son idénticos a la v1.7.21 por contenido.
- ZIP de actualización y ZIP completo: CRC correcto y **73 archivos Python de `src` idénticos** al código validado y a la copia local desempaquetada.
- Apertura de las 12 aplicaciones con el **Python 3.14.5 incluido en el paquete**, sin importar pandas ni openpyxl durante la apertura. Valores iniciales del Comparador confirmados en esa copia.
- `git diff --check` sin errores.

### Medición de rendimiento de interfaz

Medición local fuera de pantalla, no garantía de tiempos en cualquier equipo:

| Operación | Resultado |
|---|---:|
| Abrir catálogo de Procesos | 90,3 ms |
| Respuesta inmediata al pedir una aplicación | 1,1–3,7 ms |
| Aplicación preparada | 92–213 ms |
| Poblar Pesos con 5.000 filas sintéticas | 126,3 ms |
| Poblar FAC con 5.000 filas sintéticas | 63,3 ms |
| Widgets internos por tabla virtual | 18 |

Todos los límites automatizados previos se cumplen: catálogo <250 ms, respuesta <100 ms, formularios <800 ms y tablas de 5.000 filas <500 ms. Esta actualización no modifica el tiempo del motor de Pesos.

## Cómo probarla

Cierra la versión anterior y abre `Abrir_Prueba_v1.7.22.cmd`, situado en la raíz del proyecto. El acceso abre la copia fija de `outputs/full_release_1.7.22/Suite Rodriguez Finura`, no el código de desarrollo.

El acceso de prueba no sustituye la instalación existente ni la copia local v1.7.21. Como la suite habitual, utiliza las preferencias de tu perfil. La distribución mediante GitHub utiliza los paquetes completos/de actualización y el manifiesto `version.json`; no requiere las carpetas locales de prueba.

Comprobación rápida: Procesos → alternar Vista compacta → abrir Opciones → abrir Pesos → cargar archivos → seleccionar vaciado → comprobar desplazamiento y progreso. Las pruebas de esta entrega no han modificado tus archivos originales.

## Evidencias y límites

- `ui/<escala>/metrics.json`: medidas y lista de aplicaciones.
- `ui/<escala>/*.png`: capturas de Qt.
- `performance/ui_1.json`: tiempos, tablas y contraste.
- `package_results.json`: identidad de paquetes, motores y apertura con runtime incluido.
- Scripts: `Suite_PySide6/tools/verify_aesthetic_ui.py`, `verify_completion_ui.py` y `verify_local_release.py`.

No se ha repetido en esta actualización puramente visual la integración con Excel real de la v1.7.21, ni se han enviado correos o realizado impresiones físicas. Tampoco se certifica el comportamiento en todas las combinaciones de monitor/controlador de Windows. Se han conservado los motores y verificado los contratos de interfaz que los invocan.
