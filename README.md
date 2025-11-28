# 📚 BiblioBot Beta - Sistema de Biblioteca Virtual

Versión completa del bot de biblioteca virtual para Telegram con interfaz moderna y PostgreSQL.

## ✨ Características

- 🔐 **Control de Acceso**: Sistema de autorización por roles (admin/reader) con bloqueo automático
- 📂 **Categorización Inteligente**: Organización de documentos por materias
- 🔍 **Búsqueda Avanzada**: Búsqueda por título, autor o categoría
- 📄 **Vista de Detalles**: Información completa antes de descargar
- 📱 **Interfaz Moderna**: Paginación, emojis y navegación intuitiva
- 🗄️ **Base de Datos PostgreSQL**: Almacenamiento robusto y escalable

## 🚀 Configuración Rápida

### 1. Crear Bot de Telegram
1. Ve a [@BotFather](https://t.me/botfather) en Telegram
2. Envía `/newbot` y sigue las instrucciones
3. Copia el TOKEN que te proporciona

### 2. Configurar Base de Datos PostgreSQL
```bash
# Opción A: PostgreSQL Local
createdb biblio_bot
createuser biblio_bot_user
psql -c "ALTER USER biblio_bot_user PASSWORD 'your_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE biblio_bot TO biblio_bot_user;"

# Opción B: Servicios en la Nube
# - Railway, Supabase, ElephantSQL, etc.
```

### 3. Configurar Variables de Entorno
```bash
cp .env.example .env
# Edita .env con tus credenciales
```

### 4. Instalar y Ejecutar
```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar base de datos
python setup_db.py

# Ejecutar bot (desarrollo)
python bot.py
```

## 🖥️ Despliegue 24/7 en VPS

### Requisitos
- VPS Ubuntu/Debian ($10-30/mes)
- Dominio con SSL
- PostgreSQL en el servidor

### Pasos de Despliegue
1. **Configurar VPS:**
   ```bash
   # Ejecutar script de despliegue
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

# PostgreSQL (URL completa - recomendado)
POSTGRES_URL=postgresql://usuario:password@host:puerto/database

# O configuración individual
DB_HOST=localhost
DB_PORT=5432
DB_NAME=biblio_bot
DB_USER=postgres
DB_PASSWORD=tu_password

# Admin Configuration (IDs separados por comas)
ADMIN_IDS=123456789,987654321
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

## 🛠️ Solución de Problemas

### Error de Conexión a Base de Datos
```bash
# Verificar configuración
python setup_db.py
```

### Bot No Responde
- Verifica que el TOKEN sea correcto
- Asegúrate de que el bot esté ejecutándose
- Revisa los logs en la consola

### Problemas de Dependencias
```bash
pip install --upgrade -r requirements.txt
```

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
