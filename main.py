# main.py
import asyncio
import logging
import os
import shutil
from aiogram.utils import executor
from datetime import datetime

import config
import database
from loader import dp, bot
import handlers
from subscription_checker import SubscriptionChecker

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
database.init_database()
database.update_database()

# Инициализация проверяльщика подписок
subscription_checker = None

async def remove_expired_channels():
    """Периодическое удаление просроченных каналов"""
    while True:
        await asyncio.sleep(3600)  # каждый час
        expired = database.get_expired_channels()
        for ch_id in expired:
            database.delete_channel_by_id(ch_id)
            logger.info(f"Автоматически удален канал {ch_id} (истек срок или достигнут лимит)")

async def auto_backup():
    """Автоматическое резервное копирование раз в сутки"""
    while True:
        await asyncio.sleep(24 * 3600)
        backup_filename = f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(config.BACKUP_PATH, backup_filename)
        os.makedirs(config.BACKUP_PATH, exist_ok=True)
        shutil.copy2(config.DB_NAME, backup_path)
        for admin_id in config.TECH_ADMIN_IDS:
            try:
                from aiogram.types import InputFile
                await bot.send_document(admin_id, InputFile(backup_path), caption="🔄 Автоматическая резервная копия")
            except:
                pass

async def on_startup(dp):
    """Действия при запуске бота"""
    global bot_username, subscription_checker
    
    # Получаем username бота
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    handlers.bot_username = bot_username
    
    # Добавляем обязательный канал из конфига если его нет
    required_channels = database.get_required_channels()
    if not required_channels and config.REQUIRED_CHANNEL_ID:
        try:
            chat = await bot.get_chat(config.REQUIRED_CHANNEL_ID)
            database.add_channel(
                channel_id=config.REQUIRED_CHANNEL_ID,
                channel_username=f"@{chat.username}" if chat.username else None,
                channel_type='private',
                channel_link=config.REQUIRED_CHANNEL_LINK,
                is_required=True
            )
            logger.info(f"✅ Добавлен обязательный канал: {chat.title}")
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении обязательного канала: {e}")
    
    # Запускаем проверку подписок
    subscription_checker = SubscriptionChecker(bot)
    asyncio.create_task(subscription_checker.start())
    
    # Запускаем дополнительные фоновые задачи
    asyncio.create_task(remove_expired_channels())
    asyncio.create_task(auto_backup())
    
    logger.info("=" * 50)
    logger.info(f"🚀 Бот @{bot_username} успешно запущен!")
    logger.info(f"👑 Администраторов: {len(config.ADMIN_IDS)}")
    logger.info(f"💾 База данных: {config.DB_NAME}")
    logger.info(f"📊 Проверка подписок: Активна (интервал: {config.CHECK_SUBSCRIPTION_INTERVAL} сек)")
    logger.info(f"🔗 Обязательный канал ID: {config.REQUIRED_CHANNEL_ID}")
    logger.info(f"🔗 Ссылка на канал: {config.REQUIRED_CHANNEL_LINK}")
    logger.info("=" * 50)

async def on_shutdown(dp):
    """Действия при остановке бота"""
    global subscription_checker
    
    if subscription_checker:
        await subscription_checker.stop()
    
    database.conn.close()
    logger.info("✅ Бот остановлен, соединение с БД закрыто")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)