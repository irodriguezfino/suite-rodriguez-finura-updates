CONFIGURACION DEL REPO DE GITHUB PARA ACTUALIZACIONES AUTOMATICAS
Suite Rodriguez Finura

Objetivo
--------
La suite debe instalarse una vez y, al arrancar, consultar un version.json remoto
por HTTPS. Si hay una version superior, descarga el instalador desde GitHub,
comprueba su SHA-256 y lo lanza. No debe depender de OneDrive, carpetas
sincronizadas ni rutas configuradas equipo por equipo.

Configuracion recomendada del repo
----------------------------------
1. Repositorio publico usado:
   https://github.com/irodriguezfino/suite-rodriguez-finura-updates

2. En la raiz del repo, subir y mantener este archivo:
   version.json

3. En la raiz del repo, subir tambien el instalador:
   Instalador_Suite_Rodriguez_Finura_v1.3.22.exe

4. El version.json de la raiz debe apuntar al instalador con installer_url.
   Ejemplo:

   {
     "version": "1.3.22",
     "installer": "Instalador_Suite_Rodriguez_Finura_v1.3.22.exe",
     "installer_url": "https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main/Instalador_Suite_Rodriguez_Finura_v1.3.22.exe",
     "sha256": "EC576EA9F24B9558195DC237470CF3691EA9608F042012CB60EB1278F09C3597",
     "notes": "Version de prueba del canal GitHub/HTTP directo."
   }

5. La URL que queda grabada en la aplicacion es:
   https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main/version.json

Flujo para futuras versiones
----------------------------
1. Generar el instalador nuevo.
2. Calcular su SHA-256.
3. Subir el .exe nuevo a la raiz del repo.
4. Editar el version.json de la raiz del repo con:
   - version nueva
   - installer_url nuevo
   - sha256 nuevo
   - notes nuevas
5. Confirmar y subir el cambio a main.

Importante
----------
La version 1.3.21 y posteriores quedan compiladas con el version_url definitivo del repo real.
Desde esta version, los equipos no necesitan OneDrive sincronizado ni rutas
configuradas para consultar nuevas versiones.
