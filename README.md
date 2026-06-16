# Suite Rodriguez Finura - canal de actualizaciones

Este repositorio publica el manifiesto y el instalador que consulta la suite al arrancar.

## Archivos necesarios

- `version.json`: manifiesto remoto que lee la aplicacion.
- `Instalador_Suite_Rodriguez_Finura_v1.3.22.exe`: instalador descargado por el actualizador.
- `CHANGELOG_v1.3.22.txt`: cambios de la version publicada.

## Funcionamiento

La version 1.3.21 y posteriores de la suite consultan:

`https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main/version.json`

Si `version.json` contiene una version superior a la instalada, descarga `installer_url`, comprueba el `sha256` y lanza el instalador.

## Publicar una version nueva

1. Generar el instalador nuevo.
2. Calcular su SHA-256.
3. Subir el instalador al repositorio.
4. Actualizar `version.json` con `version`, `installer`, `installer_url`, `sha256` y `notes`.
5. Hacer commit y push a `main`.

No hace falta OneDrive sincronizado ni rutas locales en los equipos cliente.
