# 📚 BiblioBot Beta - Sistema de Biblioteca Virtual

Versión completa del bot de biblioteca virtual para Telegram con interfaz moderna y PostgreSQL.

## ✨ Características

- 🔐 **Control de Acceso**: Sistema de autorización por roles (admin/reader) con bloqueo automático
- 📂 **Categorización Inteligente**: Organización de documentos por materias
- 🔍 **Búsqueda Avanzada**: Búsqueda por título, autor o categoría
- 📄 **Vista de Detalles**: Información completa antes de descargar
- 📱 **Interfaz Moderna**: Paginación, emojis y navegación intuitiva
- 🗄️ **Base de Datos PostgreSQL**: Almacenamiento robusto y escalable

## 🚀 Configuración Rápida (Para Nuevos Usuarios)

Sigue estos pasos en orden para no tener errores:

### 1. Requisitos del Sistema
- **Python Recomendado**: **3.12** (es la más compatible). 
- *Nota*: Si usas **3.14**, asegúrate de tener instaladas las "C++ Build Tools" de Windows.

### 2. Preparar el Entorno
1. Descarga el código.
2. Abre una terminal en la carpeta del proyecto.
3. Ejecuta: `pip install -r requirements.txt`

### 3. Configurar Credenciales
1. Copia el archivo `.env.example` y cámbiale el nombre a `.env`. (En Windows: `copy .env.example .env`)
2. Abre el archivo `.env` con un bloc de notas y pon tu `BOT_TOKEN` y tu `ADMIN_IDS`.
3. Si usas PostgreSQL (Supabase/Neon), pon tu URL en `POSTGRES_URL`. Si no, deja todo como está y se creará una base de datos local automáticamente.

### 4. Iniciar el Bot (MÉTODO RECOMENDADO)
Simplemente haz doble clic en el archivo:
👉 **`iniciar_bot.bat`**

Este archivo hará todo por ti: verificará Python, instalará las librerías necesarias y encenderá el bot.

### 5. Iniciar manualmente (Alternativa)
Si prefieres usar la terminal:
```bash
python bot.py
```

## 🖥️ Despliegue 24/7 en VPS

### Requisitos
- VPS Ubuntu/Debian
- Dominio con SSL (opcional para polling, necesario para webhook)

### Pasos de Despliegue
1. **Configurar VPS:**
   ```bash
   chmod +x deploy.sh
   sudo ./deploy.sh
   ```

2. **Configurar Dominio:**
   - Editar `nginx.conf` con tu dominio
   - Configurar DNS apuntando al VPS
   - Instalar SSL: `certbot --nginx -d tu_dominio.com`

3. **Configurar Variables:**
   ```bash
   # En .env del servidor
   WEBHOOK_URL=https://tu_dominio.com/webhook
   POSTGRES_URL=postgresql://biblio_bot_user:password@localhost:5432/biblio_bot
   ```

4. **Iniciar Servicios:**
   ```bash
   sudo systemctl enable biblio_bot nginx
   sudo systemctl start biblio_bot nginx
   ```

### Monitoreo
- Logs: `journalctl -u biblio_bot -f`
- Estado: `systemctl status biblio_bot`
- Health check: `curl https://tu_dominio.com/health`

## 📋 Variables de Entorno (.env)

```env
# Telegram Bot
BOT_TOKEN=tu_token_de_telegram

# PostgreSQL (URL completa - recomendado para Supabase, Neon, etc.)
# Ejemplo: postgresql://usuario:password@host:5432/neondb
POSTGRES_URL=tu_url_aqui

# O configuración individual
DB_HOST=localhost
DB_PORT=5432
DB_NAME=biblio_bot
DB_USER=postgres
DB_PASSWORD=tu_password

# Admin Configuration (Tu ID de Telegram, consíguelo con @userinfobot)
ADMIN_IDS=123456789
```

## 🎯 Comandos Disponibles

### Comandos de Usuario
- `/start` - Iniciar bot y mostrar menú principal
- `/help` - Mostrar ayuda y comandos disponibles
- `/info` - Información del sistema
- `/search <término>` - Buscar documentos

### Comandos de Administrador
- `/adduser <id> <role>` - Autorizar nuevo usuario
- `/removeuser <id>` - Revocar autorización
- `/listusers` - Listar usuarios autorizados
- `/upload` - Subir documento paso a paso

### Menú Interactivo
- 📋 **Documentos** - Explorar biblioteca por categorías
- 👥 **Gestionar** - Panel administrativo (solo admins)
- 🔍 **Buscar** - Búsqueda rápida
- ℹ️ **Info** - Información del sistema

## 📖 Uso del Bot

### Para Usuarios
1. Inicia con `/start`
2. Usa el menú inferior para navegar
3. Selecciona "📋 Documentos" para ver categorías
4. Elige una categoría o usa "📂 Todas las categorías"
5. Selecciona un documento y presiona "👁️ Ver detalles"
6. Descarga el documento cuando estés listo

### Para Administradores
1. **Subida Paso a Paso (Recomendado):**
   - Envía `/upload`
   - Sigue las instrucciones del bot para ingresar título, autor, categoría y finalmente el archivo

2. **Subida Rápida:**
   - Envía el documento con comentario: `Título | Autor | Categoría`
   - _Ejemplo:_ `Manual de Combate | Ejército | Operativo`

3. Gestiona usuarios desde el menú "👥 Gestionar" (guiado paso a paso)

## 🛠️ Solución de Problemas (FAQ)

### ❓ El script de configuración dice que falta 'asyncpg' o 'aiogram'
**Solución**: No ejecutaste la instalación de dependencias. Ejecuta `pip install -r requirements.txt`.

### ❓ No puedo conectar a PostgreSQL
**Solución**: 
- El bot ahora intenta conectar con **SSL automáticamente** si falla la normal. 
- Verifica que en tu servicio (Supabase/Neon) hayas permitido las conexiones desde cualquier IP (0.0.0.0/0) si es necesario.

### ❓ El bot se cierra solo al iniciar
**Solución**: Revisa el archivo `.env`. Asegúrate de que el TOKEN no tenga espacios extra.

### ❓ Tengo Python 3.14 y me da error de 'C++ Build Tools'
**Solución**: Python 3.14 es muy nuevo. Lo más fácil es instalar **Python 3.12.x**. Si quieres seguir en 3.14, debes instalar el componente "Desktop development with C++" de Visual Studio Installer.

### ❓ Los reportes PDF no se generan
**Solución**: Asegúrate de tener `reportlab` instalado. El archivo `requirements.txt` ya lo incluye, pero si instalaste las dependencias manualmente, ejecuta: `pip install reportlab`

## 📊 Características Técnicas

- **Base de Datos**: PostgreSQL con connection pooling
- **Framework**: aiogram (asyncio)
- **Interfaz**: Inline keyboards con paginación
- **Seguridad**: Control de acceso por usuario
- **Rendimiento**: Índices optimizados para búsquedas

## 🔄 Actualizaciones

Esta versión incluye mejoras significativas en UI/UX:
- ✅ Paginación de categorías (6 por página)
- ✅ Vista detallada de documentos
- ✅ Emojis y animaciones en mensajes
- ✅ Navegación intuitiva
- ✅ Sistema robusto de base de datos
- ✅ Validación de entrada mejorada
- ✅ Botones de cancelación en workflows

## 🔒 Seguridad

- Las credenciales sensibles nunca se incluyen en el código fuente
- Los IDs de administradores se gestionan en el archivo `.env`
- El archivo `.env` está excluido del repositorio mediante `.gitignore`

---

**Desarrollado con ❤️ para sistemas de información militar**
