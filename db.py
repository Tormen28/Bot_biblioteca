import os
import asyncio
import logging
from typing import Optional, List

try:
    import asyncpg
    from asyncpg import Pool
except ImportError:
    asyncpg = None
    Pool = None

try:
    import aiosqlite
except ImportError:
    aiosqlite = None
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_URL = os.getenv('POSTGRES_URL')
if not DB_URL:
    # Fallback for local development
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'biblio_bot')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

    DB_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# Global connection pool
_pool: Optional[Pool] = None
_use_sqlite = False

async def create_pool() -> Pool:
    """Create and return a connection pool"""
    global _pool, _use_sqlite

    if _pool is None:
        try:
            if asyncpg is None:
                raise ImportError("La librería 'asyncpg' no está instalada. Ejecuta: pip install asyncpg")

            # Intentar conexión con parámetros estándar
            try:
                _pool = await asyncpg.create_pool(
                    DB_URL,
                    min_size=1,
                    max_size=10,
                    command_timeout=60,
                    max_inactive_connection_lifetime=300,
                )
            except Exception as e:
                # Si falla, intentar con SSL (necesario para Supabase/Railway/Neon)
                logger.info(f"Conexión estándar falló, reintentando con SSL... ({e})")
                _pool = await asyncpg.create_pool(
                    DB_URL,
                    ssl=True,
                    min_size=1,
                    max_size=10,
                    command_timeout=60,
                    max_inactive_connection_lifetime=300,
                )
            
            logger.info("✅ PostgreSQL connection pool created successfully")
        except Exception as e:
            logger.warning(f"❌ PostgreSQL connection failed: {e}")
            if "ssl" in str(e).lower():
                logger.error("Sugerencia: Tu base de datos requiere SSL. Verifica tu POSTGRES_URL.")
            elif "authentication" in str(e).lower() or "password" in str(e).lower():
                logger.error("Sugerencia: Usuario o contraseña incorrectos en el archivo .env")
            elif "timeout" in str(e).lower() or "connection refused" in str(e).lower():
                logger.error("Sugerencia: No se pudo alcanzar el servidor. Verifica que no esté bloqueado por un firewall o que la IP esté permitida.")
            logger.info("🔄 Falling back to SQLite...")

            # Fallback to SQLite
            _use_sqlite = True
            try:
                if aiosqlite is None:
                    raise ImportError("La librería 'aiosqlite' no está instalada. Ejecuta: pip install aiosqlite")
                _pool = await aiosqlite.connect('biblio_bot.db')
                await _pool.execute('PRAGMA foreign_keys = ON')
                logger.info("✅ SQLite connection established successfully")
            except Exception as sqlite_e:
                logger.error(f"❌ Both PostgreSQL and SQLite failed: {sqlite_e}")
                raise sqlite_e
    return _pool

async def close_pool():
    """Close the connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("🔌 Database connection pool closed")

async def get_connection():
    """Get a connection from the pool"""
    if _pool is None:
        await create_pool()

    if _use_sqlite:
        # For SQLite, return the connection directly
        return _pool
    else:
        # For PostgreSQL, acquire from pool
        return await _pool.acquire()

async def release_connection(conn):
    """Release a connection back to the pool"""
    if _pool and not _use_sqlite:
        await _pool.release(conn)
    # For SQLite, no need to release (single connection)

async def init_db():
    """Initialize database tables if they do not exist"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            # SQLite compatible schema
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id_telegram INTEGER PRIMARY KEY,
                    username TEXT,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'reader')),
                    authorized_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    authorized_by TEXT
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS books (
                    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id_telegram TEXT UNIQUE NOT NULL,
                    file_hash_sha256 TEXT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    description TEXT,
                    size_bytes INTEGER NOT NULL,
                    url_external TEXT,
                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by INTEGER REFERENCES users(user_id_telegram)
                )
            ''')

            # Add description column if it doesn't exist (migration)
            try:
                await conn.execute('ALTER TABLE books ADD COLUMN description TEXT')
                await conn.commit()
            except:
                pass  # Column already exists

            # Create indexes for better performance
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_books_subject ON books(subject)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)')

            # Create unauthorized_users table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS unauthorized_users (
                    user_id_telegram INTEGER PRIMARY KEY,
                    attempts INTEGER DEFAULT 0,
                    last_attempt TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_blocked INTEGER DEFAULT 0
                )
            ''')

        else:
            # PostgreSQL schema
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id_telegram BIGINT PRIMARY KEY,
                    username TEXT,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'reader')),
                    authorized_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    authorized_by TEXT
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS books (
                    book_id SERIAL PRIMARY KEY,
                    file_id_telegram TEXT UNIQUE NOT NULL,
                    file_hash_sha256 TEXT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    description TEXT,
                    size_bytes BIGINT NOT NULL,
                    url_external TEXT,
                    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by BIGINT REFERENCES users(user_id_telegram)
                )
            ''')

            # Add description column if it doesn't exist (migration)
            try:
                await conn.execute('ALTER TABLE books ADD COLUMN description TEXT')
            except:
                pass  # Column already exists

            # Create indexes for better performance
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_books_subject ON books(subject)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)')

            # Create unauthorized_users table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS unauthorized_users (
                    user_id_telegram BIGINT PRIMARY KEY,
                    attempts INTEGER DEFAULT 0,
                    last_attempt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    is_blocked BOOLEAN DEFAULT FALSE
                )
            ''')

        logger.info("✅ Database tables initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    finally:
        await release_connection(conn)

async def test_connection() -> bool:
    """Test database connection"""
    try:
        conn = await get_connection()
        if _use_sqlite:
            cursor = await conn.execute('SELECT 1')
            result = await cursor.fetchone()
        else:
            result = await conn.fetchval('SELECT 1')
        await release_connection(conn)
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

class User:
    def __init__(self, user_id_telegram, username, role, authorized_at, authorized_by):
        self.user_id_telegram = user_id_telegram
        self.username = username
        self.role = role
        self.authorized_at = authorized_at
        self.authorized_by = authorized_by

async def get_user(user_id: int) -> Optional[User]:
    """Get user by Telegram ID"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute('SELECT * FROM users WHERE user_id_telegram = ?', (user_id,))
            row = await cursor.fetchone()
        else:
            row = await conn.fetchrow('SELECT * FROM users WHERE user_id_telegram = $1', user_id)

        if row:
            # Access by column name to avoid index issues
            return User(
                row['user_id_telegram'] if isinstance(row, dict) or hasattr(row, '__getitem__') and not isinstance(row, tuple) else row[0],
                row['username'] if isinstance(row, dict) or hasattr(row, '__getitem__') and not isinstance(row, tuple) else row[1],
                row['role'] if isinstance(row, dict) or hasattr(row, '__getitem__') and not isinstance(row, tuple) else row[2],
                row['authorized_at'] if isinstance(row, dict) or hasattr(row, '__getitem__') and not isinstance(row, tuple) else row[3],
                row['authorized_by'] if isinstance(row, dict) or hasattr(row, '__getitem__') and not isinstance(row, tuple) else row[4]
            )
        return None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None
    finally:
        await release_connection(conn)

async def add_user(user_id: int, username: Optional[str], role: str, authorized_by: Optional[str]):
    """Add a new user to the database"""
    if role not in ['admin', 'reader']:
        raise ValueError("Role must be 'admin' or 'reader'")

    # Convert authorized_by to string if it's an int
    authorized_by_str = str(authorized_by) if authorized_by is not None else None

    conn = await get_connection()
    try:
        if _use_sqlite:
            await conn.execute(
                'INSERT INTO users (user_id_telegram, username, role, authorized_by) VALUES (?, ?, ?, ?)',
                (user_id, username, role, authorized_by_str)
            )
            await conn.commit()
        else:
            await conn.execute(
                'INSERT INTO users (user_id_telegram, username, role, authorized_by) VALUES ($1, $2, $3, $4)',
                user_id, username, role, authorized_by_str
            )
        logger.info(f"User {user_id} ({username}) added with role {role}")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e) or "duplicate key value" in str(e):
            logger.warning(f"User {user_id} already exists")
            raise ValueError(f"User {user_id} already exists")
        logger.error(f"Error adding user {user_id}: {e}")
        raise
    finally:
        await release_connection(conn)

async def remove_user(user_id: int):
    """Remove a user from the database"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            await conn.execute('DELETE FROM users WHERE user_id_telegram = ?', (user_id,))
            await conn.commit()
        else:
            result = await conn.execute('DELETE FROM users WHERE user_id_telegram = $1', user_id)
            if result == 'DELETE 0':
                logger.warning(f"⚠️ User {user_id} not found for deletion")
        logger.info(f"✅ User {user_id} removed successfully")
    except Exception as e:
        logger.error(f"Error removing user {user_id}: {e}")
        raise
    finally:
        await release_connection(conn)

async def list_users() -> List[User]:
    """List all users in the database"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute('SELECT * FROM users ORDER BY authorized_at DESC')
            rows = await cursor.fetchall()
            # For SQLite, rows are tuples, need to handle by index
            return [User(row[0], row[1], row[2], row[3], row[4]) for row in rows]
        else:
            rows = await conn.fetch('SELECT * FROM users ORDER BY authorized_at DESC')
            return [User(row['user_id_telegram'], row['username'], row['role'], row['authorized_at'], row['authorized_by']) for row in rows]
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return []
    finally:
        await release_connection(conn)

async def get_users_by_role(role: str) -> List[User]:
    """Get users by role ('admin', 'reader', 'both')"""
    if role == 'both':
        return await list_users()
    elif role in ['admin', 'reader']:
        all_users = await list_users()
        return [u for u in all_users if u.role == role]
    else:
        return []

class Book:
    def __init__(self, book_id, file_id_telegram, file_hash_sha256, title, author, subject, description, size_bytes, url_external, uploaded_at=None, uploaded_by=None):
        self.book_id = book_id
        self.file_id_telegram = file_id_telegram
        self.file_hash_sha256 = file_hash_sha256
        self.title = title
        self.author = author
        self.subject = subject
        self.description = description
        self.size_bytes = size_bytes
        self.url_external = url_external
        self.uploaded_at = uploaded_at
        self.uploaded_by = uploaded_by

async def add_book(file_id: str, file_unique_id: str, title: str, author: str, subject: str, size_bytes: int, uploaded_by: Optional[int] = None, description: Optional[str] = None):
    """Add a new book to the database"""
    if not all([file_id, title, author, subject]):
        raise ValueError("Missing required fields: file_id, title, author, subject")

    conn = await get_connection()
    try:
        if _use_sqlite:
            await conn.execute(
                '''INSERT INTO books (file_id_telegram, file_hash_sha256, title, author, subject, description, size_bytes, uploaded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (file_id, file_unique_id, title, author, subject.lower().strip(), description, size_bytes, uploaded_by)
            )
            await conn.commit()
        else:
            await conn.execute(
                '''INSERT INTO books (file_id_telegram, file_hash_sha256, title, author, subject, description, size_bytes, uploaded_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)''',
                file_id, file_unique_id, title, author, subject.lower().strip(), description, size_bytes, uploaded_by
            )
        logger.info(f"✅ Book '{title}' added successfully by user {uploaded_by}")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e) or "duplicate key value" in str(e):
            logger.warning(f"⚠️ Book with file_id {file_id} already exists")
            raise ValueError(f"Book with file_id {file_id} already exists")
        logger.error(f"Error adding book '{title}': {e}")
        raise
    finally:
        await release_connection(conn)

async def get_books_by_subject(subject: str) -> List[Book]:
    """Get all books by subject (case-insensitive partial match)"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute(
                'SELECT * FROM books WHERE subject LIKE ? COLLATE NOCASE ORDER BY uploaded_at DESC',
                (f'%{subject}%',)
            )
            rows = await cursor.fetchall()
            return [Book(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10]) for row in rows]
        else:
            rows = await conn.fetch(
                'SELECT * FROM books WHERE subject ILIKE $1 ORDER BY uploaded_at DESC',
                f'%{subject}%'
            )
            return [Book(row['book_id'], row['file_id_telegram'], row['file_hash_sha256'],
                         row['title'], row['author'], row['subject'], row['description'], row['size_bytes'],
                         row['url_external'], row['uploaded_at'], row['uploaded_by']) for row in rows]
    except Exception as e:
        logger.error(f"Error getting books by subject '{subject}': {e}")
        return []
    finally:
        await release_connection(conn)

async def count_search_books(query: str) -> int:
    """Count total search results for pagination"""
    if not query or not query.strip():
        return 0

    conn = await get_connection()
    try:
        search_term = f'%{query.strip()}%'
        if _use_sqlite:
            cursor = await conn.execute(
                '''SELECT COUNT(*) FROM books
                   WHERE title LIKE ? COLLATE NOCASE OR author LIKE ? COLLATE NOCASE OR subject LIKE ? COLLATE NOCASE''',
                (search_term, search_term, search_term)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
        else:
            return await conn.fetchval(
                '''SELECT COUNT(*) FROM books
                   WHERE title ILIKE $1 OR author ILIKE $1 OR subject ILIKE $1''',
                search_term
            )
    except Exception as e:
        logger.error(f"Error counting search results for query '{query}': {e}")
        return 0
    finally:
        await release_connection(conn)

async def get_system_stats() -> dict:
    """Get system statistics for dashboard"""
    conn = await get_connection()
    try:
        stats = {}
        if _use_sqlite:
            # Total books
            cursor = await conn.execute('SELECT COUNT(*) FROM books')
            stats['total_books'] = (await cursor.fetchone())[0]

            # Books by subject
            cursor = await conn.execute('SELECT subject, COUNT(*) FROM books WHERE subject IS NOT NULL GROUP BY subject ORDER BY COUNT(*) DESC')
            stats['books_by_subject'] = {row[0]: row[1] for row in await cursor.fetchall()}

            # Total users
            cursor = await conn.execute('SELECT COUNT(*) FROM users')
            stats['total_users'] = (await cursor.fetchone())[0]

            # Users by role
            cursor = await conn.execute('SELECT role, COUNT(*) FROM users GROUP BY role')
            stats['users_by_role'] = {row[0]: row[1] for row in await cursor.fetchall()}

            # Recent uploads (last 30 days) - approximate
            cursor = await conn.execute("SELECT COUNT(*) FROM books WHERE uploaded_at > datetime('now', '-30 days')")
            stats['recent_uploads'] = (await cursor.fetchone())[0]
        else:
            # PostgreSQL
            stats['total_books'] = await conn.fetchval('SELECT COUNT(*) FROM books')

            rows = await conn.fetch('SELECT subject, COUNT(*) FROM books WHERE subject IS NOT NULL GROUP BY subject ORDER BY COUNT(*) DESC')
            stats['books_by_subject'] = {row['subject']: row['count'] for row in rows}

            stats['total_users'] = await conn.fetchval('SELECT COUNT(*) FROM users')

            rows = await conn.fetch('SELECT role, COUNT(*) FROM users GROUP BY role')
            stats['users_by_role'] = {row['role']: row['count'] for row in rows}

            stats['recent_uploads'] = await conn.fetchval("SELECT COUNT(*) FROM books WHERE uploaded_at > CURRENT_TIMESTAMP - INTERVAL '30 days'")

        return stats
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {}
    finally:
        await release_connection(conn)

async def search_books(query: str, offset: int = 0, limit: int = None) -> List[Book]:
    """Search books by title, author, or subject with pagination"""
    if not query or not query.strip():
        return []

    conn = await get_connection()
    try:
        search_term = f'%{query.strip()}%'
        if _use_sqlite:
            sql = '''SELECT * FROM books
                     WHERE title LIKE ? COLLATE NOCASE OR author LIKE ? COLLATE NOCASE OR subject LIKE ? COLLATE NOCASE
                     ORDER BY uploaded_at DESC'''
            params = (search_term, search_term, search_term)
            if limit is not None:
                sql += ' LIMIT ? OFFSET ?'
                params = params + (limit, offset)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [Book(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10]) for row in rows]
        else:
            sql = '''SELECT * FROM books
                     WHERE title ILIKE $1 OR author ILIKE $1 OR subject ILIKE $1
                     ORDER BY uploaded_at DESC'''
            params = [search_term]
            if limit is not None:
                sql += ' LIMIT $2 OFFSET $3'
                params = [search_term, limit, offset]
            rows = await conn.fetch(sql, *params)
            return [Book(row['book_id'], row['file_id_telegram'], row['file_hash_sha256'],
                         row['title'], row['author'], row['subject'], row['description'], row['size_bytes'],
                         row['url_external'], row['uploaded_at'], row['uploaded_by']) for row in rows]
    except Exception as e:
        logger.error(f"Error searching books with query '{query}': {e}")
        return []
    finally:
        await release_connection(conn)

async def get_all_subjects() -> List[str]:
    """Get all unique subjects/categories"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute('SELECT DISTINCT subject FROM books WHERE subject IS NOT NULL')
            rows = await cursor.fetchall()
            subjects = [row[0] for row in rows if row[0]]
        else:
            rows = await conn.fetch('SELECT DISTINCT subject FROM books WHERE subject IS NOT NULL')
            subjects = [row['subject'] for row in rows if row['subject']]
        return sorted(subjects, key=str.lower)
    except Exception as e:
        logger.error(f"Error getting all subjects: {e}")
        return []
    finally:
        await release_connection(conn)

async def get_book(book_id: int) -> Optional[Book]:
    """Get a book by its ID"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute('SELECT * FROM books WHERE book_id = ?', (book_id,))
            row = await cursor.fetchone()
            if row:
                return Book(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10])
        else:
            row = await conn.fetchrow('SELECT * FROM books WHERE book_id = $1', book_id)
            if row:
                return Book(row['book_id'], row['file_id_telegram'], row['file_hash_sha256'],
                           row['title'], row['author'], row['subject'], row['description'], row['size_bytes'],
                           row['url_external'], row['uploaded_at'], row['uploaded_by'])
        return None
    except Exception as e:
        logger.error(f"Error getting book {book_id}: {e}")
        return None
    finally:
        await release_connection(conn)

async def get_books_count() -> int:
    """Get total number of books in database"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute('SELECT COUNT(*) FROM books')
            result = await cursor.fetchone()
            return result[0] if result else 0
        else:
            return await conn.fetchval('SELECT COUNT(*) FROM books')
    except Exception as e:
        logger.error(f"Error getting books count: {e}")
        return 0
    finally:
        await release_connection(conn)

async def get_all_books(offset: int = 0, limit: int = 10) -> List[Book]:
    """Get all books with pagination"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute('SELECT * FROM books ORDER BY uploaded_at DESC LIMIT ? OFFSET ?', (limit, offset))
            rows = await cursor.fetchall()
            return [Book(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10]) for row in rows]
        else:
            rows = await conn.fetch('SELECT * FROM books ORDER BY uploaded_at DESC LIMIT $1 OFFSET $2', limit, offset)
            return [Book(row['book_id'], row['file_id_telegram'], row['file_hash_sha256'],
                         row['title'], row['author'], row['subject'], row['description'], row['size_bytes'],
                         row['url_external'], row['uploaded_at'], row['uploaded_by']) for row in rows]
    except Exception as e:
        logger.error(f"Error getting all books: {e}")
        return []
    finally:
        await release_connection(conn)

async def update_book_subject(book_id: int, new_subject: str):
    """Update the subject/category of a book"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            await conn.execute('UPDATE books SET subject = ? WHERE book_id = ?', (new_subject.lower().strip(), book_id))
            await conn.commit()
        else:
            await conn.execute('UPDATE books SET subject = $1 WHERE book_id = $2', new_subject.lower().strip(), book_id)
        logger.info(f"✅ Book {book_id} subject updated to '{new_subject}'")
    except Exception as e:
        logger.error(f"Error updating book {book_id} subject: {e}")
        raise
    finally:
        await release_connection(conn)

async def update_book_description(book_id: int, new_description: str):
    """Update the description of a book"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            await conn.execute('UPDATE books SET description = ? WHERE book_id = ?', (new_description, book_id))
            await conn.commit()
        else:
            await conn.execute('UPDATE books SET description = $1 WHERE book_id = $2', new_description, book_id)
        logger.info(f"✅ Book {book_id} description updated")
    except Exception as e:
        logger.error(f"Error updating book {book_id} description: {e}")
        raise
    finally:
        await release_connection(conn)

async def delete_book(book_id: int):
    """Delete a book from the database"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            await conn.execute('DELETE FROM books WHERE book_id = ?', (book_id,))
            await conn.commit()
        else:
            await conn.execute('DELETE FROM books WHERE book_id = $1', book_id)
        logger.info(f"✅ Book {book_id} deleted successfully")
    except Exception as e:
        logger.error(f"Error deleting book {book_id}: {e}")
        raise
    finally:
        await release_connection(conn)

class UnauthorizedUser:
    def __init__(self, user_id_telegram, attempts, last_attempt, is_blocked):
        self.user_id_telegram = user_id_telegram
        self.attempts = attempts
        self.last_attempt = last_attempt
        self.is_blocked = is_blocked

async def get_unauthorized_user(user_id: int) -> Optional[UnauthorizedUser]:
    """Get unauthorized user by Telegram ID"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            cursor = await conn.execute('SELECT * FROM unauthorized_users WHERE user_id_telegram = ?', (user_id,))
            row = await cursor.fetchone()
        else:
            row = await conn.fetchrow('SELECT * FROM unauthorized_users WHERE user_id_telegram = $1', user_id)

        if row:
            return UnauthorizedUser(row[0], row[1], row[2], row[3])
        return None
    except Exception as e:
        logger.error(f"Error getting unauthorized user {user_id}: {e}")
        return None
    finally:
        await release_connection(conn)

async def increment_unauthorized_attempts(user_id: int) -> bool:
    """Increment attempts for unauthorized user, return True if blocked"""
    conn = await get_connection()
    try:
        user = await get_unauthorized_user(user_id)
        if user:
            new_attempts = user.attempts + 1
            is_blocked = new_attempts >= 2
            if _use_sqlite:
                await conn.execute(
                    'UPDATE unauthorized_users SET attempts = ?, last_attempt = CURRENT_TIMESTAMP, is_blocked = ? WHERE user_id_telegram = ?',
                    (new_attempts, 1 if is_blocked else 0, user_id)
                )
                await conn.commit()
            else:
                await conn.execute(
                    'UPDATE unauthorized_users SET attempts = $1, last_attempt = CURRENT_TIMESTAMP, is_blocked = $2 WHERE user_id_telegram = $3',
                    new_attempts, is_blocked, user_id
                )
        else:
            # Insert new
            if _use_sqlite:
                await conn.execute(
                    'INSERT INTO unauthorized_users (user_id_telegram, attempts, is_blocked) VALUES (?, 1, 0)',
                    (user_id,)
                )
                await conn.commit()
            else:
                await conn.execute(
                    'INSERT INTO unauthorized_users (user_id_telegram, attempts, is_blocked) VALUES ($1, 1, FALSE)',
                    user_id
                )
            new_attempts = 1
            is_blocked = False

        logger.info(f"User {user_id} attempts: {new_attempts}, blocked: {is_blocked}")
        return is_blocked
    except Exception as e:
        logger.error(f"Error incrementing attempts for user {user_id}: {e}")
        return False
    finally:
        await release_connection(conn)

async def is_user_blocked(user_id: int) -> bool:
    """Check if user is blocked"""
    user = await get_unauthorized_user(user_id)
    return user.is_blocked if user else False

async def unblock_user(user_id: int):
    """Unblock a user by resetting their attempts"""
    conn = await get_connection()
    try:
        if _use_sqlite:
            await conn.execute(
                'UPDATE unauthorized_users SET attempts = 0, is_blocked = 0 WHERE user_id_telegram = ?',
                (user_id,)
            )
            await conn.commit()
        else:
            await conn.execute(
                'UPDATE unauthorized_users SET attempts = 0, is_blocked = FALSE WHERE user_id_telegram = $1',
                user_id
            )
        logger.info(f"User {user_id} unblocked")
    except Exception as e:
        logger.error(f"Error unblocking user {user_id}: {e}")
        raise
    finally:
        await release_connection(conn)