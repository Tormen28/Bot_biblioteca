import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.filters.command import CommandObject
from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Callable, Dict, Any
from db import get_user, init_db, add_user, remove_user, list_users, add_book, get_books_by_subject, search_books, get_all_subjects, get_book, get_books_count, get_all_books, Book, test_connection, close_pool, increment_unauthorized_attempts, is_user_blocked, unblock_user, get_unauthorized_user

class UploadStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_author = State()
    waiting_for_category = State()
    waiting_for_document = State()

class SearchStates(StatesGroup):
    waiting_for_search_term = State()

class AddUserStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_user_role = State()

class RemoveUserStates(StatesGroup):
    waiting_for_user_id_to_remove = State()

class UnblockUserStates(StatesGroup):
    waiting_for_user_id_to_unblock = State()

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

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
            # For callback queries, answer with error
            elif hasattr(event, 'answer'):
                await event.answer("Acceso denegado. No estás autorizado.", show_alert=True)
                return
            # For other messages - increment attempts
            else:
                blocked = await increment_unauthorized_attempts(user_id)
                if blocked:
                    await event.reply("🚫 **Acceso Bloqueado**\n\nHas excedido el límite de intentos. Contacta a un administrador para ser autorizado.", parse_mode="Markdown")
                else:
                    attempts_left = 3 - (await get_unauthorized_user(user_id)).attempts
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
        # Admin persistent keyboard
        reply_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📋 Documentos"), KeyboardButton(text="📚 Todos los Documentos")],
                [KeyboardButton(text="👥 Gestionar"), KeyboardButton(text="🔍 Buscar")],
                [KeyboardButton(text="ℹ️ Info"), KeyboardButton(text="🆘 Ayuda")]
            ],
            resize_keyboard=True,
            input_field_placeholder="Selecciona una opción..."
        )
        await message.reply(
            "**BRIMBF5 - Sistema de Información Militar**\n\n"
            "✅ Acceso de Administrador confirmado.\n\n"
            "Use el menú inferior para navegar rápidamente.",
            reply_markup=reply_keyboard,
            parse_mode="Markdown"
        )
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

@dp.message(F.text == "👥 Gestionar")
async def manage_button(message: Message, user=None):
    if not user or user.role != 'admin':
        await message.reply("Solo admins pueden acceder")
        return
    users = await list_users()
    user_list = "\n".join(f"• {u.user_id_telegram} - {u.role}" for u in users) if users else "No hay personal autorizado."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Autorizar Usuario", callback_data="add_user_prompt")],
        [InlineKeyboardButton(text="➖ Revocar Autorización", callback_data="remove_user_prompt")],
        [InlineKeyboardButton(text="🔓 Desbloquear Usuario", callback_data="unblock_user_prompt")],
        [InlineKeyboardButton(text=" Actualizar Lista", callback_data="manage_users")]
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
            "`/adduser <user_id> <role>`\n\n"
            "**Roles disponibles:**\n"
            "• `admin` - Acceso completo\n"
            "• `reader` - Solo lectura\n\n"
            "_Ejemplo:_ `/adduser 123456789 reader`",
            parse_mode="Markdown"
        )
        return
    try:
        user_id, role_str = args.split()
        user_id = int(user_id)
        if role_str not in ['admin', 'reader']:
            await message.reply(
                "⚠️ **Rol inválido**\n\n"
                "Los roles disponibles son:\n"
                "• `admin` - Acceso completo\n"
                "• `reader` - Solo lectura",
                parse_mode="Markdown"
            )
            return
        await add_user(user_id, role_str, message.from_user.id)
        await message.reply(
            f"🎉 **¡Usuario Autorizado Exitosamente!**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **ID:** `{user_id}`\n"
            f"🔑 **Rol:** {role_str.title()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ El usuario ahora tiene acceso al sistema.",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.reply(
            "❌ **Formato incorrecto**\n\n"
            "Uso: `/adduser <user_id> <role>`\n\n"
            "_Ejemplo:_ `/adduser 123456789 reader`",
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
    user_list = "\n".join(f"{u.user_id_telegram}: {u.role}" for u in users)
    await message.reply(f"Usuarios autorizados:\n{user_list}")

@dp.message(Command("upload"))
async def start_upload(message: Message, state: FSMContext, user=None):
    if not user or user.role != 'admin':
        await message.reply("🚫 Solo administradores pueden subir documentos.")
        return
    await state.set_state(UploadStates.waiting_for_title)
    await message.reply("📄 **Subida de Documento - Paso 1/4**\n\nEnvía el **título** del documento.", parse_mode="Markdown", reply_markup=get_cancel_keyboard())

@dp.message(UploadStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 3:
        await message.reply("⚠️ **Título muy corto**\n\nPor favor, envía un título descriptivo (mínimo 3 caracteres).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return

    await state.update_data(title=message.text.strip())
    await state.set_state(UploadStates.waiting_for_author)
    await message.reply("👤 **Paso 2/4**\n\nEnvía el **autor** del documento.", reply_markup=get_cancel_keyboard())

@dp.message(UploadStates.waiting_for_author)
async def process_author(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 3:
        await message.reply("⚠️ **Nombre muy corto**\n\nPor favor, envía un nombre de autor válido (mínimo 3 caracteres).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return

    await state.update_data(author=message.text.strip())
    await state.set_state(UploadStates.waiting_for_category)
    await message.reply("📁 **Paso 3/4**\n\nEnvía la **categoría** del documento.", reply_markup=get_cancel_keyboard())

@dp.message(UploadStates.waiting_for_category)
async def process_category(message: Message, state: FSMContext):
    if not message.text or len(message.text) < 3:
        await message.reply("⚠️ **Categoría inválida**\n\nPor favor, envía una categoría válida (mínimo 3 caracteres).", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        return

    await state.update_data(subject=message.text.strip().lower())
    await state.set_state(UploadStates.waiting_for_document)
    await message.reply("📎 **Paso 4/4**\n\nEnvía el **archivo** del documento (PDF, DOC, etc.).", reply_markup=get_cancel_keyboard())

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

        await add_book(file_id, file_unique_id, data['title'], data['author'], data['subject'], file_size, user.user_id_telegram)

        size_str = format_file_size(file_size) if file_size else ""
        success_message = f"🎉 **¡Documento Guardado Exitosamente!**\n\n"
        success_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        success_message += f"📄 **Título:** {data['title']}\n"
        success_message += f"👤 **Autor:** {data['author']}\n"
        success_message += f"📁 **Categoría:** {data['subject'].title()}\n"
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

    books = await search_books(query)
    await state.clear()  # Clear state after processing

    if not books:
        await message.reply(
            f"🔍 **Búsqueda:** _{query}_\n\n"
            f"📭 No se encontraron documentos que coincidan.\n\n"
            f"💡 _Intenta con otros términos._",
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

@dp.message(AddUserStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(user_id=user_id)
        await state.set_state(AddUserStates.waiting_for_user_role)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Admin", callback_data="role_admin")],
            [InlineKeyboardButton(text="👤 Reader", callback_data="role_reader")],
            [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel_add_user")]
        ])
        await message.reply(f"**Paso 2/2 - ID: {user_id}**\n\nSelecciona el **rol** para este usuario:", reply_markup=keyboard, parse_mode="Markdown")
    except ValueError:
        await message.reply("❌ **ID inválido**\n\nEl ID debe ser un número entero.\n\n_Ejemplo: 123456789_", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("role_"))
async def process_user_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]  # admin or reader
    data = await state.get_data()
    user_id = data['user_id']

    try:
        await add_user(user_id, role, callback.from_user.id)
        await state.clear()
        await callback.message.edit_text(
            f"🎉 **¡Usuario Autorizado Exitosamente!**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **ID:** `{user_id}`\n"
            f"🔑 **Rol:** {role.title()}\n"
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
    
    if book:
        size_str = format_file_size(book.size_bytes) if book.size_bytes else "Desconocido"
        
        detail_text = f"**📖 {book.title}**\n\n"
        detail_text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        detail_text += f"👤 **Autor:** {book.author}\n"
        detail_text += f"📁 **Categoría:** {book.subject.title() if book.subject else 'Sin categoría'}\n"
        detail_text += f"📦 **Tamaño:** {size_str}\n"
        detail_text += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        detail_text += f"📝 **Descripción:**\n"
        detail_text += f"_Documento clasificado disponible para descarga._\n\n"
        detail_text += f"💡 _Presione el botón de descarga para obtener el archivo._"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Descargar Documento", callback_data=f"download_{book.book_id}")],
            [InlineKeyboardButton(text=f"🔙 Volver a {book.subject.title() if book.subject else 'Categorías'}", callback_data=f"genre_{book.subject}_0" if book.subject else "explore")],
            [InlineKeyboardButton(text="🏠 Inicio", callback_data="back_to_start")]
        ])
        
        await callback.message.edit_text(detail_text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer("📖 Mostrando detalles del documento")
    else:
        await callback.answer("❌ Error: Documento no encontrado.", show_alert=True)

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
    user_list = "\n".join(f"• {u.user_id_telegram} - {u.role}" for u in users) if users else "No hay personal autorizado."
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
    await state.set_state(AddUserStates.waiting_for_user_id)
    await callback.message.edit_text("**Autorizar Nuevo Usuario - Paso 1/2**\n\nEnvía el **ID del usuario de Telegram**.\n\n_Ejemplo: 123456789_", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
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