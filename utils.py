# utils.py
import asyncio
from datetime import datetime
from aiogram import Bot
from config import ADMIN_IDS, REQUIRED_CHANNEL_ID, REQUIRED_CHANNEL_LINK, TECH_ADMIN_IDS
import database as db

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_tech_admin(user_id):
    return user_id in TECH_ADMIN_IDS

async def check_channel_subscription(bot: Bot, user_id: int, channel_id: str) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    try:
        chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Ошибка при проверке подписки на канал {channel_id}: {e}")
        return False

async def check_required_channel_subscription(bot: Bot, user_id: int) -> bool:
    """Проверяет подписку на обязательный канал"""
    required_channels = db.get_required_channels()
    
    if not required_channels:
        # Если в базе нет обязательных каналов, проверяем канал из конфига
        if REQUIRED_CHANNEL_ID:
            return await check_channel_subscription(bot, user_id, REQUIRED_CHANNEL_ID)
        return True  # Если обязательных каналов нет, считаем что подписан
    
    for channel in required_channels:
        channel_db_id, channel_id, channel_username, channel_link, channel_type = channel
        chat_identifier = channel_id if channel_type == 'private' else channel_username
        
        if not await check_channel_subscription(bot, user_id, chat_identifier):
            return False
    
    return True

async def check_all_subscriptions(bot: Bot, user_id: int):
    """Проверяет все подписки пользователя и списывает звезды за отписки"""
    channels = db.get_channels()
    completed_tasks = db.get_user_completed_tasks(user_id)
    total_deducted = 0
    
    for task in completed_tasks:
        channel_db_id, channel_username, channel_link, channel_type, stars_awarded = task
        
        # Находим канал в общем списке
        channel_info = None
        for ch in channels:
            if ch[0] == channel_db_id:
                channel_info = ch
                break
        
        if not channel_info:
            continue
        
        _, channel_id, _, _, channel_type, _ = channel_info[0:6]  # учитываем новые поля, но нам нужны первые
        
        # Проверяем подписку
        chat_identifier = channel_id if channel_type == 'private' else channel_username
        if not await check_channel_subscription(bot, user_id, chat_identifier):
            # Пользователь отписался, списываем звезды (баланс может быть отрицательным)
            db.update_balance(user_id, -stars_awarded, f"Списание за отписку от {channel_username}")
            db.revoke_task_completion(user_id, channel_db_id)
            total_deducted += stars_awarded
    
    return total_deducted

async def process_unsubscription(bot: Bot, user_id: int):
    """Обрабатывает отписку от обязательного канала"""
    # Проверяем, является ли пользователь рефералом
    referrer_id = db.get_referrer_by_referred(user_id)
    
    if referrer_id:
        # Проверяем, не списаны ли уже звезды
        if not db.is_referral_stars_withdrawn(referrer_id, user_id):
            # СПИСЫВАЕМ 3 ЗВЕЗДЫ ДАЖЕ ЕСЛИ БАЛАНС БУДЕТ ОТРИЦАТЕЛЬНЫМ
            db.update_balance(referrer_id, -3, f"Списание за отписку реферала {user_id}")
            db.mark_referral_stars_withdrawn(referrer_id, user_id)
            
            # Уведомляем пригласившего
            try:
                await bot.send_message(
                    referrer_id,
                    f"⚠️ <b>Внимание!</b>\n\n"
                    f"Ваш реферал отписался от обязательного канала.\n"
                    f"С вашего баланса списано 3 звезды.\n\n"
                    f"💡 Баланс может быть отрицательным!",
                    parse_mode='HTML'
                )
            except:
                pass
    
    # Снимаем отметку о подписке
    db.set_required_channel_subscribed(user_id, False)
    db.set_registration_completed(user_id, False)
    
    return True

async def complete_user_registration(bot: Bot, user_id: int):
    """Завершает регистрацию пользователя после подписки на обязательный канал"""
    # Проверяем, прошел ли пользователь капчу
    if not db.is_captcha_passed(user_id):
        return False
    
    # Проверяем, подписан ли на обязательный канал
    if not await check_required_channel_subscription(bot, user_id):
        return False
    
    # Помечаем подписку
    db.set_required_channel_subscribed(user_id, True)
    
    # Даем награду за реферала если есть
    referrer_id = db.get_referrer_by_referred(user_id)
    if referrer_id:
        db.give_referral_reward(referrer_id, user_id)
    
    # Помечаем регистрацию как завершенную
    db.set_registration_completed(user_id, True)
    
    return True

def get_user_info_text(user_id, username, balance, referrals, earned_refs, completed_tasks):
    """Формирует текст информации о пользователе"""
    # Рассчитываем уровень активности
    if referrals > 10:
        active_text = "🟢 Очень активен"
    elif referrals > 5:
        active_text = "🟡 Активен"
    else:
        active_text = "🔵 Новичок"
    
    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"💰 <b>Баланс:</b> <code>{balance} звезд</code>\n"
        f"📊 <b>Уровень:</b> {active_text}\n\n"
        f"👥 <b>Реферальная программа:</b>\n"
        f"• Приглашено друзей: <code>{referrals}</code>\n"
        f"• Заработано с рефералов: <code>{earned_refs} звезд</code>\n"
        f"• Выполнено заданий: <code>{completed_tasks}</code>\n"
        f"• Доступно для вывода: <code>{balance} звезд</code>\n\n"
        f"🎯 <b>Выберите действие:</b>"
    )
    
    return text

def get_stats_text(total_users, total_stars, total_channels, total_referrals, total_earned_refs):
    """Формирует текст статистики"""
    text = (
        f"📊 <b>Статистика бота:</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Рефералов: {total_referrals}\n"
        f"• Заработано рефералами: {total_earned_refs}⭐\n\n"
        f"💰 <b>Экономика:</b>\n"
        f"• Всего звезд: {total_stars}⭐\n"
        f"• Каналов: {total_channels}\n\n"
        f"📈 <b>Рост:</b> Активен\n"
        f"🚀 <b>Статус:</b> Работает"
    )
    
    return text

def format_referrals_list(referrals):
    """Форматирует список рефералов для отображения"""
    if not referrals:
        return "Список рефералов пуст"
    
    text = ""
    for idx, (referred_id, username, activated_at) in enumerate(referrals, 1):
        username_display = f"@{username}" if username else f"ID: {referred_id}"
        date_str = activated_at.split()[0] if activated_at else "Неизвестно"
        text += f"{idx}. {username_display} (с {date_str})\n"
    
    return text

def get_event_bonus(event_type, default_bonus=0):
    event = db.get_active_event(event_type)
    if event:
        return event[4]  # bonus
    return default_bonus

def get_event_multiplier(event_type, default_mult=1):
    event = db.get_active_event(event_type)
    if event:
        return event[3]  # multiplier
    return default_mult