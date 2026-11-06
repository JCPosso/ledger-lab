# Ledger: laboratorio de aplicación transaccional en Azure

Paquete inicial del laboratorio. Siga la guía entregada por el docente: explica cada paso, y este
repositorio no se despliega ejecutando un solo comando.

| Carpeta | Contenido |
|---|---|
| `app/` | API FastAPI, interfaz web, pruebas y Dockerfile |
| `infra/bootstrap/` | Estado remoto e identidad para GitHub Actions |
| `infra/modules/` | Módulos `database`, `key_vault`, `container_app` y `stack` |
| `infra/environments/` | Raíces de `dev`, `prod` y `local` |
| `.github/workflows/` | Pipelines: `ci`, `publish-image`, `deploy`, `deploy-env` y `destroy` |
| `cost/` | Estimador de costos con la API pública de precios de Azure |
| `scripts/` | Consulta de regiones y pruebas contra un ambiente desplegado |
| `docs/` | Riesgos aceptados y uso opcional del emulador floci-az |
