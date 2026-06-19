# Suite Rodriguez Finura - canal de actualizaciones

Este repositorio publica el manifiesto y los paquetes que consulta la suite al arrancar.

## Archivos principales

- `version.json`: manifiesto remoto que lee la aplicacion.
- `Suite_Rodriguez_Finura_vX.Y.Z_update.zip`: paquete ZIP de actualizacion ligera.
- `CHANGELOG_vX.Y.Z.txt`: mejoras de la version publicada.
- `DOCUMENTACION_SUITE.md`: documentacion funcional viva de la suite y sus aplicaciones.
- `Suite_Rodriguez_Finura_v1.3.33.msi`: instalador MSI reservado para instalacion inicial.

## Funcionamiento

La suite consulta:

`https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main/version.json`

Si `version.json` contiene una version superior a la instalada, descarga el ZIP indicado en `package_url`, comprueba el `sha256` y aplica la actualizacion.

La ventana de solicitud de actualizacion muestra el campo `notes` de `version.json`. Ese campo debe salir de las mejoras reales del `CHANGELOG_vX.Y.Z.txt` correspondiente.

## Publicar una version nueva

1. Actualizar `version_local.json`.
2. Crear `CHANGELOG_vX.Y.Z.txt` con las mejoras concretas.
3. Actualizar `DOCUMENTACION_SUITE.md` si cambia una aplicacion o flujo importante.
4. Generar el ZIP y el `version.json`.
5. Subir al repositorio el ZIP, el `version.json`, el changelog y la documentacion actualizada.
6. Hacer commit y push a `main`.

No hace falta OneDrive sincronizado ni rutas locales en los equipos cliente.
