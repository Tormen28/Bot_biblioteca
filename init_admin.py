import asyncio
import os
from dotenv import load_dotenv
from db import init_db, add_user

load_dotenv()

async def main():
    await init_db()
    
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    if not admin_ids_str:
        print("⚠️ No se encontraron ADMIN_IDS en el archivo .env")
        return

    # Use the first admin ID as default
    first_admin_id = int(admin_ids_str.split(',')[0].strip())
    
    try:
        await add_user(first_admin_id, None, 'admin', 'system')
        print(f"✅ Admin {first_admin_id} agregado.")
    except Exception as e:
        print(f"ℹ️ Admin {first_admin_id} ya existe o error: {e}")

if __name__ == "__main__":
    asyncio.run(main())