# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💎 Заработать", callback_data="earn"),
        InlineKeyboardButton("📋 Задания", callback_data="tasks"),
        InlineKeyboardButton("💸 Вывести", callback_data="withdraw"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        InlineKeyboardButton("🏆 Топ рефералов", callback_data="top_ref"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats_user"),
        InlineKeyboardButton("👥 Рефералка", callback_data="referral_system"),
        InlineKeyboardButton("🎰 Казино", callback_data="casino"),
        InlineKeyboardButton("🏆 Рейтинг", callback_data="rating_menu")
    )
    return keyboard

def get_back_to_menu_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_menu"))
    return keyboard

def get_tasks_keyboard(user_id, channels, completed_channels):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for channel in channels:
        channel_db_id, channel_id, channel_username, channel_link, channel_type, is_required, deadline, max_subscribers, current_subscribers = channel
        
        if is_required:
            continue  # Пропускаем обязательные каналы
        
        # Проверяем, не истек ли срок и не достигнут ли лимит
        expired = False
        if deadline and datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S') < datetime.now():
            expired = True
        if max_subscribers > 0 and current_subscribers >= max_subscribers:
            expired = True
        
        if expired:
            continue  # Не показываем просроченные задания
        
        if channel_type == 'public' and channel_username:
            button_text = f"📢 Подписаться на {channel_username}"
            if channel_db_id in completed_channels:
                button_text = f"✅ {channel_username} (выполнено)"
                keyboard.add(InlineKeyboardButton(button_text, callback_data="task_completed"))
            else:
                # Добавляем информацию о прогрессе, если есть лимит
                if max_subscribers > 0:
                    progress = f" ({current_subscribers}/{max_subscribers})"
                    button_text += progress
                url = f"https://t.me/{channel_username.replace('@', '')}"
                keyboard.add(InlineKeyboardButton(button_text, url=url))
        elif channel_type == 'private' and channel_link:
            button_text = "🔒 Подписаться на приватный канал"
            if max_subscribers > 0:
                progress = f" ({current_subscribers}/{max_subscribers})"
                button_text += progress
            keyboard.add(InlineKeyboardButton(button_text, url=channel_link))
    
    keyboard.add(InlineKeyboardButton("✅ Проверить подписки", callback_data="check_subs"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_menu"))
    return keyboard

def get_withdrawal_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("15 звёзд", callback_data="withdraw_15"),
        InlineKeyboardButton("25 звёзд", callback_data="withdraw_25"),
        InlineKeyboardButton("50 звёзд", callback_data="withdraw_50"),
        InlineKeyboardButton("100 звёзд", callback_data="withdraw_100"),
        InlineKeyboardButton("🏦 Другая сумма", callback_data="custom_withdraw"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_menu")
    )
    return keyboard

def get_admin_withdrawal_keyboard(withdrawal_id):
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{withdrawal_id}"),
        InlineKeyboardButton("💰 Оплатить", callback_data=f"pay_{withdrawal_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{withdrawal_id}")
    )
    return keyboard

def get_profile_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🎁 Активировать промокод", callback_data="activate_promo"),
        InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"),
        InlineKeyboardButton("📜 История", callback_data="user_history"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_menu")
    )
    return keyboard

def get_captcha_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Пропустить", callback_data="skip_captcha"))
    return keyboard

def get_required_channel_keyboard(channel_link):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📢 Подписаться на канал", url=channel_link))
    keyboard.add(InlineKeyboardButton("✅ Я подписался", callback_data="check_required_channel"))
    return keyboard

def get_registration_complete_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🚀 Начать зарабатывать", callback_data="start_earning"))
    return keyboard

# НОВЫЕ КЛАВИАТУРЫ

def get_referral_system_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🔗 Получить ссылку", callback_data="get_ref_link"),
        InlineKeyboardButton("👥 Мои рефералы", callback_data="my_referrals"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_menu")
    )
    return keyboard

def get_casino_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎰 1 ⭐", callback_data="casino_1"),
        InlineKeyboardButton("🎰 5 ⭐", callback_data="casino_5"),
        InlineKeyboardButton("🎰 10 ⭐", callback_data="casino_10"),
        InlineKeyboardButton("🎰 25 ⭐", callback_data="casino_25"),
        InlineKeyboardButton("🎰 50 ⭐", callback_data="casino_50"),
        InlineKeyboardButton("🎰 100 ⭐", callback_data="casino_100"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_menu")
    )
    return keyboard

def get_rating_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🏆 По рефералам", callback_data="rating_ref"),
        InlineKeyboardButton("💰 По балансу", callback_data="rating_balance"),
        InlineKeyboardButton("🎰 По выигрышам в казино", callback_data="rating_casino"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_menu")
    )
    return keyboard

def get_admin_panel_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("📢 Управление каналами", callback_data="admin_channels"),
        InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promos"),
        InlineKeyboardButton("💰 Заявки на вывод", callback_data="admin_withdrawals"),
        InlineKeyboardButton("👥 Поиск пользователя", callback_data="admin_search"),
        InlineKeyboardButton("🎉 Ивенты", callback_data="admin_events"),
        InlineKeyboardButton("📜 Логи админов", callback_data="admin_logs"),
        InlineKeyboardButton("📤 Экспорт пользователей", callback_data="admin_export"),
        InlineKeyboardButton("💾 Резервная копия", callback_data="admin_backup"),
        InlineKeyboardButton("🎯 Охота за 777", callback_data="admin_hunt"),
        InlineKeyboardButton("🚫 Бан / Разбан", callback_data="admin_ban"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_menu")
    )
    return keyboard