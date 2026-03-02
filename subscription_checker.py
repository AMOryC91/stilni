# subscription_checker.py
import asyncio
from datetime import datetime
from aiogram import Bot
import database as db
from utils import check_required_channel_subscription, process_unsubscription
from config import CHECK_SUBSCRIPTION_INTERVAL, REQUIRED_CHANNEL_LINK

class SubscriptionChecker:
    def __init__(self, bot: Bot, check_interval: int = CHECK_SUBSCRIPTION_INTERVAL):
        self.bot = bot
        self.check_interval = check_interval
        self.is_running = False
    
    async def start(self):
        """Запускает периодическую проверку подписок"""
        self.is_running = True
        print(f"✅ Запущена проверка подписок (интервал: {self.check_interval} сек)")
        
        while self.is_running:
            try:
                await self.check_all_users_subscriptions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"❌ Ошибка в проверке подписок: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке
    
    async def stop(self):
        """Останавливает проверку подписок"""
        self.is_running = False
        print("⏹️ Проверка подписок остановлена")
    
    async def check_all_users_subscriptions(self):
        """Проверяет подписки всех пользователей"""
        try:
            # Получаем всех пользователей
            all_users = db.get_all_users()
            
            print(f"🔍 Проверяю подписки {len(all_users)} пользователей...")
            
            for user in all_users:
                user_id = user[0]
                if db.is_banned(user_id):
                    continue  # не проверяем забаненных
                await self.check_user_subscription(user_id)
                
        except Exception as e:
            print(f"❌ Ошибка при проверке подписок: {e}")
    
    async def check_user_subscription(self, user_id: int):
        """Проверяет подписку конкретного пользователя"""
        try:
            # Проверяем подписку на обязательный канал
            is_subscribed = await check_required_channel_subscription(self.bot, user_id)
            
            if not is_subscribed:
                # Пользователь отписался
                if db.is_required_channel_subscribed(user_id):
                    print(f"⚠️ Пользователь {user_id} отписался от обязательного канала")
                    
                    # Обрабатываем отписку
                    await process_unsubscription(self.bot, user_id)
                    
                    # Уведомляем пользователя
                    try:
                        from keyboards import get_required_channel_keyboard
                        
                        keyboard = get_required_channel_keyboard(REQUIRED_CHANNEL_LINK)
                        
                        await self.bot.send_message(
                            user_id,
                            f"⚠️ <b>Внимание!</b>\n\n"
                            f"Вы отписались от обязательного канала.\n"
                            f"Для продолжения работы с ботом необходимо снова подписаться.\n\n"
                            f"📢 <b>Обязательный канал:</b>\n"
                            f"{REQUIRED_CHANNEL_LINK}",
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        print(f"Не удалось уведомить пользователя {user_id}: {e}")
            else:
                # Пользователь подписан
                if not db.is_required_channel_subscribed(user_id):
                    db.set_required_channel_subscribed(user_id, True)
                    
                    # Если регистрация еще не завершена, завершаем ее
                    if not db.is_registration_completed(user_id):
                        from utils import complete_user_registration
                        if await complete_user_registration(self.bot, user_id):
                            try:
                                await self.bot.send_message(
                                    user_id,
                                    f"🎉 <b>Регистрация завершена!</b>\n\n"
                                    f"✅ Вы успешно подписались на обязательный канал.\n"
                                    f"💰 На ваш баланс зачислено 3 звезды!\n"
                                    f"👥 Ваш пригласитель также получил награду.\n\n"
                                    f"🚀 <b>Теперь вы можете начать зарабатывать!</b>",
                                    parse_mode='HTML'
                                )
                            except:
                                pass
            
        except Exception as e:
            print(f"❌ Ошибка при проверке подписки пользователя {user_id}: {e}")
    
    async def check_specific_user(self, user_id: int):
        """Проверяет подписку конкретного пользователя немедленно"""
        await self.check_user_subscription(user_id)