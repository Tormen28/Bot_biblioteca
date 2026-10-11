@echo off
TITLE BiblioBot - Lanzador Automatico
COLOR 0B

echo =========================================
echo    BIBLIOBOT - SISTEMA DE BIBLIOTECA
echo =========================================
echo.

:: 1. Verificar Python
echo [*] Verificando Python...
python --version
if %errorlevel% neq 0 (
    echo.
    echo [!] ERROR: Python no esta instalado o no se encuentra en el PATH.
    echo Por favor, instala Python 3.12 desde python.org
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit
)

:: 2. Verificar/Crear Entorno Virtual (VENV)
if not exist venv (
    echo [*] Creando entorno virtual (esto solo ocurre la primera vez)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [!] Error al crear el entorno virtual. Usando Python global...
        set PY_EXE=python
    ) else (
        set PY_EXE=venv\Scripts\python.exe
    )
) else (
    set PY_EXE=venv\Scripts\python.exe
)

:: 3. Verificar archivo .env
if not exist .env (
    echo [!] ADVERTENCIA: No se encontro el archivo .env
    if exist .env.example (
        echo Creando .env a partir de .env.example...
        copy .env.example .env
        echo.
        echo [!] IMPORTANTE: Edita el archivo .env con tu TOKEN y tu ID.
        echo Se abrira el Bloc de Notas. Guarda y cierra cuando termines.
        echo.
        pause
        notepad .env
        echo.
        echo Presiona una tecla cuando hayas guardado el archivo .env...
        pause
    ) else (
        echo [!] ERROR: No se encuentra .env ni .env.example
        pause
        exit
    )
)

:: 4. Instalar dependencias
echo.
echo [*] Instalando dependencias (puede tomar unos minutos la primera vez)...
%PY_EXE% -m pip install --upgrade pip >nul 2>&1
%PY_EXE% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] Hubo un problema al instalar las dependencias.
    pause
    exit
)

:: 5. Ejecutar configuracion de DB
echo.
echo [*] Verificando base de datos...
%PY_EXE% setup_db.py

:: 6. Registrar Admin(s) desde .env
echo.
echo [*] Registrando administrador(es)...
%PY_EXE% init_admin.py

:: 7. Iniciar el Bot
echo.
echo =========================================
echo    INICIANDO BOT...
echo    (Cierra esta ventana para detenerlo)
echo =========================================
echo.
%PY_EXE% bot.py

:: Si llegamos aqui, el bot se detuvo
echo.
echo =========================================
echo    EL BOT SE HA DETENIDO
echo =========================================
echo.
echo Si hubo un error, revisa el archivo 'error_log.txt'
echo.
pause
