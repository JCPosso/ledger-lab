# Seguridad y excepciones de Checkov

Checkov termina sin fallos porque 18 controles pasan y 35 se omiten explícitamente. **Eso no significa
que esta configuración esté lista para producción real.** Cada omisión es un riesgo aceptado para no
consumir el crédito de estudiante, y su razón está junto al recurso, en un comentario
`#checkov:skip`. Los módulos se evalúan por cada uso, así que un mismo control puede contar varias veces.

## Lo que sí está protegido

- Solo HTTPS en la app y TLS 1.2 o superior en SQL y Storage, con validación del certificado de la base.
- Secretos en Key Vault, leídos con una identidad administrada de solo lectura.
- Estado de Terraform accesible solo con Entra ID, sin claves, y con versionado.
- Contraseñas con scrypt y sal por usuario. JWT con algoritmo fijo y expiración obligatoria.
- Imagen fijada por digest y ejecutada con un usuario sin privilegios.
- Montos enteros, restricción `CHECK` de saldo y claves de idempotencia únicas.

## Riesgos aceptados

| Riesgo | Controles | Para producción real |
|---|---|---|
| SQL y Key Vault expuestos a la red pública, y cualquier servicio de Azure pasa el firewall de SQL | `CKV_AZURE_113`, `CKV_AZURE_189`, `CKV_AZURE_109`, `CKV2_AZURE_34` | VNet con private endpoints |
| Sin private endpoints | `CKV2_AZURE_45`, `CKV2_AZURE_32`, `CKV2_AZURE_33` | Lo mismo |
| La app entra a SQL como administrador, con contraseña | `CKV2_AZURE_27` | Entra ID e identidad administrada con permisos mínimos |
| Sin auditoría ni evaluación de vulnerabilidades en SQL | `CKV_AZURE_23`, `CKV_AZURE_24`, `CKV2_AZURE_2` | Auditoría y Defender for SQL |
| Secretos sin vencimiento ni rotación | `CKV_AZURE_41` | Rotación automatizada |
| Sin redundancia de zona ni geográfica | `CKV_AZURE_229`, `CKV_AZURE_206` | Según el objetivo de recuperación |
| Sin registros de acceso al estado | `CKV_AZURE_33`, `CKV2_AZURE_21` | Diagnósticos hacia Log Analytics |
| Llaves administradas por Microsoft | `CKV2_AZURE_1` | Llaves propias si la norma lo exige |
| Sin registro inmutable de SQL Ledger | `CKV_AZURE_224` | Tablas Ledger si se necesita prueba criptográfica |
| Storage sin restricción de red | `CKV_AZURE_59` | Firewall o private endpoint |

## Otros límites de la aplicación

- No hay límite de intentos de login ni de registros: agrégalo antes de exponer la app a usuarios reales.
- El bono de bienvenida crea dinero al registrarse: es solo una ayuda para la demostración.
- El firewall `AllowAzureServices` deja pasar tráfico de otras suscripciones de Azure, y la contraseña
  de SQL es la barrera que queda.

## Ejecutar el análisis

```bash
uvx --python 3.12 checkov --config-file .checkov.yaml
```
