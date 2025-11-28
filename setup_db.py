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
    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        print("No POSTGRES_URL found in environment variables.")
        print("The system will use SQLite as fallback.")
        print("To use PostgreSQL, set up your .env file based on .env.example")
        print("\nRequired for PostgreSQL:")
        print("   POSTGRES_URL=postgresql://user:password@host:port/database")
        # Continue with SQLite fallback

    if db_url:
        print(f"Database URL: {db_url.replace(db_url.split('@')[0].split(':')[1], '***')}")
    else:
        print("Database URL: Using SQLite fallback")

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