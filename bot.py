import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.filters.command import CommandObject
from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Callable, Dict, Any, List
from db import get_user, init_db, add_user, remove_user, list_users, add_book, get_books_by_subject, search_books, count_search_books, get_all_subjects, get_book, get_books_count, get_all_books, Book, test_connection, close_pool, increment_unauthorized_attempts, is_user_blocked, unblock_user, get_unauthorized_user, update_book_subject, update_book_description, delete_book, get_users_by_role, get_system_stats
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
from aiogram.types import BufferedInputFile

# Configuración de Logging (Consola y Archivo)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("error_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UploadStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_author = State()
    waiting_for_category = State()
    waiting_for_description = State()
    waiting_for_document = State()

class SearchStates(StatesGroup):
    waiting_for_search_term = State()

class AddUserStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_user_id = State()
    waiting_for_user_role = State()

class RemoveUserStates(StatesGroup):
    waiting_for_user_id_to_remove = State()

class UnblockUserStates(StatesGroup):
    waiting_for_user_id_to_unblock = State()

class EditBookStates(StatesGroup):
    waiting_for_edit_choice = State()
    waiting_for_new_subject = State()
    waiting_for_new_description = State()

class DeleteBookStates(StatesGroup):
    waiting_for_delete_confirmation = State()

class SendBookStates(StatesGroup):
    waiting_for_recipients = State()
    waiting_for_note = State()

# Pagination settings
CATEGORIES_PER_PAGE = 6
BOOKS_PER_PAGE = 5

# Helper function to format file size
def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancelar Operación", callback_data="cancel_op")]
    ])

# Helper function to translate roles to Spanish
def translate_role(role: str) -> str:
    translations = {'admin': 'Administrador', 'reader': 'Lector'}
    return translations.get(role, role.title())

# Helper function to format dates (handles both datetime objects and strings from SQLite)
def format_date(date_value) -> str:
    if date_value is None:
        return 'N/A'
    if isinstance(date_value, str):
        # SQLite returns dates as strings
        try:
            return date_value[:16]  # Return first 16 chars: "YYYY-MM-DD HH:MM"
        except:
            return date_value
    try:
        return date_value.strftime('%Y-%m-%d %H:%M')
    except:
        return str(date_value)

async def generate_users_report_pdf():
    """Generate PDF report with registered users"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    story.append(Paragraph("Reporte de Usuarios - Sistema BRIMBF5", title_style))
    story.append(Spacer(1, 12))

    # Generation date
    story.append(Paragraph(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 24))

    # Users Section
    story.append(Paragraph("Usuarios Registrados", styles['Heading2']))
    story.append(Spacer(1, 12))

    users = await list_users()
    if users:
        data = [['Nombre', 'ID Telegram', 'Rol', 'Fecha Autorización', 'Autorizado Por']]
        for user in users:
            data.append([
                user.username or 'Sin nombre',
                str(user.user_id_telegram),
                translate_role(user.role),
                format_date(user.authorized_at),
                user.authorized_by or 'N/A'
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No hay usuarios registrados.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

async def generate_documents_report_pdf():
    """Generate PDF report with all documents"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    story.append(Paragraph("Reporte de Documentos - Sistema BRIMBF5", title_style))
    story.append(Spacer(1, 12))

    # Generation date
    story.append(Paragraph(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 24))

    # Documents Section
    story.append(Paragraph("Documentos en la Biblioteca", styles['Heading2']))
    story.append(Spacer(1, 12))

    # Get all books (assuming max 10000 for now)
    books = await get_all_books(offset=0, limit=10000)
    if books:
        data = [['Título', 'Autor', 'Categoría', 'Descripción', 'Tamaño', 'Fecha Subida', 'Subido Por']]
        for book in books:
            size_str = format_file_size(book.size_bytes) if book.size_bytes else "N/A"
            data.append([
                book.title,
                book.author,
                book.subject.title() if book.subject else 'Sin categoría',
                book.description or 'Sin descripción',
                size_str,
                format_date(book.uploaded_at),
                str(book.uploaded_by) if book.uploaded_by else 'N/A'
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No hay documentos en la biblioteca.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here":
    logger.error("❌ ERROR: El BOT_TOKEN no está configurado correctamente en el archivo .env")
    logger.error("Búscalo en @BotFather y ponlo en el archivo .env")
    exit(1)

try:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
except Exception as e:
    logger.error(f"❌ ERROR al inicializar el bot: {e}")
    exit(1)

class AuthorizationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable,
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Handle both Message and CallbackQuery events
        user_id = event.from_user.id
        user = await get_user(user_id)

        if user:
            data['user'] = user
            return await handler(event, data)
        else:
            # Check if user is blocked
            if await is_user_blocked(user_id):
                # Don't respond to blocked users
                return

            # For messages, check if it's /start
            if hasattr(event, 'text') and event.text and event.text.startswith('/start'):
                data['user'] = None
                return await handler(event, data)
            # For callback queries, answer with error and increment attempts
            elif hasattr(event, 'answer'):
                blocked = await increment_unauthorized_attempts(user_id)
                if blocked:
                    await event.answer("🚫 Acceso Bloqueado. Contacta a un administrador.", show_alert=True)
                else:
                    await event.answer("Acceso denegado. No estás autorizado.", show_alert=True)
                return
            # For other messages - increment attempts
            else:
                blocked = await increment_unauthorized_attempts(user_id)
                if blocked:
                    await event.reply("🚫 **Acceso Bloqueado**\n\nHas excedido el límite de intentos. Contacta a un administrador para ser autorizado.", parse_mode="Markdown")
                else:
                    user_attempts = await get_unauthorized_user(user_id)
                    attempts = user_attempts.attempts if user_attempts else 0
                    if attempts == 1:
                        await event.reply(
                            f"🚫 **Acceso Denegado**\n\n"
                            f"No estás autorizado para usar este bot.\n\n"
                            f"**Si sigues intentando, te va a bloquear.**\n\n"
                            f"Solicita autorización a un administrador.",
                            parse_mode="Markdown"
                        )
                    else:
                        attempts_left = 2 - attempts
                        await event.reply(
                            f"🚫 **Acceso Denegado**\n\n"
                            f"No estás autorizado para usar este bot.\n\n"
                            f"**Intentos restantes:** {attempts_left}\n\n"
                            f"Solicita autorización a un administrador.",
                            parse_mode="Markdown"
                        )
            return

dp.message.middleware(AuthorizationMiddleware())
dp.callback_query.middleware(AuthorizationMiddleware())

@dp.message(Command("start"))
async def start_command(message: Message, user=None):
    user_id = message.from_user.id
    
    if user and user.role == 'admin':
        # Get system stats for admin dashboard
        stats = await get_system_stats()

        # Admin persistent keyboard
        reply_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📋 Documentos"), KeyboardButton(text="📚 Todos los Documentos")],
                [KeyboardButton(text="👥 Gestionar"), KeyboardButton(text="📤 Subir"), KeyboardButton(text="📊 Reporte")],
                [KeyboardButton(text="🔍 Buscar"), KeyboardButton(text="ℹ️ Info")],
                [KeyboardButton(text="🆘 Ayuda")]
            ],
            resize_keyboard=True,
            input_field_placeholder="Selecciona una opción..."
        )

        # Build stats message
        stats_msg = "**BRIMBF5 - Panel de Administración**\n\n"
        stats_msg += "✅ **Acceso de Administrador confirmado**\n\n"
        stats_msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        stats_msg += f"📚 **Documentos:** {stats.get('total_books', 0)}\n"

        if stats.get('books_by_subject'):
            top_subjects = list(stats['books_by_subject'].items())[:3]  # Top 3 categories
            for subject, count in top_subjects:
                stats_msg += f"   • {subject.title()}: {count}\n"

        stats_msg += f"👥 **Usuarios:** {stats.get('total_users', 0)}\n"
        if stats.get('users_by_role'):
            for role, count in stats['users_by_role'].items():
                role_name = translate_role(role)
                stats_msg += f"   • {role_name}: {count}\n"

        if stats.get('recent_uploads', 0) > 0:
            stats_msg += f"📈 **Subidas recientes:** {stats['recent_uploads']} (30 días)\n"

        stats_msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        stats_msg += "_Use el menú inferior para navegar rápidamente._"

        await message.reply(stats_msg, reply_markup=reply_keyboard, parse_mode="Markdown")
    elif user:
        # Regular user persistent keyboard
        reply_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📋 Documentos"), KeyboardButton(text="📚 Todos los Documentos")],
                [KeyboardButton(text="🔍 Buscar"), KeyboardButton(text="ℹ️ Info")],
                [KeyboardButton(text="🆘 Ayuda")]
            ],
            resize_keyboard=True,
            input_field_placeholder="Selecciona una opción..."
        )
        await message.reply(
            "**BRIMBF5 - Sistema de Información Militar**\n\n"
            "✅ Acceso autorizado.\n\n"
            "Use el menú inferior para navegar.",
            reply_markup=reply_keyboard,
            parse_mode="Markdown"
        )
    else:
        # Unauthorized user - no persistent keyboard
        await message.reply(
            f"**BRIMBF5 - Sistema de Información Militar**\n\n"
            f"❌ Acceso denegado. Nivel de autorización insuficiente.\n\n"
            f"ID de usuario: `{user_id}`\n\n"
            f"Solicite autorización a un administrador superior.",
            parse_mode="Markdown"
        )

# Handle quick reply button messages
@dp.message(F.text == "📋 Documentos")
async def documents_button(message: Message):
    await show_categories_page(message, page=0, is_new_message=True)

@dp.message(F.text == "📚 Todos los Documentos")
async def all_documents_button(message: Message):
    await show_all_books_page(message, page=0, is_new_message=True)

async def show_categories_page(message_or_callback, page: int = 0, is_new_message: bool = False):
    """Display paginated categories view"""
    subjects = await get_all_subjects()
    total_subjects = len(subjects)
    total_pages = max(1, (total_subjects + CATEGORIES_PER_PAGE - 1) // CATEGORIES_PER_PAGE)
    
    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * CATEGORIES_PER_PAGE
    end_idx = min(start_idx + CATEGORIES_PER_PAGE, total_subjects)
    page_subjects = subjects[start_idx:end_idx]
    
    keyboard = []
    
    # Add "All Categories" button at the top
    keyboard.append([InlineKeyboardButton(text="📂 Todas las categorías", callback_data=f"all_categories_0")])
    
    # Add category buttons in rows of 2
    row = []
    for sub in page_subjects:
        row.append(InlineKeyboardButton(text=f"📁 {sub.title()}", callback_data=f"genre_{sub}_0"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # Pagination controls
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"cat_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Siguiente ➡️", callback_data=f"cat_page_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
    
    # Page indicator and back button
    page_indicator = f"📄 Página {page + 1}/{total_pages}" if total_pages > 1 else ""
    keyboard.append([InlineKeyboardButton(text="🔙 Volver al Inicio", callback_data="back_to_start")])
    
    text = f"**📚 Acceso a Documentos Clasificados**\n\n"
    text += f"🗂️ {total_subjects} categorías disponibles\n"
    if page_indicator:
        text += f"{page_indicator}\n"
    text += "\n_Seleccione una categoría para ver los documentos:_"
    
    if is_new_message:
        await message_or_callback.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

async def show_all_books_page(message_or_callback, page: int = 0, is_new_message: bool = False):
    """Display paginated view of all books"""
    total_books = await get_books_count()
    total_pages = max(1, (total_books + BOOKS_PER_PAGE - 1) // BOOKS_PER_PAGE)

    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))

    start_idx = page * BOOKS_PER_PAGE
    books = await get_all_books(offset=start_idx, limit=BOOKS_PER_PAGE)

    keyboard = []

    if not books:
        text = "**📚 Todos los Documentos**\n\n📭 No hay documentos disponibles en la biblioteca.\n\n_Use /uploadbook para agregar contenido._"
        keyboard.append([InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")])
    else:
        result = "**📚 Todos los Documentos**\n\n"
        result += f"📊 {total_books} documento(s) en total\n"
        if total_pages > 1:
            result += f"📄 Página {page + 1}/{total_pages}\n"
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for book in books:
            size_str = format_file_size(book.size_bytes) if book.size_bytes else ""
            result += f"📄 **{book.title}**\n   _por {book.author}_ {f'({size_str})' if size_str else ''}\n"
            if book.subject:
                result += f"   📁 {book.subject.title()}\n"
            result += "\n"
            keyboard.append([InlineKeyboardButton(text=f"👁️ Ver: {book.title[:30]}{'...' if len(book.title) > 30 else ''}", callback_data=f"detail_{book.book_id}")])

        # Pagination controls
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"all_books_{page - 1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Siguiente ➡️", callback_data=f"all_books_{page + 1}"))
        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")])

        text = result

    if is_new_message:
        await message_or_callback.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

async def show_search_results_page(message_or_callback, query: str, page: int = 0, is_new_message: bool = False):
    """Display paginated search results"""
    total_books = await count_search_books(query)
    total_pages = max(1, (total_books + BOOKS_PER_PAGE - 1) // BOOKS_PER_PAGE)

    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))

    start_idx = page * BOOKS_PER_PAGE
    books = await search_books(query, offset=start_idx, limit=BOOKS_PER_PAGE)

    keyboard = []

    if not books:
        text = f"🔍 **Resultados de Búsqueda**\n\n📝 Término: _{query}_\n\n📭 No se encontraron documentos."
        keyboard.append([InlineKeyboardButton(text="🔙 Volver al Inicio", callback_data="back_to_start")])
    else:
        result = f"🔍 **Resultados de Búsqueda**\n\n"
        result += f"📝 Término: _{query}_\n"
        result += f"📊 {total_books} resultado(s) encontrado(s)\n"
        if total_pages > 1:
            result += f"📄 Página {page + 1}/{total_pages}\n"
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for book in books:
            size_str = format_file_size(book.size_bytes) if book.size_bytes else ""
            result += f"📄 **{book.title}**\n   _por {book.author}_ {f'({size_str})' if size_str else ''}\n"
            if book.subject:
                result += f"   📁 {book.subject.title()}\n"
            result += "\n"
            keyboard.append([InlineKeyboardButton(text=f"👁️ Ver: {book.title[:30]}{'...' if len(book.title) > 30 else ''}", callback_data=f"detail_{book.book_id}")])

        # Pagination controls
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"search_page_{query.replace(' ', '_')}_{page - 1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Siguiente ➡️", callback_data=f"search_page_{query.replace(' ', '_')}_{page + 1}"))
        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton(text="🔙 Volver al Inicio", callback_data="back_to_start")])

        text = result

    if is_new_message:
        await message_or_callback.reply(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

@dp.message(F.text == "👥 Gestionar")
async def manage_button(message: Message, user=None):
    if not user or user.role != 'admin':
        await message.reply("Solo admins pueden acceder")
        return
    users = await list_users()
    user_list = "\n".join(f"• {u.username or 'Sin nombre'} (ID: {u.user_id_telegram}) - {translate_role(u.role)}" for u in users) if users else "No hay personal autorizado."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Autorizar Usuario", callback_data="add_user_prompt")],
        [InlineKeyboardButton(text="➖ Revocar Autorización", callback_data="remove_user_prompt")],
        [InlineKeyboardButton(text="🔓 Desbloquear Usuario", callback_data="unblock_user_prompt")],
        [InlineKeyboardButton(text="🔄 Actualizar Lista", callback_data="manage_users")]
    ])
    await message.reply(f"**Panel de Control Administrativo**\n\n**Personal Autorizado:**\n{user_list}\n\nSeleccione operación:", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(F.text == "🔍 Buscar")
async def search_button(message: Message, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_search_term)
    await message.reply("**🔍 Búsqueda en Base de Datos**\n\nEnvía los términos de búsqueda.\n\n_Ejemplo: manual infantería_", parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Info")
async def info_button(message: Message):
    await info_command(message)

@dp.message(F.text == "🆘 Ayuda")
async def help_button(message: Message, user=None):
    await help_command(message, user)

@dp.message(F.text == "📊 Reporte")
async def report_button(message: Message, user=None):
    if not user or user.role != 'admin':
        await message.reply("🚫 Solo administradores pueden generar reportes.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Reporte de Usuarios", callback_data="report_users")],
        [InlineKeyboardButton(text="📚 Reporte de Documentos", callback_data="report_documents")],
        [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_report")]
    ])

    await message.reply(
        "**📊 Selecciona el tipo de reporte**\n\n"
        "Elige qué información deseas exportar:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def help_command(message: Message, user=None):
    base_commands = "**Comandos del Sistema:**\n/start - Reiniciar interfaz\n/help - Mostrar esta ayuda\n/info - Información del sistema BRIMBF5\n/search <término> - Buscar documentos"
    if user and user.role == 'admin':
        admin_commands = "\n\n**Comandos Administrativos:**\n/adduser <user_id> <role> - Autorizar nuevo usuario\n/removeuser <user_id> - Revocar autorización\n/listusers - Listar personal autorizado\n/upload - Subir documento paso a paso\n\n**Gestión Guiada:**\nUsa el menú '👥 Gestionar' para agregar/revocar usuarios de forma intuitiva."
        await message.reply(f"**Manual de Operaciones BRIMBF5**\n\n{base_commands}{admin_commands}\n\n**Subida Rápida:**\nEnvía archivo con comentario: `Título | Autor | Categoría`", parse_mode="Markdown")
    else:
        await message.reply(f"**Manual de Operaciones BRIMBF5**\n\n{base_commands}", parse_mode="Markdown")

@dp.message(Command("info"))
async def info_command(message: Message):
    await message.reply("**BRIMBF5 - Sistema de Información Militar Clasificada**\n\nSistema seguro para acceso a documentación militar. Protocolos de seguridad implementados.\n\n**Capacidades:**\n- Base de datos clasificada\n- Búsqueda avanzada\n- Distribución segura de archivos\n- Control de acceso por roles\n\nOperación restringida a personal autorizado.", parse_mode="Markdown")

@dp.message(Command("adduser"))
async def adduser_command(message: Message, command: CommandObject, user=None):
    if not user or user.role != 'admin':
        await message.reply("🚫 Solo administradores pueden agregar usuarios.")
        return
    args = command.args
    if not args:
        await message.reply(
            "📝 **Uso del comando:**\n\n"
            "`/adduser <user_id> <role> <username>`\n\n"
            "**Roles disponibles:**\n"
            "• `admin` - Acceso completo\n"
            "• `lector` - Solo lectura\n\n"
            "_Ejemplo:_ `/adduser 123456789 lector JuanPerez`",
            parse_mode="Markdown"
        )
        return
    try:
        parts = args.split()
        if len(parts) < 2:
            raise ValueError("Faltan argumentos")
        
        user_id = int(parts[0])
        role_str = parts[1]
        username = parts[2] if len(parts) > 2 else None
        
        if role_str not in ['admin', 'reader', 'lector']:
            await message.reply(
                "⚠️ **Rol inválido**\n\n"
                "Los roles disponibles son:\n"
                "• `admin` - Acceso completo\n"
                "• `lector` - Solo lectura",
                parse_mode="Markdown"
            )
            return
        # Convert 'lector' to 'reader' for database storage
        if role_str == 'lector':
            role_str = 'reader'
        await add_user(user_id, username, role_str, message.from_user.id)
        await message.reply(
            f"🎉 **¡Usuario Autorizado Exitosamente!**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Nombre:** {username or 'Sin nombre'}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🔑 **Rol:** {translate_role(role_str)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ El usuario ahora tiene acceso al sistema.",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.reply(
            "❌ **Formato incorrecto**\n\n"
            "Uso: `/adduser <user_id> <role> <username>`\n\n"
            "_Ejemplo:_ `/adduser 123456789 lector JuanPerez`",
            parse_mode="Markdown"
        )

@dp.message(Command("removeuser"))
async def removeuser_command(message: Message, command: CommandObject, user=None):
    if not user or user.role != 'admin':
        await message.reply("🚫 Solo administradores pueden remover usuarios.")
        return
    args = command.args
    if not args:
        await message.reply(
            "📝 **Uso del comando:**\n\n"
            "`/removeuser <user_id>`\n\n"
            "_Ejemplo:_ `/removeuser 123456789`",
            parse_mode="Markdown"
        )
        return
    try:
        user_id = int(args)
        await remove_user(user_id)
        await message.reply(
            f"✅ **Autorización Revocada**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **ID:** `{user_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🚫 El usuario ya no tiene acceso al sistema.",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.reply(
            "❌ **Formato incorrecto**\n\n"
            "Uso: `/removeuser <user_id>`\n\n"
            "_Ejemplo:_ `/removeuser 123456789`",
            parse_mode="Markdown"
        )

@dp.message(Command("listusers"))
async def listusers_command(message: Message, user=None):
    if not user or user.role != 'admin':
        await message.reply("Solo admins pueden listar usuarios.")
        return
    users = await list_users()
    if not users:
        await message.reply("No hay usuarios autorizados.")
        return
    user_list = "\n".join(f"{u.user_id_telegram}: {translate_role(u.role)}" for u in users)
    await message.reply(f"Usuarios autorizados:\n{user_list}")

@dp.message(Command("upload"))
async def start_upload(message: Message, state: FSMContext, user=None):
    if not user or user.role != 'admin':
        await message.reply("🚫 Solo administradores pueden subir documentos.")
        return
    await state.set_state(UploadStates.waiting_for_title)
    await message.reply("📄 **Subida de Documento - Paso 1/5**\n\nEnvía el **título** del documento.", parse_mode="Markdown", reply_markup=get_cancel_keyboard())

@dp.message(F.text == "📤 Subir")
async def upload_button(message: Message, state: FSMContext, user=None):
    if not user or user.role != 'admin':
        await message.reply("🚫 Solo administradores pueden subir documentos.")
        return
    await state.set_state(UploadStates.waiting_for_title)
    await message.reply("📄 **Subida de Documento - Paso 1/5**\n\nEnvía el **título** del documento.", parse_mode="Markdown", reply_markup=get_cancel_keyboard())

@dp.message(UploadStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 3:
        await message.reply("⚠️ **Título muy corto**\n\nPor favor, envía un título descriptivo (mínimo 3 caracteres).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return

    await state.update_data(title=message.text.strip())
    await state.set_state(UploadStates.waiting_for_author)
    await message.reply("👤 **Paso 2/5**\n\nEnvía el **autor** del documento.", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.message(UploadStates.waiting_for_author)
async def process_author(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 3:
        await message.reply("⚠️ **Nombre muy corto**\n\nPor favor, envía un nombre de autor válido (mínimo 3 caracteres).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return

    await state.update_data(author=message.text.strip())
    await state.set_state(UploadStates.waiting_for_category)
    await message.reply("📁 **Paso 3/5**\n\nEnvía la **categoría** del documento.", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.message(UploadStates.waiting_for_category)
async def process_category(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 3:
        await message.reply("⚠️ **Categoría inválida**\n\nPor favor, envía una categoría válida (mínimo 3 caracteres).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return

    await state.update_data(subject=message.text.strip().lower())
    await state.set_state(UploadStates.waiting_for_description)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ Omitir Descripción", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Cancelar Operación", callback_data="cancel_op")]
    ])
    await message.reply("📝 **Paso 4/5 - Descripción (Opcional)**\n\nEnvía una **descripción** del documento o presiona 'Omitir'.", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "skip_description")
async def skip_description_callback(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await state.set_state(UploadStates.waiting_for_document)
    await callback.message.edit_text("📎 **Paso 5/5**\n\nEnvía el **archivo** del documento (PDF, DOC, etc).", parse_mode="Markdown")
    await callback.answer("✅ Descripción omitida")

@dp.message(UploadStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip() if message.text else None)
    await state.set_state(UploadStates.waiting_for_document)
    await message.reply("📎 **Paso 5/5**\n\nEnvía el **archivo** del documento (PDF, DOC, etc).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.message(UploadStates.waiting_for_document)
async def process_document_upload(message: Message, state: FSMContext, user=None):
    if not message.document:
        await message.reply("⚠️ **Esperaba un documento**\n\nPor favor, adjunta el archivo que deseas subir.\nSi deseas cancelar, usa el botón abajo.", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return

    data = await state.get_data()
    try:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        file_size = message.document.file_size

        await add_book(file_id, file_unique_id, data['title'], data['author'], data['subject'], file_size, user.user_id_telegram, data.get('description'))

        size_str = format_file_size(file_size) if file_size else ""
        success_message = f"🎉 **¡Documento Guardado Exitosamente!**\n\n"
        success_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        success_message += f"📄 **Título:** {data['title']}\n"
        success_message += f"👤 **Autor:** {data['author']}\n"
        success_message += f"📁 **Categoría:** {data['subject'].title()}\n"
        if data.get('description'):
            success_message += f"📝 **Descripción:** {data['description'][:50]}{'...' if len(data.get('description', '')) > 50 else ''}\n"
        success_message += f"📦 **Tamaño:** {size_str}\n"
        success_message += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        success_message += f"✅ El documento está ahora disponible en la biblioteca."

        await message.reply(success_message, parse_mode="Markdown")
        await state.clear()
    except Exception as e:
        await message.reply(f"❌ **Error al guardar el documento**\n\nDetalles: {str(e)}", parse_mode="Markdown")
        await state.clear()

@dp.message(Command("cancel"))
async def cancel_upload(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.reply("❌ **Operación cancelada**\n\nPuedes empezar de nuevo.", parse_mode="Markdown")
    else:
        await message.reply("No hay nada que cancelar.")

@dp.callback_query(lambda c: c.data == "cancel_op")
async def cancel_op_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ **Operación cancelada**", parse_mode="Markdown")
    await callback.answer("Operación cancelada")

@dp.message(SearchStates.waiting_for_search_term)
async def process_search_term(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.reply("Por favor, envía un término de búsqueda válido.")
        return

    total_books = await count_search_books(query)
    await state.clear()  # Clear state after processing

    if total_books == 0:
        await message.reply(
            f"🔍 **Búsqueda:** _{query}_\n\n"
            f"📭 No se encontraron documentos que coincidan.\n\n"
            f"💡 _Intenta con otros términos._",
            parse_mode="Markdown"
        )
        return

    # If more than 5 results, use pagination
    if total_books > 5:
        await show_search_results_page(message, query, page=0, is_new_message=True)
    else:
        # Show all results directly (legacy behavior for small results)
        books = await search_books(query)
        result = f"🔍 **Resultados de Búsqueda**\n\n"
        result += f"📝 Término: _{query}_\n"
        result += f"📊 {len(books)} resultado(s) encontrado(s)\n\n"
        result += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"

        keyboard = []
        for book in books:
            size_str = format_file_size(book.size_bytes) if book.size_bytes else ""
            result += f"📄 **{book.title}**\n"
            result += f"   _por {book.author}_ {f'({size_str})' if size_str else ''}\n\n"
            keyboard.append([InlineKeyboardButton(text=f"👁️ Ver: {book.title[:30]}{'...' if len(book.title) > 30 else ''}", callback_data=f"detail_{book.book_id}")])

        keyboard.append([InlineKeyboardButton(text="🔙 Volver al Inicio", callback_data="back_to_start")])
        await message.reply(result, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

@dp.message(AddUserStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    username = message.text.strip()
    if not username or len(username) < 2:
        await message.reply("⚠️ **Nombre muy corto**\n\nPor favor, envía un nombre de usuario válido (mínimo 2 caracteres).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return
    
    await state.update_data(username=username)
    await state.set_state(AddUserStates.waiting_for_user_id)
    await message.reply(f"**Paso 2/3 - Nombre: {username}**\n\nEnvía el **ID de Telegram** del usuario.\n\n_Ejemplo: 123456789_", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.message(AddUserStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(user_id=user_id)
        await state.set_state(AddUserStates.waiting_for_user_role)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Administrador", callback_data="role_admin")],
            [InlineKeyboardButton(text="👤 Lector", callback_data="role_reader")],
            [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_add_user")]
        ])
        await message.reply(f"**Paso 3/3 - ID: {user_id}**\n\nSelecciona el **rol** para este usuario:", reply_markup=keyboard, parse_mode="Markdown")
    except ValueError:
        await message.reply("❌ **ID inválido**\n\nEl ID debe ser un número entero.\n\n_Ejemplo: 123456789_", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("role_"))
async def process_user_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]  # admin or reader
    data = await state.get_data()
    
    # Validate that we have the required data
    if 'user_id' not in data:
        await state.clear()
        await callback.message.edit_text(
            "❌ **Error: Datos de sesión perdidos**\n\n"
            "Por favor, inicia el proceso de nuevo.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Intentar de Nuevo", callback_data="add_user_prompt")],
                [InlineKeyboardButton(text="👥 Volver", callback_data="manage_users")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer("Sesión expirada")
        return
    
    user_id = data['user_id']
    username = data.get('username')

    try:
        await add_user(user_id, username, role, callback.from_user.id)
        await state.clear()
        await callback.message.edit_text(
            f"🎉 **¡Usuario Autorizado Exitosamente!**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Nombre:** {username or 'Sin nombre'}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🔑 **Rol:** {translate_role(role)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ El usuario ahora tiene acceso al sistema.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Gestionar Más Usuarios", callback_data="manage_users")],
                [InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")]
            ]),
            parse_mode="Markdown"
        )
    except ValueError as e:
        await state.clear()
        await callback.message.edit_text(
            f"❌ **Error:** {str(e)}\n\n"
            f"El usuario ya existe o hay un problema.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Intentar de Nuevo", callback_data="add_user_prompt")],
                [InlineKeyboardButton(text="👥 Volver", callback_data="manage_users")]
            ]),
            parse_mode="Markdown"
        )
    await callback.answer()

@dp.message(RemoveUserStates.waiting_for_user_id_to_remove)
async def process_remove_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await remove_user(user_id)
        await state.clear()
        await message.reply(
            f"✅ **Autorización Revocada**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **ID:** `{user_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🚫 El usuario ya no tiene acceso al sistema.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Gestionar Más Usuarios", callback_data="manage_users")],
                [InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")]
            ]),
            parse_mode="Markdown"
        )
    except ValueError:
        await message.reply("❌ **ID inválido**\n\nPor favor, envía un número válido de ID de usuario.\n\n_Ejemplo: 123456789_", parse_mode="Markdown")
    except Exception as e:
        await state.clear()
        await message.reply(
            f"❌ **Error:** {str(e)}\n\n"
            f"El usuario no existe o hay un problema.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Intentar de Nuevo", callback_data="remove_user_prompt")],
                [InlineKeyboardButton(text="👥 Volver", callback_data="manage_users")]
            ]),
            parse_mode="Markdown"
        )

@dp.message(UnblockUserStates.waiting_for_user_id_to_unblock)
async def process_unblock_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await unblock_user(user_id)
        await state.clear()
        await message.reply(
            f"🔓 **Usuario Desbloqueado**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **ID:** `{user_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ El usuario puede intentar acceder nuevamente.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Gestionar Más Usuarios", callback_data="manage_users")],
                [InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")]
            ]),
            parse_mode="Markdown"
        )
    except ValueError:
        await message.reply("❌ **ID inválido**\n\nPor favor, envía un número válido de ID de usuario.\n\n_Ejemplo: 123456789_", parse_mode="Markdown")
    except Exception as e:
        await state.clear()
        await message.reply(
            f"❌ **Error:** {str(e)}\n\n"
            f"No se pudo desbloquear o el usuario no está bloqueado.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Intentar de Nuevo", callback_data="unblock_user_prompt")],
                [InlineKeyboardButton(text="👥 Volver", callback_data="manage_users")]
            ]),
            parse_mode="Markdown"
        )

@dp.message(F.document)
async def handle_document(message: Message, user=None):
    if not user or user.role != 'admin':
        return

    if not message.caption:
        await message.reply(
            "📄 **Subida de Documento**\n\n"
            "Para subir un documento, añade en el comentario:\n\n"
            "`Título | Autor | Categoría`\n\n"
            "_Ejemplo:_\n"
            "`Manual de Combate | Ejército | Operativo`",
            parse_mode="Markdown"
        )
        return

    try:
        parts = message.caption.split("|")
        if len(parts) != 3:
            await message.reply(
                "⚠️ **Formato incorrecto**\n\n"
                "Use: `Título | Autor | Categoría`\n\n"
                "_Ejemplo:_\n"
                "`Manual de Combate | Ejército | Operativo`",
                parse_mode="Markdown"
            )
            return

        title = parts[0].strip()
        author = parts[1].strip()
        subject = parts[2].strip().lower()
        
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        file_size = message.document.file_size
        size_str = format_file_size(file_size) if file_size else "Desconocido"
        
        await add_book(file_id, file_unique_id, title, author, subject, file_size, message.from_user.id)
        
        success_message = f"🎉 **¡Documento Guardado Exitosamente!**\n\n"
        success_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        success_message += f"📄 **Título:** {title}\n"
        success_message += f"👤 **Autor:** {author}\n"
        success_message += f"📁 **Categoría:** {subject.title()}\n"
        success_message += f"📦 **Tamaño:** {size_str}\n"
        success_message += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        success_message += f"✅ El documento está ahora disponible en la biblioteca."
        
        await message.reply(success_message, parse_mode="Markdown")
        
    except Exception as e:
        await message.reply(
            f"❌ **Error al guardar el documento**\n\n"
            f"_Detalles:_ {str(e)}\n\n"
            f"Por favor, intente nuevamente.",
            parse_mode="Markdown"
        )

# Category pagination callback
@dp.callback_query(lambda c: c.data.startswith("cat_page_"))
async def category_page_callback(callback: CallbackQuery):
    page = int(callback.data.split("_")[2])
    await show_categories_page(callback, page=page, is_new_message=False)
    await callback.answer()

# All categories view with pagination
@dp.callback_query(lambda c: c.data.startswith("all_categories_"))
async def all_categories_callback(callback: CallbackQuery):
    page = int(callback.data.split("_")[2])
    subjects = await get_all_subjects()
    total_subjects = len(subjects)
    total_pages = max(1, (total_subjects + 10 - 1) // 10)  # 10 categories per page in "all" view

    page = max(0, min(page, total_pages - 1))
    start_idx = page * 10
    end_idx = min(start_idx + 10, total_subjects)
    page_subjects = subjects[start_idx:end_idx]

    keyboard = []
    for sub in page_subjects:
        keyboard.append([InlineKeyboardButton(text=f"📁 {sub.title()}", callback_data=f"genre_{sub}_0")])

    # Pagination controls
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"all_categories_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Siguiente ➡️", callback_data=f"all_categories_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text="🔙 Volver", callback_data="cat_page_0")])

    text = f"**📂 Todas las Categorías**\n\n"
    text += f"📊 Mostrando {start_idx + 1}-{end_idx} de {total_subjects}\n"
    text += f"📄 Página {page + 1}/{total_pages}\n\n"
    text += "_Seleccione una categoría:_"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

# All books view with pagination
@dp.callback_query(lambda c: c.data.startswith("all_books_"))
async def all_books_callback(callback: CallbackQuery):
    page = int(callback.data.split("_")[2])
    await show_all_books_page(callback, page=page, is_new_message=False)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("search_page_"))
async def search_page_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    query_encoded = "_".join(parts[2:-1])  # Everything between search_page_ and the page number
    query = query_encoded.replace("_", " ")
    page = int(parts[-1])
    await show_search_results_page(callback, query, page=page, is_new_message=False)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "explore")
async def explore_callback(callback: CallbackQuery):
    await show_categories_page(callback, page=0, is_new_message=False)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("genre_"))
async def genre_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    subject = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    
    books = await get_books_by_subject(subject)
    total_books = len(books)
    total_pages = max(1, (total_books + BOOKS_PER_PAGE - 1) // BOOKS_PER_PAGE)
    
    page = max(0, min(page, total_pages - 1))
    
    if not books:
        await callback.message.edit_text(
            f"**📁 Categoría: {subject.title()}**\n\n"
            f"📭 No hay documentos disponibles en esta categoría.\n\n"
            f"_Use /uploadbook para agregar contenido._",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Volver a Categorías", callback_data="explore")],
                [InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")]
            ]),
            parse_mode="Markdown"
        )
    else:
        start_idx = page * BOOKS_PER_PAGE
        end_idx = min(start_idx + BOOKS_PER_PAGE, total_books)
        page_books = books[start_idx:end_idx]
        
        result = f"**📁 {subject.title()}**\n\n"
        result += f"📚 {total_books} documento(s) disponible(s)\n"
        if total_pages > 1:
            result += f"📄 Página {page + 1}/{total_pages}\n"
        result += "\n"
        
        keyboard = []
        for book in page_books:
            size_str = format_file_size(book.size_bytes) if book.size_bytes else ""
            result += f"📄 **{book.title}**\n   _por {book.author}_ {f'({size_str})' if size_str else ''}\n\n"
            keyboard.append([InlineKeyboardButton(text=f"👁️ Ver detalles: {book.title[:30]}{'...' if len(book.title) > 30 else ''}", callback_data=f"detail_{book.book_id}")])
        
        # Pagination controls for books
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"genre_{subject}_{page - 1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Siguiente ➡️", callback_data=f"genre_{subject}_{page + 1}"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton(text="🔙 Volver a Categorías", callback_data="explore")])
        keyboard.append([InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")])
        
        await callback.message.edit_text(result, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

# Book detail view
@dp.callback_query(lambda c: c.data.startswith("detail_"))
async def book_detail_callback(callback: CallbackQuery):
    book_id = int(callback.data.split("_")[1])
    book = await get_book(book_id)
    user = await get_user(callback.from_user.id)

    if book:
        size_str = format_file_size(book.size_bytes) if book.size_bytes else "Desconocido"

        detail_text = f"**📖 {book.title}**\n\n"
        detail_text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        detail_text += f"👤 **Autor:** {book.author}\n"
        detail_text += f"📁 **Categoría:** {book.subject.title() if book.subject else 'Sin categoría'}\n"
        detail_text += f"📦 **Tamaño:** {size_str}\n"
        if book.description:
            detail_text += f"📝 **Descripción:** {book.description}\n"
        detail_text += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        detail_text += f"_Documento clasificado disponible para descarga._\n\n"
        detail_text += f"💡 _Presione el botón de descarga para obtener el archivo._"

        keyboard_buttons = [
            [InlineKeyboardButton(text="📥 Descargar Documento", callback_data=f"download_{book.book_id}")],
            [InlineKeyboardButton(text=f"🔙 Volver a {book.subject.title() if book.subject else 'Categorías'}", callback_data=f"genre_{book.subject}_0" if book.subject else "explore")],
            [InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")]
        ]

        # Add admin buttons if user is admin
        if user and user.role == 'admin':
            keyboard_buttons.insert(1, [
                InlineKeyboardButton(text="📤 Enviar Documento", callback_data=f"send_book_{book.book_id}"),
                InlineKeyboardButton(text="✏️ Editar Documento", callback_data=f"edit_book_{book.book_id}"),
                InlineKeyboardButton(text="🗑️ Eliminar Documento", callback_data=f"delete_book_{book.book_id}")
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(detail_text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer("📖 Mostrando detalles del documento")
    else:
        await callback.answer("❌ Error: Documento no encontrado.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("edit_book_"))
async def edit_book_callback(callback: CallbackQuery):
    book_id = int(callback.data.split("_")[2])
    book = await get_book(book_id)
    user = await get_user(callback.from_user.id)

    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    if book:
        text = f"**✏️ Editar Documento**\n\n**{book.title}**\n\n¿Qué deseas editar?"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📁 Cambiar Categoría", callback_data=f"edit_choice_{book_id}_subject")],
            [InlineKeyboardButton(text="📝 Cambiar Descripción", callback_data=f"edit_choice_{book_id}_description")],
            [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"detail_{book_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
    else:
        await callback.answer("Documento no encontrado.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("edit_choice_"))
async def edit_choice_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    book_id = int(parts[2])
    choice = parts[3]
    book = await get_book(book_id)
    user = await get_user(callback.from_user.id)

    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    if choice == "subject":
        await state.set_state(EditBookStates.waiting_for_new_subject)
        await state.update_data(book_id=book_id)
        text = f"**📁 Cambiar Categoría**\n\nDocumento: **{book.title}**\n\nEnvía la nueva categoría:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"detail_{book_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    elif choice == "description":
        await state.set_state(EditBookStates.waiting_for_new_description)
        await state.update_data(book_id=book_id)
        text = f"**📝 Cambiar Descripción**\n\nDocumento: **{book.title}**\n\nEnvía la nueva descripción (o 'ninguna' para eliminar):"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏩ Omitir Descripción", callback_data=f"skip_edit_description_{book_id}")],
            [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"detail_{book_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("skip_edit_description_"))
async def skip_edit_description_callback(callback: CallbackQuery, state: FSMContext):
    book_id = int(callback.data.split("_")[3])
    await update_book_description(book_id, None)
    await state.clear()
    await callback.message.edit_text("✅ **Descripción eliminada**\n\nVolviendo al detalle del documento...", parse_mode="Markdown")
    # Re-trigger detail view
    await book_detail_callback(callback)
    await callback.answer("Descripción eliminada")

@dp.message(EditBookStates.waiting_for_new_subject)
async def process_new_subject(message: Message, state: FSMContext):
    new_subject = message.text.strip()
    if not new_subject:
        await message.reply("⚠️ **Categoría inválida**\n\nPor favor, envía una categoría válida.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_edit")]
        ]), parse_mode="Markdown")
        return

    data = await state.get_data()
    book_id = data['book_id']
    await update_book_subject(book_id, new_subject)
    await state.clear()
    await message.reply(f"✅ **Categoría actualizada**\n\nNueva categoría: {new_subject.title()}", parse_mode="Markdown")

@dp.message(EditBookStates.waiting_for_new_description)
async def process_new_description(message: Message, state: FSMContext):
    new_description = message.text.strip() if message.text else None
    data = await state.get_data()
    book_id = data['book_id']
    await update_book_description(book_id, new_description)
    await state.clear()
    await message.reply("✅ **Descripción actualizada**" + (f"\n\nNueva descripción: {new_description}" if new_description else ""), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("delete_book_"))
async def delete_book_callback(callback: CallbackQuery):
    book_id = int(callback.data.split("_")[2])
    book = await get_book(book_id)
    user = await get_user(callback.from_user.id)

    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    if book:
        text = f"**🗑️ Eliminar Documento**\n\n**{book.title}**\n\n¿Estás seguro de que quieres eliminar este documento?\n\n⚠️ **Esta acción no se puede deshacer.**"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Sí, eliminar", callback_data=f"delete_confirm_{book_id}")],
            [InlineKeyboardButton(text="❌ No, cancelar", callback_data=f"detail_{book_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
    else:
        await callback.answer("Documento no encontrado.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("delete_confirm_"))
async def delete_confirm_callback(callback: CallbackQuery):
    book_id = int(callback.data.split("_")[2])
    user = await get_user(callback.from_user.id)

    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    try:
        await delete_book(book_id)
        await callback.message.edit_text("✅ **Documento eliminado**\n\nEl documento ha sido removido de la biblioteca.", parse_mode="Markdown")
    except Exception as e:
        await callback.message.edit_text(f"❌ **Error al eliminar**\n\n{e}", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("send_book_"))
async def send_book_callback(callback: CallbackQuery):
    book_id = int(callback.data.split("_")[2])
    book = await get_book(book_id)
    user = await get_user(callback.from_user.id)

    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    if book:
        text = f"**📤 Enviar Documento**\n\n**{book.title}**\n\n¿A quién quieres enviar este documento?"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Solo Admins", callback_data=f"send_to_admin_{book_id}")],
            [InlineKeyboardButton(text="👤 Solo Lectores", callback_data=f"send_to_reader_{book_id}")],
            [InlineKeyboardButton(text="👥 Ambos", callback_data=f"send_to_both_{book_id}")],
            [InlineKeyboardButton(text="🎯 Personal", callback_data=f"send_to_personal_{book_id}")],
            [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"detail_{book_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
    else:
        await callback.answer("Documento no encontrado.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("send_to_"))
async def send_to_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    target = parts[2]
    book_id = int(parts[3])
    book = await get_book(book_id)
    user = await get_user(callback.from_user.id)

    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    if target == "personal":
        await state.set_state(SendBookStates.waiting_for_recipients)
        await state.update_data(book_id=book_id, target=target)
        text = f"**🎯 Envío Personal**\n\nDocumento: **{book.title}**\n\nEnvía los usernames (o IDs si no tienen username) separados por coma.\n\n_Ejemplo: JuanPerez, MariaLopez, 123456789_"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"detail_{book_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        # For admin, reader, both - send immediately
        await state.update_data(book_id=book_id)
        await send_document_to_users(book, target, callback, state)
    await callback.answer()

async def send_document_to_users(book: Book, target: str, callback_or_message, state: FSMContext = None, note: str = None, users: List = None):
    """Send document to selected users"""
    if users is None:
        users = await get_users_by_role(target)
    if not users:
        if hasattr(callback_or_message, 'message'):
            await callback_or_message.message.edit_text("❌ **No hay destinatarios disponibles**", parse_mode="Markdown")
        else:
            await callback_or_message.reply("❌ **No hay destinatarios disponibles**", parse_mode="Markdown")
        return

    size_str = format_file_size(book.size_bytes) if book.size_bytes else "Desconocido"
    caption = f"📄 **{book.title}**\n"
    caption += f"👤 Autor: {book.author}\n"
    if book.subject:
        caption += f"📁 Categoría: {book.subject.title()}\n"
    caption += f"📦 Tamaño: {size_str}\n"
    if book.description:
        caption += f"📝 Descripción: {book.description}\n"
    if note:
        caption += f"📤 Nota: {note}\n"

    sent_count = 0
    for u in users:
        try:
            await callback_or_message.bot.send_document(
                chat_id=u.user_id_telegram,
                document=book.file_id_telegram,
                caption=caption,
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Error sending to user {u.user_id_telegram}: {e}")

    success_text = f"✅ **Documento enviado exitosamente**\n\nEnviado a {sent_count} de {len(users)} destinatarios."

    # Ask for note if not already provided
    if note is None:
        if state:
            await state.update_data(target=target, users=users if users else [])
            await state.set_state(SendBookStates.waiting_for_note)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Agregar Nota", callback_data="add_note")],
            [InlineKeyboardButton(text="✅ Enviar sin Nota", callback_data="skip_note")]
        ])
        success_text += "\n\n¿Quieres agregar una nota?"
        if hasattr(callback_or_message, 'message'):
            await callback_or_message.message.edit_text(success_text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await callback_or_message.reply(success_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        if state:
            await state.clear()
        if hasattr(callback_or_message, 'message'):
            await callback_or_message.message.edit_text(success_text, parse_mode="Markdown")
        else:
            await callback_or_message.reply(success_text, parse_mode="Markdown")

@dp.message(SendBookStates.waiting_for_recipients)
async def process_recipients(message: Message, state: FSMContext):
    recipients_input = message.text.strip()
    if not recipients_input:
        await message.reply("⚠️ **Input vacío**\n\nPor favor, envía los usernames o IDs separados por coma.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_send")]
        ]), parse_mode="Markdown")
        return

    data = await state.get_data()
    book_id = data['book_id']
    book = await get_book(book_id)

    # Parse recipients
    recipient_strings = [r.strip() for r in recipients_input.split(',') if r.strip()]
    users = []

    for r in recipient_strings:
        u = None
        # Try by username first
        all_users = await list_users()
        for user in all_users:
            if user.username and user.username.lower() == r.lower():
                u = user
                break
        # If not found, try by ID
        if not u:
            try:
                user_id = int(r)
                u = await get_user(user_id)
            except ValueError:
                pass
        if u:
            users.append(u)
        else:
            await message.reply(f"❌ **Usuario no encontrado:** {r}\n\nVerifica el username o ID.", parse_mode="Markdown")
            return

    if not users:
        await message.reply("❌ **No se encontraron usuarios válidos**", parse_mode="Markdown")
        return

    # Send to selected users
    await send_document_to_users(book, None, message, state, users=users)

@dp.message(SendBookStates.waiting_for_note)
async def process_note(message: Message, state: FSMContext):
    note = message.text.strip()
    data = await state.get_data()
    book_id = data['book_id']
    target = data.get('target')
    users = data.get('users')
    book = await get_book(book_id)

    await send_document_to_users(book, target, message, state, note=note, users=users)

@dp.callback_query(lambda c: c.data == "add_note")
async def add_note_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    book = await get_book(data['book_id'])
    await callback.message.edit_text(f"**📝 Agregar Nota**\n\nDocumento: **{book.title}**\n\nEnvía la nota que quieres agregar:", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "skip_note")
async def skip_note_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    book_id = data['book_id']
    target = data.get('target')
    users = data.get('users')
    book = await get_book(book_id)

    await send_document_to_users(book, target, callback, state, note="", users=users)
    await callback.answer("Nota omitida")

@dp.callback_query(lambda c: c.data.startswith("download_"))
async def download_callback(callback: CallbackQuery):
    book_id = int(callback.data.split("_")[1])
    book = await get_book(book_id)
    
    if book:
        size_str = format_file_size(book.size_bytes) if book.size_bytes else ""
        caption = f"📄 **{book.title}**\n"
        caption += f"👤 Autor: {book.author}\n"
        if book.subject:
            caption += f"📁 Categoría: {book.subject.title()}\n"
        if size_str:
            caption += f"📦 Tamaño: {size_str}\n"
        caption += f"\n✅ _Descarga completada exitosamente_"
        
        await callback.message.answer_document(document=book.file_id_telegram, caption=caption, parse_mode="Markdown")
        await callback.answer("🎉 ¡Documento enviado exitosamente!")
    else:
        await callback.answer("❌ Error: Documento no encontrado.", show_alert=True)

@dp.message(Command("search"))
async def search_command(message: Message, command: CommandObject):
    query = command.args
    if not query:
        await message.reply(
            "🔍 **Búsqueda en Base de Datos**\n\n"
            "Uso: `/search <términos de búsqueda>`\n\n"
            "_Ejemplo:_ `/search manual infantería`",
            parse_mode="Markdown"
        )
        return
    books = await search_books(query)
    if not books:
        await message.reply(
            f"🔍 **Búsqueda:** _{query}_\n\n"
            f"📭 No se encontraron documentos que coincidan con la búsqueda.\n\n"
            f"💡 _Intente con otros términos o revise las categorías disponibles._",
            parse_mode="Markdown"
        )
        return
    
    result = f"🔍 **Resultados de Búsqueda**\n\n"
    result += f"📝 Término: _{query}_\n"
    result += f"📊 {len(books)} resultado(s) encontrado(s)\n\n"
    result += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    keyboard = []
    for book in books[:5]:
        size_str = format_file_size(book.size_bytes) if book.size_bytes else ""
        result += f"📄 **{book.title}**\n"
        result += f"   _por {book.author}_ {f'({size_str})' if size_str else ''}\n\n"
        keyboard.append([InlineKeyboardButton(text=f"👁️ Ver: {book.title[:30]}{'...' if len(book.title) > 30 else ''}", callback_data=f"detail_{book.book_id}")])
    
    if len(books) > 5:
        result += f"\n_...y {len(books) - 5} resultado(s) más_\n"
    
    keyboard.append([InlineKeyboardButton(text="🔙 Volver al Inicio", callback_data="back_to_start")])
    await message.reply(result, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "manage_users")
async def manage_users_callback(callback: CallbackQuery, user=None):
    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado. Nivel de autorización insuficiente.")
        return
    users = await list_users()
    user_list = "\n".join(f"• {u.username or 'Sin nombre'} (ID: {u.user_id_telegram}) - {translate_role(u.role)}" for u in users) if users else "No hay personal autorizado."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Autorizar Usuario", callback_data="add_user_prompt")],
        [InlineKeyboardButton(text="➖ Revocar Autorización", callback_data="remove_user_prompt")],
        [InlineKeyboardButton(text="🔓 Desbloquear Usuario", callback_data="unblock_user_prompt")],
        [InlineKeyboardButton(text="🔄 Actualizar Lista", callback_data="manage_users")],
        [InlineKeyboardButton(text="🔙 Volver", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(f"**Panel de Control Administrativo**\n\n**Personal Autorizado:**\n{user_list}\n\nSeleccione operación:", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "add_user_prompt")
async def add_user_prompt_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddUserStates.waiting_for_username)
    await callback.message.edit_text("**Autorizar Nuevo Usuario - Paso 1/3**\n\nEnvía el **nombre de usuario**.\n\n_Ejemplo: JuanPerez_", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_add_user")]
    ]), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_add_user")
async def cancel_add_user_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("**Operación cancelada**\n\nPuedes volver al panel administrativo.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Volver a Gestionar", callback_data="manage_users")]
    ]), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "remove_user_prompt")
async def remove_user_prompt_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RemoveUserStates.waiting_for_user_id_to_remove)
    await callback.message.edit_text("**Revocar Autorización - Paso 1/1**\n\nEnvía el **ID del usuario** a revocar.\n\n_Ejemplo: 123456789_", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_remove_user")]
    ]), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_remove_user")
async def cancel_remove_user_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("**Operación cancelada**\n\nPuedes volver al panel administrativo.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Volver a Gestionar", callback_data="manage_users")]
    ]), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "unblock_user_prompt")
async def unblock_user_prompt_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UnblockUserStates.waiting_for_user_id_to_unblock)
    await callback.message.edit_text("**Desbloquear Usuario - Paso 1/1**\n\nEnvía el **ID del usuario** a desbloquear.\n\n_Ejemplo: 123456789_", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_remove_user")]  # Reuse cancel
    ]), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_start")
async def back_to_start_callback(callback: CallbackQuery, user=None):
    await start_command(callback.message, user)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "report_users")
async def report_users_callback(callback: CallbackQuery, user=None):
    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    await callback.message.edit_text("📊 **Generando reporte de usuarios...**\n\nEsto puede tomar unos momentos.", parse_mode="Markdown")

    try:
        pdf_buffer = await generate_users_report_pdf()
        buffered_file = BufferedInputFile(pdf_buffer.getvalue(), filename=f"reporte_usuarios_brimbf5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        await callback.message.answer_document(
            document=buffered_file,
            caption="📄 **Reporte de Usuarios - Sistema BRIMBF5**\n\nContiene información completa de todos los usuarios registrados.",
            parse_mode="Markdown"
        )
        await callback.message.delete()  # Remove the generating message
    except Exception as e:
        await callback.message.edit_text(f"❌ **Error al generar el reporte**\n\nDetalles: {str(e)}", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "report_documents")
async def report_documents_callback(callback: CallbackQuery, user=None):
    if not user or user.role != 'admin':
        await callback.answer("Acceso denegado.", show_alert=True)
        return

    await callback.message.edit_text("📊 **Generando reporte de documentos...**\n\nEsto puede tomar unos momentos.", parse_mode="Markdown")

    try:
        pdf_buffer = await generate_documents_report_pdf()
        buffered_file = BufferedInputFile(pdf_buffer.getvalue(), filename=f"reporte_documentos_brimbf5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        await callback.message.answer_document(
            document=buffered_file,
            caption="📄 **Reporte de Documentos - Sistema BRIMBF5**\n\nContiene información completa de todos los documentos en la biblioteca.",
            parse_mode="Markdown"
        )
        await callback.message.delete()  # Remove the generating message
    except Exception as e:
        await callback.message.edit_text(f"❌ **Error al generar el reporte**\n\nDetalles: {str(e)}", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_report")
async def cancel_report_callback(callback: CallbackQuery):
    await callback.message.edit_text("❌ **Operación cancelada**\n\nPuedes volver al menú principal.", parse_mode="Markdown")
    await callback.answer()

async def main():
    try:
        # Test database connection
        print("Testing database connection...")
        if not await test_connection():
            print("Database connection failed. Please check your database configuration.")
            return

        # Initialize database tables and indexes
        print("Initializing database...")
        await init_db()
        print("Database initialized successfully")

        # Set bot commands menu
        commands = [
            BotCommand(command="start", description="Iniciar el bot"),
            BotCommand(command="help", description="Mostrar ayuda"),
            BotCommand(command="info", description="Información del sistema"),
            BotCommand(command="search", description="Buscar documentos"),
            BotCommand(command="upload", description="Subir documento (admins)"),
            BotCommand(command="cancel", description="Cancelar subida"),
        ]
        await bot.set_my_commands(commands)
        print("Bot commands configured")

        # Check if webhook URL is provided for production
        webhook_url = os.getenv('WEBHOOK_URL')
        if webhook_url:
            print(f"Setting webhook to: {webhook_url}")
            await bot.set_webhook(url=webhook_url)
            print("Webhook configured for 24/7 operation")
        else:
            print("No WEBHOOK_URL found, starting polling (development mode)...")
            await dp.start_polling(bot)

    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error starting bot: {e}")
    finally:
        # Clean up database connections
        await close_pool()
        print("Database connections closed")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())