"""
Скрипт инициализации промокода MAXVISUAL200.

Запуск: python -m scripts.add_maxvisual200
"""
import asyncio
import sys
sys.path.insert(0, ".")

from src.db.session import init_db, close_db, get_session
from src.db.repositories.balance_repo import create_promocode, get_promocode


async def main():
    print("🚀 Инициализация базы данных...")
    await init_db()
    
    print("🎁 Проверяем промокод MAXVISUAL200...")
    
    async with get_session() as session:
        # Проверяем, существует ли уже
        existing = await get_promocode(session, "MAXVISUAL200")
        
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
                code="MAXVISUAL200",
                discount_percent=100,
                max_uses=None, # Безлимитный
                applicable_packs=["single", "pack3", "pack10", "subscription_1m"],
                description="Промокод Max Visual 200 - 100% скидка",
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
