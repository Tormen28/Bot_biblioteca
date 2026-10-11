#!/usr/bin/env python3
"""Test script to verify anti-spam functions work correctly"""
import asyncio
from db import init_db, increment_unauthorized_attempts, get_unauthorized_user, is_user_blocked, unblock_user, close_pool

async def main():
    print("Testing anti-spam functions...")

    # Initialize DB
    await init_db()
    print("DB initialized")

    test_user_id = 999999999  # Test user ID

    # Clean up any previous test data
    await unblock_user(test_user_id)
    print("Cleaned up previous test data")

    # Test initial state
    blocked = await is_user_blocked(test_user_id)
    print(f"Initial blocked status: {blocked} (should be False)")

    # First attempt
    print("\n--- First attempt ---")
    blocked = await increment_unauthorized_attempts(test_user_id)
    print(f"Blocked after attempt 1: {blocked} (should be False)")
    user = await get_unauthorized_user(test_user_id)
    print(f"Attempts: {user.attempts if user else 0} (should be 1)")

    # Second attempt
    print("\n--- Second attempt ---")
    blocked = await increment_unauthorized_attempts(test_user_id)
    print(f"Blocked after attempt 2: {blocked} (should be True)")
    user = await get_unauthorized_user(test_user_id)
    print(f"Attempts: {user.attempts if user else 0} (should be 2)")

    # Third attempt (should still be blocked)
    print("\n--- Third attempt (should still be blocked) ---")
    blocked = await increment_unauthorized_attempts(test_user_id)
    print(f"Blocked after attempt 3: {blocked} (should be True)")
    user = await get_unauthorized_user(test_user_id)
    print(f"Attempts: {user.attempts if user else 0} (should be 3)")

    # Unblock
    print("\n--- Unblocking ---")
    await unblock_user(test_user_id)
    blocked = await is_user_blocked(test_user_id)
    print(f"Blocked after unblock: {blocked} (should be False)")
    user = await get_unauthorized_user(test_user_id)
    print(f"Attempts after unblock: {user.attempts if user else 0} (should be 0)")

    await close_pool()
    print("\nAnti-spam tests completed!")

if __name__ == "__main__":
    asyncio.run(main())