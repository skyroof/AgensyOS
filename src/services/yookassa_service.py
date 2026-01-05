import uuid
import logging
from typing import Tuple, Optional
from yookassa import Configuration, Payment
from src.core.config import get_settings

logger = logging.getLogger(__name__)

class YookassaService:
    def __init__(self):
        self.settings = get_settings()
        if self.settings.yookassa_shop_id and self.settings.yookassa_secret_key:
            Configuration.account_id = self.settings.yookassa_shop_id
            Configuration.secret_key = self.settings.yookassa_secret_key

    def create_payment(self, amount: float, description: str, metadata: dict = None) -> Tuple[str, str]:
        """
        Создать платеж и вернуть (URL для оплаты, payment_id).
        amount: сумма в рублях (float)
        """
        if not self.settings.yookassa_shop_id:
            raise ValueError("YooKassa credentials not configured")

        idempotence_key = str(uuid.uuid4())
        try:
            payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/MAXDiagnosticBot"  # Возврат в бот
                },
                "capture": True,
                "description": description,
                "metadata": metadata or {}
            }, idempotence_key)

            return payment.confirmation.confirmation_url, payment.id
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise

    def check_payment(self, payment_id: str) -> str:
        """
        Проверить статус платежа.
        Возвращает: pending, waiting_for_capture, succeeded, canceled
        """
        if not self.settings.yookassa_shop_id:
            return "unknown"
            
        try:
            payment = Payment.find_one(payment_id)
            return payment.status
        except Exception as e:
            logger.error(f"Error checking payment {payment_id}: {e}")
            return "error"

yookassa_service = YookassaService()
