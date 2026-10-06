# MIDI Premium 2

Aplicación de control MIDI para Windows con perfiles, PADs, perillas, integración con Photoshop, OBS y acciones del sistema.

## Actualizaciones

Desde v1.1.0 la aplicación consulta `latest.json` de este repositorio. Si existe una versión superior, descarga el instalador publicado en GitHub Releases y lo ejecuta. Los datos del usuario se conservan en `%APPDATA%\MIDI Premium 2`.

## Publicar una nueva versión

1. Cambiar `app_source/app/version.py`.
2. Actualizar `latest.json`, `CHANGELOG.md` y los números de versión del instalador/build.
3. Commit y push a `main`.
4. Crear/push del tag `vX.Y.Z`.
5. GitHub Actions genera el portable, el instalador y la Release.
