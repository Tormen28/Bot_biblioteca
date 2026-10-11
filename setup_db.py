#!/usr/bin/env python3
"""
Database Setup Script for Biblio Bot
This script helps you set up and test your PostgreSQL database connection.
"""

import asyncio
import os
from dotenv import load_dotenv
from db import init_db, test_connection, create_pool, close_pool, get_books_count

# Load environment variables
load_dotenv()

async def main():
    print("Biblio Bot - Database Setup")
    print("=" * 40)

    # Check environment variables
    if not os.path.exists('.env'):
        print("⚠️ ARCHIVO .ENV NO ENCONTRADO.")
        print("Copia .env.example a .env y configura tus credenciales.")
        if os.path.exists('.env.example'):
            print("Sugerencia: ejecuta 'copy .env.example .env' en Windows")
        print("-" * 40)

    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        print("No se encontró POSTGRES_URL en las variables de entorno.")
        print("El sistema usará SQLite como alternativa (biblio_bot.db).")
    else:
        # Safer URL masking
        try:
            if '@' in db_url and ':' in db_url.split('@')[0]:
                masked_url = db_url.replace(db_url.split('@')[0].split(':')[1], '***', 1)
                print(f"URL de Base de Datos: {masked_url}")
            else:
                print(f"URL de Base de Datos: {db_url}")
        except Exception:
            print("URL de Base de Datos configurada.")

    # Test connection
    print("\nTesting database connection...")
    try:
        if await test_connection():
            print("Database connection successful!")
        else:
            print("Database connection failed!")
            print("\nTroubleshooting tips:")
            print("   1. Check if PostgreSQL is running")
            print("   2. Verify database credentials")
            print("   3. Ensure database exists")
            print("   4. Check firewall/network settings")
            return
    except Exception as e:
        print(f"Connection error: {e}")
        return

    # Initialize database
    print("\nInitializing database tables...")
    try:
        await init_db()
        print("Database tables created successfully!")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        return

    # Get statistics
    print("\nDatabase Statistics:")
    try:
        books_count = await get_books_count()
        print(f"   Total books: {books_count}")
        print("   Users table: Ready")
        print("   Books table: Ready")
        print("   Indexes: Created")
    except Exception as e:
        print(f"Error getting statistics: {e}")

    # Cleanup
    await close_pool()

    print("\nDatabase setup completed successfully!")
    print("\nYou can now run the bot with: python bot.py")

if __name__ == "__main__":
    asyncio.run(main())