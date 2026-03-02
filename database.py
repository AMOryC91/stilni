# database.py
import sqlite3
from datetime import datetime
import random
from config import DB_NAME

# Инициализация базы данных
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

def init_database():
    """Инициализация таблиц базы данных"""
    # Создание таблицы пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        earned_from_refs INTEGER DEFAULT 0,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        required_channel_subscribed BOOLEAN DEFAULT 0,
        captcha_passed BOOLEAN DEFAULT 0,
        registration_completed BOOLEAN DEFAULT 0,
        banned BOOLEAN DEFAULT 0,
        total_casino_win INTEGER DEFAULT 0,
        total_casino_loss INTEGER DEFAULT 0
    )
    ''')
    
    # Создание таблицы каналов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        channel_username TEXT,
        channel_link TEXT,
        channel_type TEXT DEFAULT 'public',
        is_required BOOLEAN DEFAULT 0,
        deadline TIMESTAMP,                -- Срок действия задания (NULL = бессрочно)
        max_subscribers INTEGER DEFAULT 0, -- Лимит подписчиков (0 = без лимита)
        current_subscribers INTEGER DEFAULT 0 -- Текущее количество выполнивших
    )
    ''')
    
    # Создание таблицы заданий пользователя
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_channels (
        user_id INTEGER,
        channel_id INTEGER,
        completed BOOLEAN DEFAULT 0,
        completed_at TIMESTAMP,
        stars_awarded INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, channel_id),
        FOREIGN KEY (channel_id) REFERENCES channels(id)
    )
    ''')
    
    # Создание таблицы выводов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        username TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP
    )
    ''')
    
    # Создание таблицы промокодов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promocodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promo_code TEXT UNIQUE,
        stars INTEGER,
        max_activations INTEGER,
        used_activations INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Создание таблицы активаций промокодов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promo_activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        promo_id INTEGER,
        activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, promo_id)
    )
    ''')
    
    # Создание таблицы рефералов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referral_activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        stars_withdrawn BOOLEAN DEFAULT 0,
        reward_given BOOLEAN DEFAULT 0
    )
    ''')
    
    # Создание таблицы капчи для рефералов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referral_captcha (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        num1 INTEGER,
        num2 INTEGER,
        operation TEXT,
        answer INTEGER,
        attempts INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referrer_id) REFERENCES users(user_id)
    )
    ''')
    
    # Создание таблицы истории операций
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        transaction_type TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # НОВЫЕ ТАБЛИЦЫ
    
    # Таблица событий (ивентов)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,  -- 'referral', 'casino', 'task'
        multiplier INTEGER DEFAULT 1,
        bonus INTEGER DEFAULT 0,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        is_active BOOLEAN DEFAULT 0
    )
    ''')
    
    # Таблица административных логов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        admin_username TEXT,
        action TEXT,
        target_user_id INTEGER,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица для игр в казино
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS casino_games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bet INTEGER,
        result INTEGER,
        win INTEGER,
        multiplier INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица для банов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        banned_by INTEGER,
        reason TEXT,
        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    print("✅ База данных инициализирована")

def update_database():
    """Обновление структуры базы данных"""
    try:
        # Проверяем существование таблиц
        tables = ['users', 'channels', 'user_channels', 'withdrawals', 
                  'promocodes', 'promo_activations', 'referral_activations', 
                  'referral_captcha', 'user_transactions', 'events', 'admin_logs', 'casino_games', 'bans']
        
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                print(f"❌ Таблица {table} не найдена")
                return False
        
        # Проверяем столбцы в таблице users
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]
        
        if 'required_channel_subscribed' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN required_channel_subscribed BOOLEAN DEFAULT 0')
            print("✅ Добавлен столбец required_channel_subscribed")
        
        if 'captcha_passed' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN captcha_passed BOOLEAN DEFAULT 0')
            print("✅ Добавлен столбец captcha_passed")
        
        if 'registration_completed' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN registration_completed BOOLEAN DEFAULT 0')
            print("✅ Добавлен столбец registration_completed")
        
        if 'banned' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN banned BOOLEAN DEFAULT 0')
            print("✅ Добавлен столбец banned")
        
        if 'total_casino_win' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN total_casino_win INTEGER DEFAULT 0')
            print("✅ Добавлен столбец total_casino_win")
        
        if 'total_casino_loss' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN total_casino_loss INTEGER DEFAULT 0')
            print("✅ Добавлен столбец total_casino_loss")
        
        # Проверяем столбцы в таблице channels
        cursor.execute("PRAGMA table_info(channels)")
        channel_columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_required' not in channel_columns:
            cursor.execute('ALTER TABLE channels ADD COLUMN is_required BOOLEAN DEFAULT 0')
            print("✅ Добавлен столбец is_required")
        
        if 'deadline' not in channel_columns:
            cursor.execute('ALTER TABLE channels ADD COLUMN deadline TIMESTAMP')
            print("✅ Добавлен столбец deadline")
        
        if 'max_subscribers' not in channel_columns:
            cursor.execute('ALTER TABLE channels ADD COLUMN max_subscribers INTEGER DEFAULT 0')
            print("✅ Добавлен столбец max_subscribers")
        
        if 'current_subscribers' not in channel_columns:
            cursor.execute('ALTER TABLE channels ADD COLUMN current_subscribers INTEGER DEFAULT 0')
            print("✅ Добавлен столбец current_subscribers")
        
        # Проверяем столбцы в таблице user_channels
        cursor.execute("PRAGMA table_info(user_channels)")
        user_channel_columns = [column[1] for column in cursor.fetchall()]
        
        if 'stars_awarded' not in user_channel_columns:
            cursor.execute('ALTER TABLE user_channels ADD COLUMN stars_awarded INTEGER DEFAULT 0')
            print("✅ Добавлен столбец stars_awarded")
        
        # Проверяем столбцы в таблице referral_activations
        cursor.execute("PRAGMA table_info(referral_activations)")
        referral_columns = [column[1] for column in cursor.fetchall()]
        
        if 'stars_withdrawn' not in referral_columns:
            cursor.execute('ALTER TABLE referral_activations ADD COLUMN stars_withdrawn BOOLEAN DEFAULT 0')
            print("✅ Добавлен столбец stars_withdrawn")
        
        if 'reward_given' not in referral_columns:
            cursor.execute('ALTER TABLE referral_activations ADD COLUMN reward_given BOOLEAN DEFAULT 0')
            print("✅ Добавлен столбец reward_given")
        
        conn.commit()
        print("✅ База данных обновлена успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении базы данных: {e}")
        return False

# Функции работы с пользователями
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def create_user(user_id, username):
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, last_active) VALUES (?, ?, ?)', 
                   (user_id, username, datetime.now()))
    conn.commit()

def update_balance(user_id, amount, description=""):
    # БАЛАНС МОЖЕТ БЫТЬ ОТРИЦАТЕЛЬНЫМ - УБИРАЕМ ПРОВЕРКИ
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    
    # Записываем транзакцию
    if description:
        transaction_type = "начисление" if amount > 0 else "списание"
        cursor.execute('''
            INSERT INTO user_transactions (user_id, amount, transaction_type, description) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, abs(amount), transaction_type, description))
    
    conn.commit()

def get_balance(user_id):
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def set_user_captcha_passed(user_id, status=True):
    cursor.execute('UPDATE users SET captcha_passed = ? WHERE user_id = ?', 
                   (1 if status else 0, user_id))
    conn.commit()

def set_required_channel_subscribed(user_id, status=True):
    cursor.execute('UPDATE users SET required_channel_subscribed = ? WHERE user_id = ?', 
                   (1 if status else 0, user_id))
    conn.commit()

def set_registration_completed(user_id, status=True):
    cursor.execute('UPDATE users SET registration_completed = ? WHERE user_id = ?', 
                   (1 if status else 0, user_id))
    conn.commit()

def is_registration_completed(user_id):
    cursor.execute('SELECT registration_completed FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

def is_required_channel_subscribed(user_id):
    cursor.execute('SELECT required_channel_subscribed FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

def is_captcha_passed(user_id):
    cursor.execute('SELECT captcha_passed FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

def get_user_transactions(user_id, limit=10):
    cursor.execute('''
        SELECT amount, transaction_type, description, created_at 
        FROM user_transactions 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit))
    return cursor.fetchall()

# Функции работы с каналами
def add_channel(channel_id, channel_username, channel_type='public', channel_link=None, is_required=False, deadline=None, max_subscribers=0):
    cursor.execute('''
        INSERT OR IGNORE INTO channels (channel_id, channel_username, channel_link, channel_type, is_required, deadline, max_subscribers) 
        VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                   (channel_id, channel_username, channel_link, channel_type, 1 if is_required else 0, deadline, max_subscribers))
    conn.commit()
    return cursor.lastrowid

def delete_channel(channel_identifier):
    cursor.execute('DELETE FROM channels WHERE channel_username = ? OR channel_id = ?', 
                   (channel_identifier, channel_identifier))
    conn.commit()

def get_channels():
    cursor.execute('SELECT id, channel_id, channel_username, channel_link, channel_type, is_required, deadline, max_subscribers, current_subscribers FROM channels')
    return cursor.fetchall()

def get_required_channels():
    cursor.execute('SELECT id, channel_id, channel_username, channel_link, channel_type FROM channels WHERE is_required = 1')
    return cursor.fetchall()

def get_channel_by_username(channel_username):
    cursor.execute('SELECT * FROM channels WHERE channel_username = ?', (channel_username,))
    return cursor.fetchone()

def get_channel_by_id(channel_id):
    cursor.execute('SELECT * FROM channels WHERE channel_id = ?', (channel_id,))
    return cursor.fetchone()

def update_channel_subscribers(channel_db_id):
    """Обновляет счетчик current_subscribers для канала"""
    cursor.execute('''
        UPDATE channels SET current_subscribers = (
            SELECT COUNT(*) FROM user_channels WHERE channel_id = ? AND completed = 1
        ) WHERE id = ?
    ''', (channel_db_id, channel_db_id))
    conn.commit()

def get_expired_channels():
    """Возвращает каналы, у которых истек срок или достигнут лимит"""
    now = datetime.now()
    cursor.execute('''
        SELECT id FROM channels 
        WHERE (deadline IS NOT NULL AND deadline < ?) 
           OR (max_subscribers > 0 AND current_subscribers >= max_subscribers)
    ''', (now,))
    return [row[0] for row in cursor.fetchall()]

def delete_channel_by_id(channel_db_id):
    """Удаляет канал и все связанные задания пользователей"""
    cursor.execute('DELETE FROM user_channels WHERE channel_id = ?', (channel_db_id,))
    cursor.execute('DELETE FROM channels WHERE id = ?', (channel_db_id,))
    conn.commit()

# Функции для заданий пользователя
def check_task_completion(user_id, channel_db_id):
    cursor.execute('SELECT completed, stars_awarded FROM user_channels WHERE user_id = ? AND channel_id = ?', 
                   (user_id, channel_db_id))
    result = cursor.fetchone()
    return (result[0], result[1]) if result else (0, 0)

def complete_task(user_id, channel_db_id, stars_awarded=2):
    cursor.execute('''
        INSERT OR REPLACE INTO user_channels (user_id, channel_id, completed, completed_at, stars_awarded) 
        VALUES (?, ?, 1, ?, ?)
    ''', (user_id, channel_db_id, datetime.now(), stars_awarded))
    # Обновляем счетчик подписчиков канала
    update_channel_subscribers(channel_db_id)
    conn.commit()

def revoke_task_completion(user_id, channel_db_id):
    """Отменяет выполнение задания и списывает начисленные звезды"""
    cursor.execute('SELECT stars_awarded FROM user_channels WHERE user_id = ? AND channel_id = ?', 
                   (user_id, channel_db_id))
    result = cursor.fetchone()
    
    if result:
        stars_awarded = result[0]
        # Удаляем запись о выполнении
        cursor.execute('DELETE FROM user_channels WHERE user_id = ? AND channel_id = ?', 
                       (user_id, channel_db_id))
        # Обновляем счетчик подписчиков канала
        update_channel_subscribers(channel_db_id)
        conn.commit()
        return stars_awarded
    return 0

def get_user_completed_tasks(user_id):
    cursor.execute('''
        SELECT c.id, c.channel_username, c.channel_link, c.channel_type, uc.stars_awarded
        FROM user_channels uc
        JOIN channels c ON uc.channel_id = c.id
        WHERE uc.user_id = ? AND uc.completed = 1
    ''', (user_id,))
    return cursor.fetchall()

# Функции для выводов
def add_withdrawal(user_id, amount, username):
    cursor.execute('''INSERT INTO withdrawals (user_id, amount, username, created_at) 
                      VALUES (?, ?, ?, ?)''', 
                   (user_id, amount, username, datetime.now()))
    conn.commit()
    return cursor.lastrowid

def update_withdrawal_status(withdrawal_id, status):
    cursor.execute('UPDATE withdrawals SET status = ? WHERE id = ?', (status, withdrawal_id))
    conn.commit()

def get_withdrawal(withdrawal_id):
    cursor.execute('SELECT * FROM withdrawals WHERE id = ?', (withdrawal_id,))
    return cursor.fetchone()

def get_pending_withdrawals():
    cursor.execute('SELECT * FROM withdrawals WHERE status = "pending"')
    return cursor.fetchall()

# Функции для промокодов
def add_promo(promo_code, stars, max_activations):
    cursor.execute('''
        INSERT OR IGNORE INTO promocodes (promo_code, stars, max_activations) 
        VALUES (?, ?, ?)''', 
                   (promo_code.upper(), stars, max_activations))
    conn.commit()
    return cursor.lastrowid

def delete_promo(promo_code):
    cursor.execute('DELETE FROM promocodes WHERE promo_code = ?', (promo_code.upper(),))
    conn.commit()

def get_promo(promo_code):
    cursor.execute('SELECT * FROM promocodes WHERE promo_code = ?', (promo_code.upper(),))
    return cursor.fetchone()

def activate_promo(user_id, promo_id):
    cursor.execute('SELECT * FROM promo_activations WHERE user_id = ? AND promo_id = ?', 
                   (user_id, promo_id))
    if cursor.fetchone():
        return False, "❌ Вы уже активировали этот промокод!"
    
    cursor.execute('SELECT stars, max_activations, used_activations FROM promocodes WHERE id = ?', (promo_id,))
    promo = cursor.fetchone()
    
    if not promo:
        return False, "❌ Промокод не найден!"
    
    stars, max_activations, used_activations = promo
    
    if used_activations >= max_activations:
        return False, "❌ Лимит активаций промокода исчерпан!"
    
    cursor.execute('UPDATE promocodes SET used_activations = used_activations + 1 WHERE id = ?', (promo_id,))
    cursor.execute('INSERT INTO promo_activations (user_id, promo_id) VALUES (?, ?)', (user_id, promo_id))
    update_balance(user_id, stars, f"Активация промокода")
    conn.commit()
    
    return True, f"✅ Промокод активирован! Получено {stars} звёзд!"

def get_all_promos():
    cursor.execute('SELECT promo_code, stars, max_activations, used_activations FROM promocodes')
    return cursor.fetchall()

# Функции для рефералов
def get_top_referrers(limit=10):
    cursor.execute('''
        SELECT user_id, username, referrals, earned_from_refs 
        FROM users 
        WHERE referrals > 0 
        ORDER BY referrals DESC, earned_from_refs DESC 
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()

def update_user_activity(user_id):
    cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', 
                   (datetime.now(), user_id))
    conn.commit()

def check_referral_exists(referrer_id, referred_id):
    cursor.execute('SELECT * FROM referral_activations WHERE referrer_id = ? AND referred_id = ?', 
                   (referrer_id, referred_id))
    return cursor.fetchone() is not None

def add_referral(referrer_id, referred_id):
    cursor.execute('INSERT OR IGNORE INTO referral_activations (referrer_id, referred_id) VALUES (?, ?)', 
                   (referrer_id, referred_id))
    
    # Обновляем статистику реферера
    cursor.execute('UPDATE users SET referrals = referrals + 1 WHERE user_id = ?', (referrer_id,))
    conn.commit()

def get_referrer_by_referred(referred_id):
    """Получает ID пригласившего по ID реферала"""
    cursor.execute('SELECT referrer_id FROM referral_activations WHERE referred_id = ?', (referred_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def mark_referral_stars_withdrawn(referrer_id, referred_id):
    """Помечает, что звезды за реферала уже списаны"""
    cursor.execute('UPDATE referral_activations SET stars_withdrawn = 1 WHERE referrer_id = ? AND referred_id = ?', 
                   (referrer_id, referred_id))
    conn.commit()

def is_referral_stars_withdrawn(referrer_id, referred_id):
    """Проверяет, списаны ли уже звезды за реферала"""
    cursor.execute('SELECT stars_withdrawn FROM referral_activations WHERE referrer_id = ? AND referred_id = ?', 
                   (referrer_id, referred_id))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

def mark_referral_reward_given(referrer_id, referred_id):
    """Помечает, что награда за реферала уже выдана"""
    cursor.execute('UPDATE referral_activations SET reward_given = 1 WHERE referrer_id = ? AND referred_id = ?', 
                   (referrer_id, referred_id))
    conn.commit()

def is_referral_reward_given(referrer_id, referred_id):
    """Проверяет, выдана ли уже награда за реферала"""
    cursor.execute('SELECT reward_given FROM referral_activations WHERE referrer_id = ? AND referred_id = ?', 
                   (referrer_id, referred_id))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

# Функции для капчи рефералов
def create_captcha(referrer_id, referred_id):
    # ПРОВЕРЯЕМ, НЕ СУЩЕСТВУЕТ ЛИ УЖЕ КАПЧА ДЛЯ ЭТОГО ПОЛЬЗОВАТЕЛЯ
    cursor.execute('SELECT * FROM referral_captcha WHERE referred_id = ?', (referred_id,))
    existing_captcha = cursor.fetchone()
    if existing_captcha:
        # Капча уже существует, возвращаем существующую
        return existing_captcha[3], existing_captcha[4], existing_captcha[6]
    
    # ПРОВЕРЯЕМ, НЕ БЫЛ ЛИ УЖЕ ЗАРЕГИСТРИРОВАН КАК РЕФЕРАЛ
    cursor.execute('SELECT * FROM referral_activations WHERE referred_id = ?', (referred_id,))
    existing_referral = cursor.fetchone()
    if existing_referral:
        # Реферал уже существует, не создаем новую капчу
        return None
    
    num1 = random.randint(1, 50)
    num2 = random.randint(1, 50)
    answer = num1 + num2
    
    cursor.execute('''
        INSERT INTO referral_captcha (referrer_id, referred_id, num1, num2, operation, answer) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (referrer_id, referred_id, num1, num2, '+', answer))
    conn.commit()
    
    return num1, num2, answer

def get_captcha(referred_id):
    cursor.execute('SELECT * FROM referral_captcha WHERE referred_id = ?', (referred_id,))
    return cursor.fetchone()

def increment_captcha_attempts(captcha_id):
    cursor.execute('UPDATE referral_captcha SET attempts = attempts + 1 WHERE id = ?', (captcha_id,))
    conn.commit()

def delete_captcha(captcha_id):
    cursor.execute('DELETE FROM referral_captcha WHERE id = ?', (captcha_id,))
    conn.commit()

def process_successful_captcha(referrer_id, referred_id):
    """Обрабатывает успешное прохождение капчи"""
    # ПРОВЕРЯЕМ, НЕ БЫЛ ЛИ УЖЕ ОБРАБОТАН ЭТОТ РЕФЕРАЛ
    if check_referral_exists(referrer_id, referred_id):
        # Удаляем капчу если она есть
        cursor.execute('DELETE FROM referral_captcha WHERE referred_id = ?', (referred_id,))
        conn.commit()
        return False  # Уже обработан
    
    # Удаляем капчу
    cursor.execute('DELETE FROM referral_captcha WHERE referred_id = ?', (referred_id,))
    
    # Добавляем реферала
    add_referral(referrer_id, referred_id)
    
    # Начисляем бонусы только после проверки подписки на обязательный канал
    cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (referred_id,))
    conn.commit()
    
    return True

def give_referral_reward(referrer_id, referred_id):
    """Выдает награду за реферала (после подписки на обязательный канал)"""
    # Проверяем, не выдана ли уже награда
    if is_referral_reward_given(referrer_id, referred_id):
        return False
    
    # Начисляем бонусы рефереру
    update_balance(referrer_id, 3, f"Бонус за реферала {referred_id}")
    cursor.execute('UPDATE users SET earned_from_refs = earned_from_refs + 3 WHERE user_id = ?', (referrer_id,))
    
    # Начисляем бонусы рефералу
    update_balance(referred_id, 3, f"Бонус за регистрацию по реферальной ссылке")
    
    # Помечаем, что награда выдана
    mark_referral_reward_given(referrer_id, referred_id)
    
    # Помечаем регистрацию как завершенную
    set_registration_completed(referred_id, True)
    
    conn.commit()
    return True

# Функции для администраторов
def get_user_by_username(username):
    """Поиск пользователя по username"""
    cursor.execute('SELECT user_id, username, balance FROM users WHERE username = ?', (username,))
    return cursor.fetchone()

def get_all_users():
    """Получение всех пользователей"""
    cursor.execute('SELECT user_id, username, balance FROM users')
    return cursor.fetchall()

def get_user_stats():
    """Получение общей статистики"""
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(balance) FROM users')
    total_stars = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM channels')
    total_channels = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(referrals) FROM users')
    total_referrals = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(earned_from_refs) FROM users')
    total_earned_refs = cursor.fetchone()[0] or 0
    
    return {
        'total_users': total_users,
        'total_stars': total_stars,
        'total_channels': total_channels,
        'total_referrals': total_referrals,
        'total_earned_refs': total_earned_refs
    }

def get_referrals_by_user(user_id):
    """Получает список рефералов пользователя"""
    cursor.execute('''
        SELECT ra.referred_id, u.username, ra.activated_at 
        FROM referral_activations ra
        JOIN users u ON ra.referred_id = u.user_id
        WHERE ra.referrer_id = ?
        ORDER BY ra.activated_at DESC
    ''', (user_id,))
    return cursor.fetchall()

# НОВЫЕ ФУНКЦИИ

# Функции для событий (ивентов)
def create_event(name, event_type, multiplier=1, bonus=0, duration_hours=24):
    start = datetime.now()
    end = datetime.fromtimestamp(start.timestamp() + duration_hours * 3600)
    cursor.execute('''
        INSERT INTO events (name, type, multiplier, bonus, start_time, end_time, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', (name, event_type, multiplier, bonus, start, end))
    conn.commit()
    return cursor.lastrowid

def deactivate_expired_events():
    now = datetime.now()
    cursor.execute('UPDATE events SET is_active = 0 WHERE end_time < ?', (now,))
    conn.commit()

def get_active_event(event_type):
    cursor.execute('SELECT * FROM events WHERE type = ? AND is_active = 1 AND start_time <= datetime("now") AND end_time >= datetime("now")', (event_type,))
    return cursor.fetchone()

def get_all_events():
    cursor.execute('SELECT id, name, type, multiplier, bonus, start_time, end_time, is_active FROM events ORDER BY start_time DESC')
    return cursor.fetchall()

def toggle_event(event_id, active):
    cursor.execute('UPDATE events SET is_active = ? WHERE id = ?', (1 if active else 0, event_id))
    conn.commit()

def delete_event(event_id):
    cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()

# Функции для админ-логов
def log_admin_action(admin_id, admin_username, action, target_user_id=None, details=None):
    cursor.execute('''
        INSERT INTO admin_logs (admin_id, admin_username, action, target_user_id, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (admin_id, admin_username, action, target_user_id, details))
    conn.commit()

def get_admin_logs(limit=50):
    cursor.execute('''
        SELECT admin_id, admin_username, action, target_user_id, details, created_at
        FROM admin_logs ORDER BY created_at DESC LIMIT ?
    ''', (limit,))
    return cursor.fetchall()

# Функции для банов
def ban_user(user_id, banned_by, reason=None):
    cursor.execute('INSERT OR IGNORE INTO bans (user_id, banned_by, reason) VALUES (?, ?, ?)', (user_id, banned_by, reason))
    cursor.execute('UPDATE users SET banned = 1 WHERE user_id = ?', (user_id,))
    conn.commit()

def unban_user(user_id):
    cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE users SET banned = 0 WHERE user_id = ?', (user_id,))
    conn.commit()

def is_banned(user_id):
    cursor.execute('SELECT banned FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

# Функции для казино
def add_casino_game(user_id, bet, result, win, multiplier):
    cursor.execute('''
        INSERT INTO casino_games (user_id, bet, result, win, multiplier)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, bet, result, win, multiplier))
    # Обновляем статистику пользователя
    if win > 0:
        cursor.execute('UPDATE users SET total_casino_win = total_casino_win + ? WHERE user_id = ?', (win, user_id))
    else:
        cursor.execute('UPDATE users SET total_casino_loss = total_casino_loss + ? WHERE user_id = ?', (bet, user_id))
    conn.commit()

def get_user_casino_stats(user_id):
    cursor.execute('SELECT total_casino_win, total_casino_loss FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone() or (0, 0)

# Функции для рейтингов
def get_top_by_referrals(limit=10):
    cursor.execute('''
        SELECT user_id, username, referrals 
        FROM users 
        WHERE referrals > 0 
        ORDER BY referrals DESC 
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()

def get_top_by_balance(limit=10):
    cursor.execute('''
        SELECT user_id, username, balance 
        FROM users 
        WHERE balance > 0 
        ORDER BY balance DESC 
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()

def get_top_by_casino_wins(limit=10):
    cursor.execute('''
        SELECT user_id, username, total_casino_win 
        FROM users 
        WHERE total_casino_win > 0 
        ORDER BY total_casino_win DESC 
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()

# Функции для экспорта пользователей
def get_all_users_full():
    cursor.execute('''
        SELECT user_id, username, balance, referrals, earned_from_refs, last_active, banned,
               total_casino_win, total_casino_loss
        FROM users
    ''')
    return cursor.fetchall()

# Функция для получения истории пользователя
def get_user_full_history(user_id):
    history = {}
    # Транзакции
    cursor.execute('SELECT amount, transaction_type, description, created_at FROM user_transactions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    history['transactions'] = cursor.fetchall()
    # Рефералы
    cursor.execute('SELECT referred_id, activated_at FROM referral_activations WHERE referrer_id = ?', (user_id,))
    history['referrals'] = cursor.fetchall()
    # Казино
    cursor.execute('SELECT bet, result, win, multiplier, created_at FROM casino_games WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    history['casino'] = cursor.fetchall()
    # Задания
    cursor.execute('''
        SELECT c.channel_username, uc.completed_at, uc.stars_awarded 
        FROM user_channels uc
        JOIN channels c ON uc.channel_id = c.id
        WHERE uc.user_id = ? AND uc.completed = 1
    ''', (user_id,))
    history['tasks'] = cursor.fetchall()
    return history