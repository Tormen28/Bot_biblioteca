import asyncio
import os
from dotenv import load_dotenv
from db import init_db, add_user, list_users

load_dotenv()

async def main():
    await init_db()
    
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    if not admin_ids_str:
        print("⚠️ No se encontraron ADMIN_IDS en el archivo .env")
        return

    admin_ids = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
    
    for admin_id in admin_ids:
        try:
            await add_user(admin_id, 'admin', 'system')
            print(f"✅ Admin {admin_id} agregado")
        except Exception as e:
            print(f"ℹ️  Admin {admin_id} ya existe o error: {e}")
    
    users = await list_users()
    print("\n📋 Lista de admins autorizados:")
    for u in users:
        print(f"  • {u.user_id_telegram} - {u.role}")

if __name__ == "__main__":
    asyncio.run(main())
