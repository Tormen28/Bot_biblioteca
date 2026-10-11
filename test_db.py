#!/usr/bin/env python3
"""Test script to verify database functions work correctly"""
import asyncio
from db import test_connection, list_users, get_books_count, get_all_subjects, get_all_books, close_pool

async def main():
    print("Testing database functions...")
    
    # Test connection
    if await test_connection():
        print("✅ Connection: OK")
    else:
        print("❌ Connection: FAILED")
        return
    
    # Test list_users
    try:
        users = await list_users()
        print(f"✅ list_users: {len(users)} users found")
        for u in users:
            print(f"   - {u.user_id_telegram} ({u.username or 'no name'}) - {u.role}")
    except Exception as e:
        print(f"❌ list_users: {e}")
    
    # Test get_books_count
    try:
        count = await get_books_count()
        print(f"✅ get_books_count: {count} books")
    except Exception as e:
        print(f"❌ get_books_count: {e}")
    
    # Test get_all_subjects
    try:
        subjects = await get_all_subjects()
        print(f"✅ get_all_subjects: {subjects}")
    except Exception as e:
        print(f"❌ get_all_subjects: {e}")
    
    # Test get_all_books
    try:
        books = await get_all_books(offset=0, limit=5)
        print(f"✅ get_all_books: {len(books)} books returned")
        for b in books:
            print(f"   - {b.title} by {b.author}")
    except Exception as e:
        print(f"❌ get_all_books: {e}")
    
    await close_pool()
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
