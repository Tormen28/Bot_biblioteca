#!/bin/bash

# Script de despliegue para BiblioBot en Ubuntu/Debian VPS
# Ejecutar como root o con sudo

echo "🚀 Iniciando despliegue de BiblioBot..."

# Actualizar sistema
echo "📦 Actualizando sistema..."
apt update && apt upgrade -y

# Instalar dependencias
echo "🔧 Instalando dependencias..."
apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx certbot python3-certbot-nginx ufw

# Configurar PostgreSQL
echo "🐘 Configurando PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE biblio_bot;"
sudo -u postgres psql -c "CREATE USER biblio_bot_user WITH PASSWORD 'tu_password_seguro';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE biblio_bot TO biblio_bot_user;"

# Configurar firewall
echo "🔥 Configurando firewall..."
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

# Crear directorio del proyecto
echo "📁 Creando directorio del proyecto..."
mkdir -p /var/www/biblio_bot
cd /var/www/biblio_bot

# Aquí copiar los archivos del proyecto
# scp -r biblio_bot_beta/* user@server:/var/www/biblio_bot/

# Configurar entorno virtual
echo "🐍 Configurando entorno virtual..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar Nginx
echo "🌐 Configurando Nginx..."
cp nginx.conf /etc/nginx/sites-available/biblio_bot
ln -s /etc/nginx/sites-available/biblio_bot /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# Configurar SSL con Let's Encrypt
echo "🔒 Configurando SSL..."
# certbot --nginx -d your_domain.com

# Crear servicio systemd
echo "⚙️ Creando servicio systemd..."
cat > /etc/systemd/system/biblio_bot.service << EOF
[Unit]
Description=BiblioBot Telegram Service
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/biblio_bot
Environment="PATH=/var/www/biblio_bot/venv/bin"
ExecStart=/var/www/biblio_bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Iniciar servicios
echo "▶️ Iniciando servicios..."
systemctl daemon-reload
systemctl enable biblio_bot
systemctl start biblio_bot
systemctl enable nginx
systemctl start nginx

echo "✅ Despliegue completado!"
echo "📋 Próximos pasos:"
echo "1. Configurar dominio en nginx.conf"
echo "2. Ejecutar: certbot --nginx -d your_domain.com"
echo "3. Configurar WEBHOOK_URL en .env"
echo "4. Reiniciar el servicio: systemctl restart biblio_bot"