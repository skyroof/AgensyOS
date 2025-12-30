"""
Скрипт инициализации промокода MAXVISUAL100.

Запуск: python -m scripts.init_promocode
"""
import asyncio
import sys
sys.path.insert(0, ".")

from src.db.session import init_db, close_db, get_session
from src.db.repositories.balance_repo import create_promocode, get_promocode


async def main():
    print("🚀 Инициализация базы данных...")
    await init_db()
    
    print("🎁 Проверяем промокод MAXVISUAL100...")
    
    async with get_session() as session:
        # Проверяем, существует ли уже
        existing = await get_promocode(session, "MAXVISUAL100")
        
        if existing:
            print(f"✅ Промокод уже существует:")
            print(f"   Code: {existing.code}")
            print(f"   Discount: {existing.discount_percent}%")
            print(f"   Uses: {existing.current_uses}/{existing.max_uses or '∞'}")
            print(f"   Active: {existing.is_active}")
        else:
            # Создаём
            promo = await create_promocode(
                session=session,
                code="MAXVISUAL100",
                discount_percent=100,
                max_uses=1000,
                applicable_packs=["single", "pack3", "pack10"],
                description="Промокод Max Visual - 100% скидка",
                created_by="system",
            )
            print(f"✅ Промокод создан:")
            print(f"   Code: {promo.code}")
            print(f"   Discount: {promo.discount_percent}%")
            print(f"   Max uses: {promo.max_uses}")
            print(f"   Applicable packs: {promo.applicable_packs}")
    
    await close_db()
    print("\n🎉 Готово!")


if __name__ == "__main__":
    asyncio.run(main())

