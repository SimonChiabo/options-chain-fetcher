# Configuración de Schwab API

Guía paso a paso para obtener las credenciales y conectar el proyecto a la Schwab API.

---

## 1. Crear cuenta de desarrollador

1. Ir a [developer.schwab.com](https://developer.schwab.com)
2. Hacer clic en **"Log In"** → usar las mismas credenciales de la cuenta Schwab de trading
3. Aceptar los términos de uso de la API

---

## 2. Registrar una nueva aplicación

1. En el dashboard, ir a **"My Apps"** → **"Add a New App"**
2. Completar el formulario:
   - **App Name**: `options-chain-fetcher` (o el nombre que prefieras)
   - **App Type**: `Personal Use`
   - **Callback URL**: `https://127.0.0.1`  ← **importante, exactamente así**
   - **Description**: breve descripción del uso
3. Hacer submit y esperar aprobación (puede tardar minutos o hasta 24hs)

---

## 3. Obtener credenciales

Una vez aprobada la app:

1. En **"My Apps"**, hacer clic en la app creada
2. Copiar:
   - **App Key** → este es tu `SCHWAB_CLIENT_ID`
   - **Secret** → este es tu `SCHWAB_CLIENT_SECRET`

---

## 4. Configurar el proyecto

```bash
# Desde la raíz del proyecto
cp .env.example .env
```

Editar `.env`:

```
SCHWAB_CLIENT_ID=tu_app_key_aqui
SCHWAB_CLIENT_SECRET=tu_secret_aqui
SCHWAB_REDIRECT_URI=https://127.0.0.1
```

---

## 5. Primera autenticación

Al correr el proyecto por primera vez:

```bash
python main.py --symbol SPY --expiration 2025-06-20
```

1. Se abrirá el navegador con la pantalla de login de Schwab
2. Iniciar sesión con la cuenta de trading
3. Autorizar el acceso a la app
4. Schwab redirigirá a `https://127.0.0.1` → el navegador mostrará un error (es normal)
5. Copiar la URL completa del navegador y pegarla en la terminal cuando lo pida
6. El token se guarda en `token.pickle` → las siguientes ejecuciones son automáticas

---

## 6. Permisos necesarios

La app necesita acceso a:
- ✅ `MarketData` (lectura de cotizaciones y opciones)
- ❌ `Trading` (NO requerido, no activar para seguridad)

---

## 7. Notas importantes

- El token expira cada **30 minutos** pero `schwab-py` lo refresca automáticamente
- Si `token.pickle` se corrompe, borrarlo y volver al paso 5
- **Nunca commitear** `.env` ni `token.pickle` al repositorio (ya están en `.gitignore`)
- La API tiene límites de rate: ~120 requests/minuto para datos de mercado

---

## 8. Verificar conexión

```bash
python -c "from src.auth import get_client; c = get_client(); print('✅ Conexión OK')"
```
