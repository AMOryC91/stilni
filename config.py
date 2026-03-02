# config.py

# Токен бота
API_TOKEN = '8583210329:AAHl8LCjTqOu6KeyDjptjuNppvk15APIQBk'

# ID администраторов
ADMIN_IDS = [8558014654, 1890263091, 8139801428, 6012850351, 7083546977]
TECH_ADMIN_IDS = [1890263091]  # Технические администраторы

# Обязательный канал
REQUIRED_CHANNEL_ID = '-1003504791986'  # ID обязательного канала
REQUIRED_CHANNEL_LINK = 'https://t.me/stilni1000'  # Ссылка для подписки

# Настройки базы данных
DB_NAME = 'bot_database.db'

# Другие настройки
CHECK_SUBSCRIPTION_INTERVAL = 300  # Интервал проверки подписок (в секундах)
CAPTCHA_ATTEMPTS = 3  # Количество попыток для капчи
REFERRAL_REWARD = 3  # Награда за реферала
TASK_REWARD = 2  # Награда за задание
MIN_WITHDRAWAL = 15  # Минимальная сумма вывода
MAX_WITHDRAWAL = 100  # Максимальная сумма вывода за раз

# Настройки для событий (ивентов)
EVENT_REFERRAL_BONUS = 4  # Бонус за реферала во время ивента
EVENT_CASINO_MULTIPLIER = 5  # Множитель в казино во время ивента
EVENT_TASK_REWARD = 3  # Награда за задание во время ивента

# Настройки для охоты за 777
HUNT_777_ENABLED = True  # По умолчанию включена рассылка
HUNT_777_BROADCAST = True  # Рассылать ли сообщение о 777

# Путь для резервных копий
BACKUP_PATH = 'backups/'