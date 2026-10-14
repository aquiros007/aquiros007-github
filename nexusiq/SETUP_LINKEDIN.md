# LinkedIn Auto-Publisher — Setup

## Cómo funciona

El workflow `.github/workflows/publish-linkedin.yml` se dispara automáticamente a las **7:00 AM Costa Rica (13:00 UTC)** de lunes a sábado. Lee el post del día del JSON de campaña correspondiente y lo publica en LinkedIn usando la API oficial.

## Configuración de secretos en GitHub (una sola vez)

Ve a tu repositorio en GitHub → **Settings → Secrets and variables → Actions → New repository secret**.

### `LINKEDIN_ACCESS_TOKEN`

Token OAuth 2.0 de LinkedIn. Se obtiene así:

1. Creá una app en [LinkedIn Developers](https://www.linkedin.com/developers/apps)
2. Habilitá los permisos: `w_member_social`, `r_basicprofile`
3. Generá un token OAuth con esos scopes (podés usar [OAuth 2.0 Playground](https://www.oauth.com/playground/) o Postman)
4. Copiá el `access_token` resultado

> El token expira cada **60 días**. Creá un recordatorio para renovarlo antes de que expire.

### `LINKEDIN_PERSON_URN`

El identificador de tu cuenta en LinkedIn. Para obtenerlo:

```bash
curl -H "Authorization: Bearer TU_ACCESS_TOKEN" \
     https://api.linkedin.com/v2/me
```

Buscá el campo `"id"` en la respuesta y formatealo como: `urn:li:person:TU_ID`

Ejemplo: si `"id": "AbCdEfG123"`, entonces el valor es `urn:li:person:AbCdEfG123`

---

## Estructura de los archivos de campaña

Cada semana tiene su propio JSON en `nexusiq/data/campaigns/`. El publicador busca el post cuyo campo `date` coincida con la fecha de hoy en hora de Costa Rica.

```json
{
  "id": "lun_19oct",
  "date": "2026-10-19",
  "status": "READY_TO_PUBLISH",
  "content": "Texto completo del post...\n\n#Hashtag1 #NexusIQ",
  "image": {
    "url": "https://..."
  }
}
```

### Estados del post

| Estado | Significado |
|--------|-------------|
| `READY_TO_PUBLISH` | Listo para publicar |
| `IMAGE_READY` | Imagen generada, texto listo |
| `PUBLISHED` | Publicado correctamente |
| `SKIPPED` | Omitido manualmente |

---

## Publicación manual

Podés disparar el workflow manualmente desde GitHub → **Actions → Publish LinkedIn Post → Run workflow**.

Opcionalmente podés especificar una fecha (`YYYY-MM-DD`) para republicar o probar un post específico.

---

## Renovación del token cada 60 días

Creá un recordatorio cada 55 días para renovar el token:
1. Generá un nuevo `access_token` con los mismos scopes
2. Actualizá el secreto `LINKEDIN_ACCESS_TOKEN` en GitHub Settings
3. El workflow usará el nuevo token en la próxima ejecución automáticamente
