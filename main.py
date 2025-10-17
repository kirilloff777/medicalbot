#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#"""
#Telegram Bot для напоминаний о приёме лекарств
#Создан для Ксюши ❤️
#"""

import logging
import sqlite3
import random
import asyncio
import os
from datetime import datetime, timedelta, date, time as dt_time
from typing import Dict, List, Optional
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# ============= КОНФИГУРАЦИЯ =============

# Токен из GitHub Secrets
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Пробуем получить ADMIN_ID из GitHub Secrets
admin_id_env = os.environ.get('ADMIN_ID')

# Если переменная отсутствует — используем запасной ID (например, твой)
# 👇 замените 55948371 на свой реальный Telegram ID
ADMIN_ID = int(admin_id_env) if admin_id_env and admin_id_env.isdigit() else 55948371

# Проверка токена
if not BOT_TOKEN:
    raise ValueError(
        "❌ BOT_TOKEN не найден!\n"
        "Добавьте его в GitHub Secrets:\n"
        "Settings → Secrets and variables → Actions → New secret\n"
        "Name: BOT_TOKEN\n"
        "Value: токен от @BotFather"
    )

# Часовой пояс
TIMEZONE = pytz.timezone('Europe/Moscow')

# База данных
DATABASE_NAME = 'medications.db'

# Обращения
NICKNAMES = ["Солнышко", "Мышка", "Котёнок", "Любимая", "Ксюшенька"]

# Фразы похвалы
PRAISE_MESSAGES = [
        "🌟 Умничка, горжусь тобой!",
        "💪 Молодец, так держать!",
        "❤️ Отлично, котёнок!",
        "🎉 Супер! Ты большая умница!",
        "💖 Я в тебя верю, продолжай в том же духе!",
        "✨ Прекрасно! Ты справляешься!",
        "🌺 Солнышко моё, ты лучшая!"
    ]

# Фразы при откладывании
POSTPONE_MESSAGES = [
        "😊 Хорошо, напомню позже",
        "👌 Ладно, напишу чуть попозже",
        "💫 Без проблем, солнышко",
        "🕐 Окей, напомню снова",
        "💝 Хорошо, но не забудь!",
        "☺️ Понятно, вернусь к тебе через время",
        "🤗 Не вопрос, вернусь позже"
    ]

# Периоды дня
PERIODS = {
    'morning': '🌅 Утро',
    'day': '☀️ День',
    'evening': '🌆 Вечер',
    'night': '🌙 Ночь'
}

# Дни недели
WEEKDAYS_FULL = {
    0: 'Понедельник',
    1: 'Вторник',
    2: 'Среда',
    3: 'Четверг',
    4: 'Пятница',
    5: 'Суббота',
    6: 'Воскресенье'
}

WEEKDAYS_SHORT = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}

# Достижения
ACHIEVEMENTS = {
    'first_pill': {'name': '🏆 Первая таблетка', 'description': 'Выпила первую таблетку'},
    'week_streak': {'name': '🔥 Неделя без пропусков', 'description': '7 дней подряд без пропусков'},
    'first_course': {'name': '💯 Первый завершённый курс', 'description': 'Завершила первый курс'},
    'three_courses': {'name': '💪 Три курса завершено', 'description': 'Завершила три курса'},
    'fifty_pills': {'name': '⭐️ 50 таблеток принято', 'description': 'Приняла 50 таблеток'},
    'hundred_pills': {'name': '🌟 100 таблеток принято', 'description': 'Приняла 100 таблеток'},
    'month_streak': {'name': '👑 Месяц без пропусков', 'description': '30 дней подряд без пропусков'},
    'perfect_course': {'name': '🎯 Идеальный курс', 'description': 'Завершила курс без единого пропуска'}
}

# Состояния ConversationHandler
(ADD_MED_NAME, ADD_MED_DURATION, ADD_MED_DURATION_INPUT, 
 ADD_MED_SCHEDULE_TYPE, ADD_MED_WEEKDAYS, ADD_MED_FREQUENCY,
 ADD_MED_TIMES_PERIOD, ADD_MED_TIME_INPUT, ADD_MED_REMINDER,
 ADD_MED_DOSAGE_CHOICE, ADD_MED_DOSAGE_SCHEME, ADD_MED_CONFIRM,
 EDIT_MED_SELECT, EDIT_MED_ACTION, EDIT_MED_VALUE,
 ADMIN_BROADCAST, EDIT_MED_NAME, EDIT_MED_NAME_INPUT, 
 EDIT_MED_DURATION, EDIT_MED_DURATION_INPUT, 
 EDIT_MED_SCHEDULE_TYPE, EDIT_MED_WEEKDAYS, 
 EDIT_MED_FREQUENCY, EDIT_MED_TIMES_PERIOD, EDIT_MED_TIME_INPUT, 
 EDIT_MED_REMINDER, EDIT_MED_CONFIRM) = range(27)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============= БАЗА ДАННЫХ =============

def get_connection():
    """Создаёт подключение к БД"""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

from contextlib import contextmanager

@contextmanager
def get_db():
    """Context manager для безопасной работы с БД"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def init_database():
    """Инициализация базы данных"""
    conn = get_connection()
    c = conn.cursor()

    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        name TEXT,
        authorized BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Добавляем поле authorized если его нет (для существующих БД)
    try:
        c.execute('ALTER TABLE users ADD COLUMN authorized BOOLEAN DEFAULT 0')
        # Автоматически авторизуем всех существующих пользователей при миграции
        c.execute('UPDATE users SET authorized = 1 WHERE authorized IS NULL OR authorized = 0')
        logger.info("✅ Миграция: все существующие пользователи авторизованы")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует

    # Таблица лекарств
    c.execute('''CREATE TABLE IF NOT EXISTS medications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        duration_days INTEGER NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        schedule_type TEXT DEFAULT 'daily',
        weekdays TEXT,
        has_dosage_scheme BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Таблица расписаний приёма
    c.execute('''CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medication_id INTEGER NOT NULL,
        time TEXT NOT NULL,
        period TEXT NOT NULL,
        reminder_interval INTEGER DEFAULT 60,
        FOREIGN KEY (medication_id) REFERENCES medications(id)
    )''')

    # Таблица логов приёмов
    c.execute('''CREATE TABLE IF NOT EXISTS medication_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medication_id INTEGER NOT NULL,
        schedule_id INTEGER NOT NULL,
        scheduled_date DATE NOT NULL,
        scheduled_time TEXT NOT NULL,
        taken_time TIMESTAMP,
        status TEXT NOT NULL,
        postpone_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (medication_id) REFERENCES medications(id),
        FOREIGN KEY (schedule_id) REFERENCES schedules(id)
    )''')

    # Таблица схем дозировки
    c.execute('''CREATE TABLE IF NOT EXISTS dosage_schemes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medication_id INTEGER NOT NULL,
        day_from INTEGER NOT NULL,
        day_to INTEGER NOT NULL,
        dosage TEXT NOT NULL,
        times TEXT NOT NULL,
        FOREIGN KEY (medication_id) REFERENCES medications(id)
    )''')

    # Таблица достижений
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        achievement_type TEXT NOT NULL,
        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, achievement_type),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Таблица отложенных напоминаний
    c.execute('''CREATE TABLE IF NOT EXISTS postponed_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medication_id INTEGER NOT NULL,
        schedule_id INTEGER NOT NULL,
        user_telegram_id INTEGER NOT NULL,
        scheduled_date DATE NOT NULL,
        original_time TIMESTAMP NOT NULL,
        next_reminder_time TIMESTAMP NOT NULL,
        postpone_count INTEGER DEFAULT 1,
        reminder_interval INTEGER DEFAULT 60,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (medication_id) REFERENCES medications(id),
        FOREIGN KEY (schedule_id) REFERENCES schedules(id)
    )''')

    # Миграция: добавляем reminder_interval если нет
    try:
        c.execute('ALTER TABLE postponed_reminders ADD COLUMN reminder_interval INTEGER DEFAULT 60')
        logger.info("✅ Миграция: добавлена колонка reminder_interval в postponed_reminders")
    except sqlite3.OperationalError:
        pass  # Уже существует

    # Таблица активных (неотвеченных) напоминаний для автоповтора
    c.execute('''CREATE TABLE IF NOT EXISTS active_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medication_id INTEGER NOT NULL,
        schedule_id INTEGER NOT NULL,
        user_telegram_id INTEGER NOT NULL,
        scheduled_date DATE NOT NULL,
        first_reminder_time TIMESTAMP NOT NULL,
        last_reminder_time TIMESTAMP NOT NULL,
        reminder_count INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (medication_id) REFERENCES medications(id),
        FOREIGN KEY (schedule_id) REFERENCES schedules(id),
        UNIQUE(medication_id, schedule_id, scheduled_date)
    )''')

    # Автоматически авторизуем админа
    c.execute('SELECT id FROM users WHERE telegram_id = ?', (ADMIN_ID,))
    if c.fetchone():
        c.execute('UPDATE users SET authorized = 1 WHERE telegram_id = ?', (ADMIN_ID,))

    # Создаём индексы для оптимизации запросов
    try:
        c.execute('CREATE INDEX IF NOT EXISTS idx_medications_user_active ON medications(user_id, is_active)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_medications_dates ON medications(start_date, end_date)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_schedules_medication ON schedules(medication_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_logs_medication_date ON medication_logs(medication_id, scheduled_date)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_logs_user_date ON medication_logs(medication_id, scheduled_date)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_postponed_user ON postponed_reminders(user_telegram_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_active_reminders_user ON active_reminders(user_telegram_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_active_reminders_time ON active_reminders(last_reminder_time)')
        logger.info("✅ Индексы созданы")
    except sqlite3.OperationalError as e:
        logger.warning(f"Индексы уже существуют: {e}")

    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# Функции работы с пользователями
def get_or_create_user(telegram_id: int, name: str = None) -> int:
    """Получает ID пользователя или создаёт нового"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            # Используем INSERT OR IGNORE для предотвращения race condition
            is_authorized = 1 if telegram_id == ADMIN_ID else 0
            c.execute('''INSERT OR IGNORE INTO users 
                         (telegram_id, name, authorized) 
                         VALUES (?, ?, ?)''', 
                      (telegram_id, name, is_authorized))

            # Теперь безопасно получаем ID
            c.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
            result = c.fetchone()
            return result['id']
    except Exception as e:
        logger.error(f"❌ Ошибка get_or_create_user: {e}")
        raise

def is_user_authorized(telegram_id: int) -> bool:
    """Проверяет, авторизован ли пользователь"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT authorized FROM users WHERE telegram_id = ?', (telegram_id,))
            result = c.fetchone()

            if result:
                return bool(result['authorized'])
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка is_user_authorized: {e}")
        return False

def set_user_authorization(telegram_id: int, authorized: bool):
    """Устанавливает статус авторизации пользователя"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET authorized = ? WHERE telegram_id = ?', 
                      (1 if authorized else 0, telegram_id))
    except Exception as e:
        logger.error(f"❌ Ошибка set_user_authorization: {e}")
        raise

async def request_user_authorization(telegram_id: int, name: str, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет запрос админу на авторизацию нового пользователя"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Разрешить", callback_data=f"auth_approve_{telegram_id}"),
            InlineKeyboardButton("❌ Запретить", callback_data=f"auth_deny_{telegram_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"🔔 <b>Новый пользователь запрашивает доступ</b>\n\n"
        f"👤 Имя: {name}\n"
        f"🆔 ID: {telegram_id}\n\n"
        f"Разрешить использование бота?"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Ошибка отправки запроса на авторизацию: {e}")

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Получает пользователя по ID"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            result = c.fetchone()
            return dict(result) if result else None
    except Exception as e:
        logger.error(f"❌ Ошибка get_user_by_id: {e}")
        return None

def get_all_users() -> List[Dict]:
    """Получает всех пользователей"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM users ORDER BY created_at DESC')
            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_all_users: {e}")
        return []

# Функции работы с лекарствами
def create_medication(user_id: int, name: str, duration_days: int, 
                     start_date: date, schedule_type: str = 'daily',
                     weekdays: str = None, has_dosage_scheme: bool = False) -> int:
    """Создаёт новое лекарство"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            end_date = start_date + timedelta(days=duration_days - 1)

            c.execute('''INSERT INTO medications 
                         (user_id, name, duration_days, start_date, end_date, 
                          schedule_type, weekdays, has_dosage_scheme)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (user_id, name, duration_days, start_date.isoformat(), 
                       end_date.isoformat(), schedule_type, weekdays, has_dosage_scheme))

            medication_id = c.lastrowid
            return medication_id
    except Exception as e:
        logger.error(f"Error creating medication: {e}")
        raise

def get_active_medications(user_id: int) -> List[Dict]:
    """Получает активные лекарства пользователя"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('''SELECT * FROM medications 
                         WHERE user_id = ? AND is_active = 1
                         ORDER BY start_date DESC''', (user_id,))

            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_active_medications: {e}")
        return []

def get_completed_medications(user_id: int, limit: int = 20) -> List[Dict]:
    """Получает завершённые лекарства"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('''SELECT * FROM medications 
                         WHERE user_id = ? AND is_active = 0
                         ORDER BY end_date DESC LIMIT ?''', (user_id, limit))

            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_completed_medications: {e}")
        return []

def get_medication_by_id(medication_id: int) -> Optional[Dict]:
    """Получает лекарство по ID"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('SELECT * FROM medications WHERE id = ?', (medication_id,))
            result = c.fetchone()

            return dict(result) if result else None
    except Exception as e:
        logger.error(f"❌ Ошибка get_medication_by_id: {e}")
        return None

def update_medication(medication_id: int, **kwargs):
    """Обновляет данные лекарства"""
    ALLOWED_FIELDS = {
        'name', 'duration_days', 'start_date', 'end_date', 'is_active',
        'schedule_type', 'weekdays', 'has_dosage_scheme'
    }

    # Фильтруем только разрешенные поля
    safe_kwargs = {k: v for k, v in kwargs.items() if k in ALLOWED_FIELDS}

    if not safe_kwargs:
        raise ValueError("No valid fields to update")

    try:
        with get_db() as conn:
            c = conn.cursor()

            fields = ', '.join([f"{k} = ?" for k in safe_kwargs.keys()])
            values = list(safe_kwargs.values()) + [medication_id]

            c.execute(f'UPDATE medications SET {fields} WHERE id = ?', values)
    except Exception as e:
        logger.error(f"Error updating medication: {e}")
        raise

def deactivate_medication(medication_id: int):
    """Деактивирует лекарство"""
    update_medication(medication_id, is_active=0)

def delete_medication_by_id(medication_id: int):
    """Удаляет лекарство и связанные записи"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('DELETE FROM medications WHERE id = ?', (medication_id,))
            c.execute('DELETE FROM schedules WHERE medication_id = ?', (medication_id,))
            c.execute('DELETE FROM medication_logs WHERE medication_id = ?', (medication_id,))
            c.execute('DELETE FROM dosage_schemes WHERE medication_id = ?', (medication_id,))
            c.execute('DELETE FROM postponed_reminders WHERE medication_id = ?', (medication_id,))
    except Exception as e:
        logger.error(f"Error deleting medication: {e}")
        raise

def extend_medication_course(medication_id: int, extra_days: int):
    """Продлевает курс лекарства"""
    med = get_medication_by_id(medication_id)
    if not med:
        return

    end_date = datetime.strptime(med['end_date'], '%Y-%m-%d').date()
    new_end_date = end_date + timedelta(days=extra_days)
    new_duration = med['duration_days'] + extra_days

    update_medication(medication_id, 
                     end_date=new_end_date.isoformat(),
                     duration_days=new_duration)

# Функции работы с расписаниями
def create_schedule(medication_id: int, time_str: str, period: str, 
                   reminder_interval: int = 60) -> int:
    """Создаёт расписание приёма"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('''INSERT INTO schedules 
                         (medication_id, time, period, reminder_interval)
                         VALUES (?, ?, ?, ?)''',
                      (medication_id, time_str, period, reminder_interval))

            return c.lastrowid
    except Exception as e:
        logger.error(f"❌ Ошибка create_schedule: {e}")
        raise

def get_medication_schedules(medication_id: int) -> List[Dict]:
    """Получает все расписания для лекарства"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('SELECT * FROM schedules WHERE medication_id = ? ORDER BY time',
                      (medication_id,))

            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_medication_schedules: {e}")
        return []

def delete_medication_schedules(medication_id: int):
    """Удаляет все расписания лекарства"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('DELETE FROM schedules WHERE medication_id = ?', (medication_id,))
    except Exception as e:
        logger.error(f"❌ Ошибка delete_medication_schedules: {e}")
        raise

# Функции работы с логами
def log_medication_taken(medication_id: int, schedule_id: int, 
                        scheduled_date: date, scheduled_time: str):
    """Логирует приём лекарства"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            taken_time = datetime.now(TIMEZONE)

            c.execute('''INSERT INTO medication_logs 
                         (medication_id, schedule_id, scheduled_date, scheduled_time, 
                          taken_time, status)
                         VALUES (?, ?, ?, ?, ?, 'taken')''',
                      (medication_id, schedule_id, scheduled_date.isoformat(), 
                       scheduled_time, taken_time.isoformat()))

            logger.info(f"✅ Принято лекарство {medication_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка log_medication_taken: {e}")
        raise

def log_medication_missed(medication_id: int, schedule_id: int,
                         scheduled_date: date, scheduled_time: str):
    """Логирует пропуск приёма"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('''INSERT INTO medication_logs 
                         (medication_id, schedule_id, scheduled_date, scheduled_time, 
                          status)
                         VALUES (?, ?, ?, ?, 'missed')''',
                      (medication_id, schedule_id, scheduled_date.isoformat(), 
                       scheduled_time))
    except Exception as e:
        logger.error(f"❌ Ошибка log_medication_missed: {e}")
        raise

def get_medication_logs(medication_id: int, limit: int = 100) -> List[Dict]:
    """Получает логи приёмов лекарства"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('''SELECT * FROM medication_logs 
                         WHERE medication_id = ? 
                         ORDER BY scheduled_date DESC, scheduled_time DESC 
                         LIMIT ?''', (medication_id, limit))

            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_medication_logs: {e}")
        return []

def get_logs_for_date(user_id: int, target_date: date) -> List[Dict]:
    """Получает логи за определённую дату"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('''SELECT ml.*, m.name as medication_name, s.period, s.time
                         FROM medication_logs ml
                         JOIN medications m ON ml.medication_id = m.id
                         JOIN schedules s ON ml.schedule_id = s.id
                         WHERE m.user_id = ? AND ml.scheduled_date = ?
                         ORDER BY ml.scheduled_time''',
                      (user_id, target_date.isoformat()))

            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_logs_for_date: {e}")
        return []

# Функции для достижений
def unlock_achievement(user_id: int, achievement_type: str) -> bool:
    """Разблокирует достижение. Возвращает True если новое"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO achievements (user_id, achievement_type)
                         VALUES (?, ?)''', (user_id, achievement_type))
            return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка unlock_achievement: {e}")
        return False

def get_user_achievements(user_id: int) -> List[Dict]:
    """Получает все достижения пользователя"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('''SELECT * FROM achievements 
                         WHERE user_id = ? 
                         ORDER BY unlocked_at DESC''', (user_id,))

            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_user_achievements: {e}")
        return []

# Функции статистики
def get_user_statistics(user_id: int) -> Dict:
    """Получает статистику пользователя"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            # Завершённые курсы
            c.execute('''SELECT COUNT(*) as count FROM medications 
                         WHERE user_id = ? AND is_active = 0''', (user_id,))
            completed_courses = c.fetchone()['count']

            # Принято таблеток
            c.execute('''SELECT COUNT(*) as count FROM medication_logs ml
                         JOIN medications m ON ml.medication_id = m.id
                         WHERE m.user_id = ? AND ml.status = 'taken' ''', (user_id,))
            total_taken = c.fetchone()['count']

            # Пропущено
            c.execute('''SELECT COUNT(*) as count FROM medication_logs ml
                         JOIN medications m ON ml.medication_id = m.id
                         WHERE m.user_id = ? AND ml.status = 'missed' ''', (user_id,))
            total_missed = c.fetchone()['count']

            # Процент успешности
            total_logs = total_taken + total_missed
            success_rate = (total_taken / total_logs * 100) if total_logs > 0 else 0

            # Текущая серия
            c.execute('''SELECT scheduled_date, status FROM medication_logs ml
                         JOIN medications m ON ml.medication_id = m.id
                         WHERE m.user_id = ?
                         ORDER BY scheduled_date DESC, scheduled_time DESC
                         LIMIT 100''', (user_id,))

            logs = c.fetchall()
            current_streak = 0
            dates_checked = set()

            for log in logs:
                log_date = log['scheduled_date']
                if log_date not in dates_checked:
                    dates_checked.add(log_date)
                    if log['status'] == 'taken':
                        current_streak += 1
                    else:
                        break

            return {
                'completed_courses': completed_courses,
                'total_taken': total_taken,
                'total_missed': total_missed,
                'success_rate': round(success_rate, 1),
                'current_streak': current_streak
            }
    except Exception as e:
        logger.error(f"❌ Ошибка get_user_statistics: {e}")
        return {
            'completed_courses': 0,
            'total_taken': 0,
            'total_missed': 0,
            'success_rate': 0,
            'current_streak': 0
        }

# Отложенные напоминания
def create_or_update_postponed_reminder(medication_id: int, schedule_id: int, user_telegram_id: int,
                                        scheduled_date: date, original_time: datetime, 
                                        next_time: datetime, reminder_interval: int, postpone_count: int = 1):
    """Создаёт или обновляет отложенное напоминание"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            # Проверяем существующий для этой даты/sched
            c.execute('''SELECT id, postpone_count FROM postponed_reminders 
                         WHERE medication_id = ? AND schedule_id = ? AND scheduled_date = ?''',
                      (medication_id, schedule_id, scheduled_date.isoformat()))
            existing = c.fetchone()

            if existing:
                new_count = existing['postpone_count'] + postpone_count
                c.execute('''UPDATE postponed_reminders SET 
                             next_reminder_time = ?, postpone_count = ?, reminder_interval = ?
                             WHERE id = ?''',
                          (next_time.isoformat(), new_count, reminder_interval, existing['id']))
            else:
                c.execute('''INSERT INTO postponed_reminders 
                             (medication_id, schedule_id, user_telegram_id, scheduled_date,
                              original_time, next_reminder_time, postpone_count, reminder_interval)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (medication_id, schedule_id, user_telegram_id, scheduled_date.isoformat(),
                           original_time.isoformat(), next_time.isoformat(), postpone_count, reminder_interval))
    except Exception as e:
        logger.error(f"❌ Ошибка create_or_update_postponed_reminder: {e}")
        raise

def get_due_postponed_reminders() -> List[Dict]:
    """Получает отложенные напоминания, которые пора отправить"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            now = datetime.now(TIMEZONE).isoformat()

            c.execute('''SELECT * FROM postponed_reminders 
                         WHERE next_reminder_time <= ?''', (now,))

            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_due_postponed_reminders: {e}")
        return []

def delete_postponed_reminder(reminder_id: int):
    """Удаляет отложенное напоминание"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute('DELETE FROM postponed_reminders WHERE id = ?', (reminder_id,))
    except Exception as e:
        logger.error(f"❌ Ошибка delete_postponed_reminder: {e}")
        raise

# Активные напоминания (для автоповтора)
def create_active_reminder(medication_id: int, schedule_id: int, user_telegram_id: int,
                           scheduled_date: date):
    """Создаёт активное напоминание для отслеживания"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            now = datetime.now(TIMEZONE)
            
            # Используем INSERT OR IGNORE чтобы избежать дубликатов
            c.execute('''INSERT OR IGNORE INTO active_reminders 
                         (medication_id, schedule_id, user_telegram_id, scheduled_date,
                          first_reminder_time, last_reminder_time, reminder_count)
                         VALUES (?, ?, ?, ?, ?, ?, 1)''',
                      (medication_id, schedule_id, user_telegram_id, scheduled_date.isoformat(),
                       now.isoformat(), now.isoformat()))
    except Exception as e:
        logger.error(f"❌ Ошибка create_active_reminder: {e}")
        raise

def get_unanswered_reminders() -> List[Dict]:
    """Получает напоминания, которые нужно повторить (прошло 15+ минут, меньше 5 попыток)"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            now = datetime.now(TIMEZONE)
            fifteen_min_ago = (now - timedelta(minutes=15)).isoformat()
            
            c.execute('''SELECT * FROM active_reminders 
                         WHERE last_reminder_time <= ? AND reminder_count < 5''',
                      (fifteen_min_ago,))
            
            results = c.fetchall()
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"❌ Ошибка get_unanswered_reminders: {e}")
        return []

def delete_active_reminder(medication_id: int, schedule_id: int, scheduled_date: date):
    """Удаляет активное напоминание (когда пользователь ответил)"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''DELETE FROM active_reminders 
                         WHERE medication_id = ? AND schedule_id = ? AND scheduled_date = ?''',
                      (medication_id, schedule_id, scheduled_date.isoformat()))
    except Exception as e:
        logger.error(f"❌ Ошибка delete_active_reminder: {e}")
        raise

def update_active_reminder_count(reminder_id: int):
    """Обновляет счётчик повторов и время последнего напоминания"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            now = datetime.now(TIMEZONE)
            
            c.execute('''UPDATE active_reminders 
                         SET last_reminder_time = ?, reminder_count = reminder_count + 1
                         WHERE id = ?''',
                      (now.isoformat(), reminder_id))
    except Exception as e:
        logger.error(f"❌ Ошибка update_active_reminder_count: {e}")
        raise

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

def get_greeting_by_time():
    """Возвращает приветствие в зависимости от времени суток"""
    current_hour = datetime.now(TIMEZONE).hour

    if 6 <= current_hour < 11:
        return "🌅 Доброе утро"
    elif 11 <= current_hour < 17:
        return "☀️ Привет"
    elif 17 <= current_hour < 22:
        return "🌆 Добрый вечер"
    else:
        return "🌙"

def get_random_nickname():
    """Возвращает случайное обращение"""
    return random.choice(NICKNAMES)

def check_and_unlock_achievements(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и разблокирует достижения"""
    stats = get_user_statistics(user_id)
    unlocked = []

    # Первая таблетка
    if stats['total_taken'] >= 1:
        if unlock_achievement(user_id, 'first_pill'):
            unlocked.append('first_pill')

    # Неделя без пропусков
    if stats['current_streak'] >= 7:
        if unlock_achievement(user_id, 'week_streak'):
            unlocked.append('week_streak')

    # Месяц без пропусков
    if stats['current_streak'] >= 30:
        if unlock_achievement(user_id, 'month_streak'):
            unlocked.append('month_streak')

    # Завершённые курсы
    if stats['completed_courses'] >= 1:
        if unlock_achievement(user_id, 'first_course'):
            unlocked.append('first_course')

    if stats['completed_courses'] >= 3:
        if unlock_achievement(user_id, 'three_courses'):
            unlocked.append('three_courses')

    # Количество таблеток
    if stats['total_taken'] >= 50:
        if unlock_achievement(user_id, 'fifty_pills'):
            unlocked.append('fifty_pills')

    if stats['total_taken'] >= 100:
        if unlock_achievement(user_id, 'hundred_pills'):
            unlocked.append('hundred_pills')

    return unlocked

# ============= ВАЛИДАЦИЯ ДАННЫХ =============

def validate_date(date_str: str) -> tuple:
    """
    Проверяет корректность даты
    Возвращает: (valid, error_message, parsed_date)
    """
    try:
        parsed_date = datetime.strptime(date_str, '%d.%m.%Y').date()
        start_date = datetime.now(TIMEZONE).date()

        # Проверка на прошлое
        if parsed_date <= start_date:
            return False, "Дата должна быть в будущем!", None

        # Проверка на разумность (не больше 3 лет)
        max_date = start_date + timedelta(days=1095)  # 3 года
        if parsed_date > max_date:
            return False, "Дата слишком далеко в будущем (максимум 3 года)!", None

        return True, "", parsed_date

    except ValueError:
        return False, "Неверный формат даты! Используйте ДД.ММ.ГГГГ", None

def validate_time_format(time_str: str) -> bool:
    """Проверяет формат времени HH:MM"""
    try:
        datetime.strptime(time_str, '%H:%M')
        return True
    except ValueError:
        return False

# ============= ФУНКЦИИ НАВИГАЦИИ ДЛЯ ДОБАВЛЕНИЯ ЛЕКАРСТВ =============

def add_navigation_buttons(keyboard, step_number=None, show_back=True, show_cancel=True):
    """Добавляет кнопки навигации к клавиатуре"""
    nav_row = []
    if show_back and step_number and step_number > 1:
        nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data="nav_back"))
    if show_cancel:
        nav_row.append(InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med"))
    if nav_row:
        keyboard.append(nav_row)
    return keyboard

async def go_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат на предыдущий шаг"""
    query = update.callback_query
    await query.answer()

    # Получаем историю шагов
    step_history = context.user_data.get('step_history', [])

    if not step_history or len(step_history) < 2:
        # Если истории нет, отменяем
        return await cancel_add_medication(update, context)

    # Удаляем текущий шаг
    step_history.pop()

    # Получаем предыдущий шаг
    previous_step = step_history[-1]
    context.user_data['step_history'] = step_history

    # Переходим к предыдущему шагу
    if previous_step == ADD_MED_NAME:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "➕ <b>Добавление лекарства</b>\n\n"
            "📝 Шаг 1/8: Введите название лекарства:\n"
            "(Например: Аспирин, Витамин D)",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_NAME

    elif previous_step == ADD_MED_DURATION:
        keyboard = [
            [InlineKeyboardButton("3 дня", callback_data="duration_3"),
             InlineKeyboardButton("5 дней", callback_data="duration_5")],
            [InlineKeyboardButton("7 дней", callback_data="duration_7"),
             InlineKeyboardButton("10 дней", callback_data="duration_10")],
            [InlineKeyboardButton("14 дней", callback_data="duration_14"),
             InlineKeyboardButton("21 день", callback_data="duration_21")],
            [InlineKeyboardButton("30 дней", callback_data="duration_30")],
            [InlineKeyboardButton("✏️ Своя длительность", callback_data="duration_custom")],
            [InlineKeyboardButton("📅 Дата окончания", callback_data="duration_date")],
        ]
        keyboard = add_navigation_buttons(keyboard, step_number=2, show_back=True)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"💊 <b>{context.user_data.get('med_name', 'Лекарство')}</b>\n\n"
            "📅 Шаг 2/8: Выберите длительность курса:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_DURATION

    elif previous_step == ADD_MED_SCHEDULE_TYPE:
        keyboard = [
            [InlineKeyboardButton("Каждый день", callback_data="schedule_daily")],
            [InlineKeyboardButton("Через день", callback_data="schedule_every_other")],
            [InlineKeyboardButton("По дням недели", callback_data="schedule_weekdays")],
        ]
        keyboard = add_navigation_buttons(keyboard, step_number=3)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"💊 <b>{context.user_data.get('med_name')}</b>\n"
            f"📅 Курс: {context.user_data.get('med_duration')} дней\n\n"
            "📋 Шаг 3/8: Как часто принимать?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_SCHEDULE_TYPE

    elif previous_step == ADD_MED_WEEKDAYS:
        keyboard = []
        selected = context.user_data.get('selected_weekdays', [])
        for day_num, day_name in WEEKDAYS_FULL.items():
            icon = "☑️" if day_num in selected else "☐"
            keyboard.append([InlineKeyboardButton(f"{icon} {day_name}", callback_data=f"weekday_{day_num}")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="weekdays_done")])
        keyboard = add_navigation_buttons(keyboard, step_number=3)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"💊 <b>{context.user_data.get('med_name')}</b>\n\n"
            "📆 Выберите дни недели (можно несколько):",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_WEEKDAYS

    elif previous_step == ADD_MED_FREQUENCY:
        keyboard = [
            [InlineKeyboardButton("1 раз в день", callback_data="freq_1")],
            [InlineKeyboardButton("2 раза в день", callback_data="freq_2")],
            [InlineKeyboardButton("3 раза в день", callback_data="freq_3")],
            [InlineKeyboardButton("4 раза в день", callback_data="freq_4")],
        ]
        keyboard = add_navigation_buttons(keyboard, step_number=4)
        reply_markup = InlineKeyboardMarkup(keyboard)

        schedule_info = ""
        if context.user_data.get('schedule_type') == 'daily':
            schedule_info = "Каждый день"
        elif context.user_data.get('schedule_type') == 'every_other':
            schedule_info = "Через день"
        elif context.user_data.get('schedule_type') == 'weekdays':
            selected = context.user_data.get('selected_weekdays', [])
            days_str = ', '.join([WEEKDAYS_SHORT[d] for d in sorted(selected)])
            schedule_info = f"{days_str}"

        await query.message.edit_text(
            f"💊 <b>{context.user_data.get('med_name')}</b>\n"
            f"📅 Курс: {context.user_data.get('med_duration')} дней\n"
            f"📋 Приём: {schedule_info}\n\n"
            "🔢 Шаг 4/8: Сколько раз в день?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_FREQUENCY

    elif previous_step == ADD_MED_TIMES_PERIOD:
        current_index = context.user_data.get('current_time_index', 0)
        total = context.user_data.get('frequency', 1)

        keyboard = [
            [InlineKeyboardButton("🌅 Утро (6-11)", callback_data="period_morning")],
            [InlineKeyboardButton("☀️ День (11-17)", callback_data="period_day")],
            [InlineKeyboardButton("🌆 Вечер (17-22)", callback_data="period_evening")],
            [InlineKeyboardButton("🌙 Ночь (22-6)", callback_data="period_night")],
        ]
        keyboard = add_navigation_buttons(keyboard, step_number=5)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"💊 <b>{context.user_data.get('med_name')}</b>\n"
            f"⏰ Приём {current_index + 1}/{total}\n\n"
            "Шаг 5/8: Выберите период дня:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_TIMES_PERIOD

    # Для остальных шагов - отменяем
    return await cancel_add_medication(update, context)


# ============= ОБРАБОТЧИКИ КОМАНД =============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user

    # Создаём пользователя если не существует
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, authorized FROM users WHERE telegram_id = ?', (user.id,))
    result = c.fetchone()
    conn.close()

    # Определяем откуда вызвана команда (message или callback)
    if update.callback_query:
        send_message = update.callback_query.message.reply_text
    else:
        send_message = update.message.reply_text

    if not result:
        # Новый пользователь - создаём
        get_or_create_user(user.id, user.first_name)

        # Если не админ - отправляем запрос на авторизацию
        if user.id != ADMIN_ID:
            await request_user_authorization(user.id, user.first_name, context)
            await send_message(
                f"👋 Привет, {user.first_name}!\n\n"
                "📋 Ваш запрос на доступ к боту отправлен администратору.\n"
                "Пожалуйста, дождитесь одобрения.\n\n"
                "Вы получите уведомление, когда доступ будет разрешён."
            )
            return
    else:
        # Пользователь существует, проверяем авторизацию
        if not result['authorized'] and user.id != ADMIN_ID:
            # Неавторизованный пользователь - отправляем запрос админу
            await request_user_authorization(user.id, user.first_name, context)
            await send_message(
                f"👋 Привет, {user.first_name}!\n\n"
                "📋 Ваш запрос на доступ к боту отправлен администратору.\n"
                "Пожалуйста, дождитесь одобрения.\n\n"
                "Вы получите уведомление, когда доступ будет разрешён."
            )
            return

    # Проверяем авторизацию для всех остальных случаев
    if not is_user_authorized(user.id):
        await send_message(
            "❌ У вас нет доступа к этому боту.\n\n"
            "Ваш запрос на доступ ожидает одобрения администратора."
        )
        return

    # Авторизованный пользователь - показываем меню
    keyboard = [
        [KeyboardButton("💊 Лекарства"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📅 Календарь")],
        [KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await send_message(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я твой помощник по лекарствам.\n"
        "Помогу не забывать принимать таблетки вовремя! 💊\n\n"
        "Выбери нужный раздел:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = """❓ <b>Инструкция по использованию бота</b>

<b>💊 Лекарства</b>
• Просмотр текущих и завершённых курсов
• Информация о каждом лекарстве

<b>⚙️ Настройки</b>
• Добавить новое лекарство
• Редактировать существующие

<b>📊 Статистика</b>
• Завершённые курсы
• Принятые таблетки
• Процент успешности
• Достижения 🏆

<b>📅 Календарь</b>
• Визуальный календарь приёмов
• ✅ - Все приёмы выполнены
• ⚠️ - Пропущен 1 приём
• ❌ - Пропущено 2+ приёма

<b>🔔 Напоминания</b>
Бот напоминает о приёме в указанное время.
• <b>✅ Выпила</b> - отметить приём
• <b>⏰ Отложить</b> - напомнить позже

<b>📝 Как добавить лекарство:</b>
1. ⚙️ Настройки → ➕ Добавить
2. Введи название
3. Выбери длительность курса
4. Укажи частоту (каждый день/через день/по дням)
5. Выбери количество приёмов в день
6. Установи время приёмов
7. Настрой интервал напоминаний

<b>🎯 Достижения:</b>
🏆 Первая таблетка
🔥 Неделя без пропусков
💯 Первый курс
💪 Три курса
⭐️ 50 таблеток
🌟 100 таблеток
👑 Месяц без пропусков
🎯 Идеальный курс
"""

    if update.message:
        await update.message.reply_text(help_text, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(help_text, parse_mode='HTML')
        await update.callback_query.answer()

# ============= ОБРАБОТЧИКИ ЛЕКАРСТВ =============

async def medications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню лекарств"""
    keyboard = [
        [InlineKeyboardButton("📝 Текущие лекарства", callback_data="med_current")],
        [InlineKeyboardButton("✅ Выпитые лекарства", callback_data="med_completed")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "💊 <b>Лекарства</b>\n\nВыберите список:"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def show_current_medications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущие лекарства"""
    query = update.callback_query
    await query.answer()

    user_id = get_or_create_user(update.effective_user.id)
    medications = get_active_medications(user_id)

    if not medications:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="medications")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "📝 <b>Текущие лекарства</b>\n\n"
            "У вас пока нет активных лекарств.\n\n"
            "Добавьте через ⚙️ Настройки → ➕ Добавить лекарство",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

    text = "📝 <b>Текущие лекарства:</b>\n\n"
    keyboard = []

    today = datetime.now(TIMEZONE).date()

    for med in medications:
        start = datetime.strptime(med['start_date'], '%Y-%m-%d').date()
        end = datetime.strptime(med['end_date'], '%Y-%m-%d').date()

        days_passed = max(0, min((today - start).days + 1, med['duration_days']))
        days_left = max(0, (end - today).days)

        text += f"💊 <b>{med['name']}</b>\n"
        text += f"📅 Начало: {start.strftime('%d.%m.%Y')}\n"
        text += f"⏳ Принято: {days_passed} из {med['duration_days']} дней\n"
        text += f"📆 Осталось: {days_left} дней\n"
        text += f"🏁 Окончание: {end.strftime('%d.%m.%Y')}\n"

        # Добавляем время приёмов
        schedules = get_medication_schedules(med['id'])
        if schedules:
            times_str = ", ".join([f"{PERIODS.get(s['period'], '⏰')} {s['time']}" for s in schedules])
            text += f"⏰ Время: {times_str}\n"

        text += "\n"

        keyboard.append([InlineKeyboardButton(f"📋 {med['name']}", callback_data=f"med_detail_{med['id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="medications")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def show_completed_medications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает завершённые лекарства"""
    query = update.callback_query
    await query.answer()

    user_id = get_or_create_user(update.effective_user.id)
    medications = get_completed_medications(user_id)

    if not medications:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="medications")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "✅ <b>Выпитые лекарства</b>\n\n"
            "У вас пока нет завершённых курсов.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

    text = "✅ <b>Выпитые лекарства:</b>\n\n"

    for med in medications:
        start = datetime.strptime(med['start_date'], '%Y-%m-%d').date()
        end = datetime.strptime(med['end_date'], '%Y-%m-%d').date()

        text += f"💊 <b>{med['name']}</b>\n"
        text += f"📅 Курс: {start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}\n"
        text += f"⏱️ Длительность: {med['duration_days']} дней\n"
        text += f"✓ Завершён\n\n"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="medications")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def show_medication_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детали лекарства"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return

    schedules = get_medication_schedules(medication_id)

    start = datetime.strptime(med['start_date'], '%Y-%m-%d').date()
    end = datetime.strptime(med['end_date'], '%Y-%m-%d').date()
    today = datetime.now(TIMEZONE).date()

    days_passed = max(0, min((today - start).days + 1, med['duration_days']))
    days_left = max(0, (end - today).days)

    text = f"💊 <b>{med['name']}</b>\n\n"
    text += f"📅 Начало: {start.strftime('%d.%m.%Y')}\n"
    text += f"🏁 Окончание: {end.strftime('%d.%m.%Y')}\n"
    text += f"⏱️ Длительность: {med['duration_days']} дней\n"
    text += f"⏳ Принято: {days_passed} дней\n"
    text += f"📆 Осталось: {days_left} дней\n\n"

    if med['schedule_type'] == 'daily':
        text += "📋 Приём: Каждый день\n\n"
    elif med['schedule_type'] == 'every_other':
        text += "📋 Приём: Через день\n\n"
    elif med['schedule_type'] == 'weekdays':
        weekdays_list = med['weekdays'].split(',') if med['weekdays'] else []
        days_str = ', '.join([WEEKDAYS_SHORT[int(d)] for d in weekdays_list])
        text += f"📋 Приём: {days_str}\n\n"

    if schedules:
        text += "⏰ <b>Время приёмов:</b>\n"
        for sched in schedules:
            text += f"  • {PERIODS.get(sched['period'], '⏰')}: {sched['time']}\n"
        text += "\n"

    logs = get_medication_logs(medication_id, limit=1000)
    taken = len([l for l in logs if l['status'] == 'taken'])
    missed = len([l for l in logs if l['status'] == 'missed'])
    total = taken + missed

    if total > 0:
        success_rate = (taken / total) * 100
        text += f"📊 <b>Статистика:</b>\n"
        text += f"  ✅ Принято: {taken}\n"
        text += f"  ❌ Пропущено: {missed}\n"
        text += f"  📈 Успешность: {success_rate:.1f}%\n"

    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_med_{med['id']}")],
        [InlineKeyboardButton("🔙 К списку", callback_data="med_current")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

# ============= НАСТРОЙКИ =============

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить лекарство", callback_data="add_medication")],
        [InlineKeyboardButton("✏️ Редактировать лекарства", callback_data="edit_medications")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "⚙️ <b>Настройки</b>\n\nВыберите действие:"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

# ============= ДОБАВЛЕНИЕ ЛЕКАРСТВ =============
async def add_medication_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления лекарства"""
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    context.user_data['step_history'] = [ADD_MED_NAME]

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        "➕ <b>Добавление лекарства</b>\n\n"
        "📝 Шаг 1/8: Введите название лекарства:\n"
        "(Например: Аспирин, Витамин D)",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_NAME

async def add_medication_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение названия"""
    med_name = update.message.text.strip()
    context.user_data['med_name'] = med_name
    context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_DURATION]

    keyboard = [
        [InlineKeyboardButton("3 дня", callback_data="duration_3"),
         InlineKeyboardButton("5 дней", callback_data="duration_5")],
        [InlineKeyboardButton("7 дней", callback_data="duration_7"),
         InlineKeyboardButton("10 дней", callback_data="duration_10")],
        [InlineKeyboardButton("14 дней", callback_data="duration_14"),
         InlineKeyboardButton("21 день", callback_data="duration_21")],
        [InlineKeyboardButton("30 дней", callback_data="duration_30")],
        [InlineKeyboardButton("✏️ Своя длительность", callback_data="duration_custom")],
        [InlineKeyboardButton("📅 Дата окончания", callback_data="duration_date")],
    ]
    keyboard = add_navigation_buttons(keyboard, step_number=2, show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"💊 <b>{med_name}</b>\n\n"
        "📅 Шаг 2/8: Выберите длительность курса:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_DURATION

async def add_medication_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка длительности"""
    query = update.callback_query
    await query.answer()

    if query.data == "duration_custom":
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_DURATION_INPUT]

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="nav_back"),
                     InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n\n"
            "📝 Введите длительность в днях (1-365):",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_DURATION_INPUT

    elif query.data == "duration_date":
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_DURATION_INPUT]

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="nav_back"),
                     InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n\n"
            "📅 Введите дату окончания (ДД.ММ.ГГГГ):\n"
            "Например: 25.12.2025",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ADD_MED_DURATION_INPUT

    else:
        duration = int(query.data.split('_')[1])
        context.user_data['med_duration'] = duration
        context.user_data['med_start_date'] = datetime.now(TIMEZONE).date()
        context.user_data['med_end_date'] = context.user_data['med_start_date'] + timedelta(days=duration - 1)
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_SCHEDULE_TYPE]

        return await ask_schedule_type(query, context)

async def add_medication_duration_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод пользовательской длительности"""
    text = update.message.text.strip()

    if '.' in text:
        try:
            end_date = datetime.strptime(text, '%d.%m.%Y').date()
            start_date = datetime.now(TIMEZONE).date()

            if end_date <= start_date:
                await update.message.reply_text(
                    "❌ Дата должна быть в будущем!\n"
                    "Попробуйте снова (ДД.ММ.ГГГГ):"
                )
                return ADD_MED_DURATION_INPUT

            duration = (end_date - start_date).days + 1
            context.user_data['med_duration'] = duration
            context.user_data['med_start_date'] = start_date
            context.user_data['med_end_date'] = end_date
            context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_SCHEDULE_TYPE]

            keyboard = [
                [InlineKeyboardButton("Каждый день", callback_data="schedule_daily")],
                [InlineKeyboardButton("Через день", callback_data="schedule_every_other")],
                [InlineKeyboardButton("По дням недели", callback_data="schedule_weekdays")],
            ]
            keyboard = add_navigation_buttons(keyboard, step_number=3, show_back=True)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"💊 <b>{context.user_data['med_name']}</b>\n"
                f"📅 Курс: {duration} дней\n\n"
                "📋 Шаг 3/8: Как часто принимать?",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

            return ADD_MED_SCHEDULE_TYPE

        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат!\n"
                "Используйте: ДД.ММ.ГГГГ (например: 25.12.2025)"
            )
            return ADD_MED_DURATION_INPUT

    try:
        duration = int(text)
        if duration < 1 or duration > 365:
            await update.message.reply_text("❌ Введите число от 1 до 365:")
            return ADD_MED_DURATION_INPUT

        context.user_data['med_duration'] = duration
        context.user_data['med_start_date'] = datetime.now(TIMEZONE).date()
        context.user_data['med_end_date'] = context.user_data['med_start_date'] + timedelta(days=duration - 1)
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_SCHEDULE_TYPE]

        keyboard = [
            [InlineKeyboardButton("Каждый день", callback_data="schedule_daily")],
            [InlineKeyboardButton("Через день", callback_data="schedule_every_other")],
            [InlineKeyboardButton("По дням недели", callback_data="schedule_weekdays")],
        ]
        keyboard = add_navigation_buttons(keyboard, step_number=3, show_back=True)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n"
            f"📅 Курс: {duration} дней\n\n"
            "📋 Шаг 3/8: Как часто принимать?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        return ADD_MED_SCHEDULE_TYPE

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return ADD_MED_DURATION_INPUT

async def ask_schedule_type(query, context):
    """Запрос типа расписания"""
    keyboard = [
        [InlineKeyboardButton("Каждый день", callback_data="schedule_daily")],
        [InlineKeyboardButton("Через день", callback_data="schedule_every_other")],
        [InlineKeyboardButton("По дням недели", callback_data="schedule_weekdays")],
    ]
    keyboard = add_navigation_buttons(keyboard, step_number=3, show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"💊 <b>{context.user_data['med_name']}</b>\n"
        f"📅 Курс: {context.user_data['med_duration']} дней\n\n"
        "📋 Шаг 3/8: Как часто принимать?",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_SCHEDULE_TYPE

async def add_medication_schedule_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка типа расписания"""
    query = update.callback_query
    await query.answer()

    schedule_type = query.data.split('_', 1)[1]
    context.user_data['schedule_type'] = schedule_type

    if schedule_type == 'weekdays':
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_WEEKDAYS]

        keyboard = []
        for day_num, day_name in WEEKDAYS_FULL.items():
            keyboard.append([InlineKeyboardButton(f"☐ {day_name}", callback_data=f"weekday_{day_num}")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="weekdays_done")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="nav_back"),
                         InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['selected_weekdays'] = []

        await query.message.edit_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n\n"
            "📆 Выберите дни недели (можно несколько):",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        return ADD_MED_WEEKDAYS
    else:
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_FREQUENCY]
        return await ask_frequency(query, context)

async def add_medication_weekdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор дней недели"""
    query = update.callback_query

    if query.data == "weekdays_done":
        if not context.user_data.get('selected_weekdays'):
            await query.answer("❌ Выберите хотя бы один день!", show_alert=True)
            return ADD_MED_WEEKDAYS

        await query.answer()
        context.user_data['weekdays'] = ','.join(map(str, sorted(context.user_data['selected_weekdays'])))
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_FREQUENCY]
        return await ask_frequency(query, context)

    day_num = int(query.data.split('_')[1])
    selected = context.user_data.get('selected_weekdays', [])

    if day_num in selected:
        selected.remove(day_num)
    else:
        selected.append(day_num)

    context.user_data['selected_weekdays'] = selected

    keyboard = []
    for d_num, d_name in WEEKDAYS_FULL.items():
        icon = "☑️" if d_num in selected else "☐"
        keyboard.append([InlineKeyboardButton(f"{icon} {d_name}", callback_data=f"weekday_{d_num}")])
    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="weekdays_done")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="nav_back"),
                     InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer()
    await query.message.edit_reply_markup(reply_markup=reply_markup)

    return ADD_MED_WEEKDAYS

async def ask_frequency(query, context):
    """Запрос частоты приёма"""
    keyboard = [
        [InlineKeyboardButton("1 раз в день", callback_data="freq_1")],
        [InlineKeyboardButton("2 раза в день", callback_data="freq_2")],
        [InlineKeyboardButton("3 раза в день", callback_data="freq_3")],
        [InlineKeyboardButton("4 раза в день", callback_data="freq_4")],
    ]
    keyboard = add_navigation_buttons(keyboard, step_number=4, show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)

    schedule_info = ""
    if context.user_data['schedule_type'] == 'daily':
        schedule_info = "Каждый день"
    elif context.user_data['schedule_type'] == 'every_other':
        schedule_info = "Через день"
    elif context.user_data['schedule_type'] == 'weekdays':
        selected = context.user_data['selected_weekdays']
        days_str = ', '.join([WEEKDAYS_SHORT[d] for d in sorted(selected)])
        schedule_info = f"{days_str}"

    await query.message.edit_text(
        f"💊 <b>{context.user_data['med_name']}</b>\n"
        f"📅 Курс: {context.user_data['med_duration']} дней\n"
        f"📋 Приём: {schedule_info}\n\n"
        "🔢 Шаг 4/8: Сколько раз в день?",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_FREQUENCY

async def add_medication_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка частоты"""
    query = update.callback_query
    await query.answer()

    frequency = int(query.data.split('_')[1])
    context.user_data['frequency'] = frequency
    context.user_data['times'] = []
    context.user_data['current_time_index'] = 0
    context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_TIMES_PERIOD]

    return await ask_time_period(query, context)

async def ask_time_period(query, context):
    """Запрос периода дня"""
    current_index = context.user_data['current_time_index']
    total = context.user_data['frequency']

    keyboard = [
        [InlineKeyboardButton("🌅 Утро (6-11)", callback_data="period_morning")],
        [InlineKeyboardButton("☀️ День (11-17)", callback_data="period_day")],
        [InlineKeyboardButton("🌆 Вечер (17-22)", callback_data="period_evening")],
        [InlineKeyboardButton("🌙 Ночь (22-6)", callback_data="period_night")],
    ]
    keyboard = add_navigation_buttons(keyboard, step_number=5, show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"💊 <b>{context.user_data['med_name']}</b>\n"
        f"⏰ Приём {current_index + 1}/{total}\n\n"
        "Шаг 5/8: Выберите период дня:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_TIMES_PERIOD

async def add_medication_time_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка периода"""
    query = update.callback_query
    await query.answer()

    period = query.data.split('_')[1]
    context.user_data['current_period'] = period
    context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_TIME_INPUT]

    time_options = {
        'morning': ['06:00', '07:00', '08:00', '09:00', '10:00'],
        'day': ['12:00', '13:00', '14:00', '15:00', '16:00'],
        'evening': ['18:00', '19:00', '20:00', '21:00'],
        'night': ['22:00', '23:00', '00:00']
    }

    keyboard = []
    for time_opt in time_options[period]:
        keyboard.append([InlineKeyboardButton(time_opt, callback_data=f"time_{time_opt}")])

    keyboard.append([InlineKeyboardButton("✏️ Своё время", callback_data="time_custom")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="nav_back"),
                     InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    period_names = {'morning': '🌅 Утро', 'day': '☀️ День', 'evening': '🌆 Вечер', 'night': '🌙 Ночь'}

    await query.message.edit_text(
        f"💊 <b>{context.user_data['med_name']}</b>\n"
        f"🕐 {period_names[period]}\n\n"
        "Выберите время:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_TIME_INPUT

async def add_medication_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "time_custom":
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="nav_back"),
                         InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(
                "⏰ Введите время (ЧЧ:ММ):\n"
                "Например: 08:30",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return ADD_MED_TIME_INPUT

        time_str = query.data.split('_')[1]
        context.user_data['times'].append({'time': time_str, 'period': context.user_data['current_period']})
        context.user_data['current_time_index'] += 1

        if context.user_data['current_time_index'] < context.user_data['frequency']:
            context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_TIMES_PERIOD]
            return await ask_time_period(query, context)
        else:
            context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_REMINDER]
            return await ask_reminder_interval(query, context)

    else:
        time_str = update.message.text.strip()

        try:
            datetime.strptime(time_str, '%H:%M')
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Используйте ЧЧ:ММ (например: 08:30)")
            return ADD_MED_TIME_INPUT

        context.user_data['times'].append({'time': time_str, 'period': context.user_data['current_period']})
        context.user_data['current_time_index'] += 1

        if context.user_data['current_time_index'] < context.user_data['frequency']:
            context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_TIMES_PERIOD]

            keyboard = [
                [InlineKeyboardButton("🌅 Утро", callback_data="period_morning")],
                [InlineKeyboardButton("☀️ День", callback_data="period_day")],
                [InlineKeyboardButton("🌆 Вечер", callback_data="period_evening")],
                [InlineKeyboardButton("🌙 Ночь", callback_data="period_night")],
            ]
            keyboard = add_navigation_buttons(keyboard, step_number=5, show_back=True)
            reply_markup = InlineKeyboardMarkup(keyboard)

            current_index = context.user_data['current_time_index']
            total = context.user_data['frequency']

            await update.message.reply_text(
                f"💊 <b>{context.user_data['med_name']}</b>\n"
                f"⏰ Приём {current_index + 1}/{total}\n\n"
                "Выберите период дня:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return ADD_MED_TIMES_PERIOD
        else:
            context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_REMINDER]

            keyboard = [
                [InlineKeyboardButton("⏰ 30 минут", callback_data="reminder_30")],
                [InlineKeyboardButton("⏰ 1 час", callback_data="reminder_60")],
                [InlineKeyboardButton("⏰ 1.5 часа", callback_data="reminder_90")],
                [InlineKeyboardButton("⏰ 2 часа", callback_data="reminder_120")],
            ]
            keyboard = add_navigation_buttons(keyboard, step_number=6, show_back=True)
            reply_markup = InlineKeyboardMarkup(keyboard)

            times_list = '\n'.join([f"  • {PERIODS[t['period']]}: {t['time']}" for t in context.user_data['times']])

            await update.message.reply_text(
                f"💊 <b>{context.user_data['med_name']}</b>\n\n"
                f"⏰ Время:\n{times_list}\n\n"
                "🔔 Шаг 6/8: Интервал напоминаний (если отложено)?",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

            return ADD_MED_REMINDER

async def ask_reminder_interval(query, context):
    """Запрос интервала напоминаний"""
    keyboard = [
        [InlineKeyboardButton("⏰ 30 минут", callback_data="reminder_30")],
        [InlineKeyboardButton("⏰ 1 час", callback_data="reminder_60")],
        [InlineKeyboardButton("⏰ 1.5 часа", callback_data="reminder_90")],
        [InlineKeyboardButton("⏰ 2 часа", callback_data="reminder_120")],
    ]
    keyboard = add_navigation_buttons(keyboard, step_number=6, show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)

    times_list = '\n'.join([f"  • {PERIODS[t['period']]}: {t['time']}" for t in context.user_data['times']])

    await query.message.edit_text(
        f"💊 <b>{context.user_data['med_name']}</b>\n\n"
        f"⏰ Время:\n{times_list}\n\n"
        "🔔 Шаг 6/8: Интервал напоминаний?",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_REMINDER

async def add_medication_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка интервала напоминаний"""
    query = update.callback_query
    await query.answer()

    reminder_minutes = int(query.data.split('_')[1])
    context.user_data['reminder_interval'] = reminder_minutes
    context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_DOSAGE_CHOICE]

    # Спрашиваем про схему дозировки
    keyboard = [
        [InlineKeyboardButton("Нет, одинаково", callback_data="dosage_no")],
        [InlineKeyboardButton("Да, настроить схему", callback_data="dosage_yes")],
    ]
    keyboard = add_navigation_buttons(keyboard, step_number=7, show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"💊 <b>{context.user_data['med_name']}</b>\n\n"
        "💊 Шаг 7/8: Дозировка меняется?\n"
        "(Например: первые 3 дня - 2 таблетки, потом 1)",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ADD_MED_DOSAGE_CHOICE

async def add_medication_dosage_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор схемы дозировки"""
    query = update.callback_query
    await query.answer()

    if query.data == "dosage_no":
        context.user_data['has_dosage_scheme'] = False
        return await show_confirmation(query, context)
    else:
        context.user_data['has_dosage_scheme'] = True
        context.user_data['dosage_schemes'] = []
        context.user_data['step_history'] = context.user_data.get('step_history', []) + [ADD_MED_DOSAGE_SCHEME]

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n"
            f"Курс: {context.user_data['med_duration']} дней\n\n"
            "📝 Формат: <code>1-3: 2 таблетки</code>\n\n"
            "Введите схему или <code>готово</code>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        return ADD_MED_DOSAGE_SCHEME

async def add_medication_dosage_scheme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод схемы дозировки"""
    text = update.message.text.strip().lower()

    if text == 'готово':
        if not context.user_data.get('dosage_schemes'):
            await update.message.reply_text("❌ Введите хотя бы одну схему!")
            return ADD_MED_DOSAGE_SCHEME

        keyboard = [
            [InlineKeyboardButton("✅ Сохранить", callback_data="confirm_yes")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        return await show_confirmation_with_keyboard(update.message, context, reply_markup)

    try:
        parts = text.split(':')
        if len(parts) != 2:
            raise ValueError()

        days_range = parts[0].strip()
        dosage = parts[1].strip()

        day_from, day_to = map(int, days_range.split('-'))

        if day_from < 1 or day_to > context.user_data['med_duration'] or day_from > day_to:
            raise ValueError()

        context.user_data['dosage_schemes'].append({
            'day_from': day_from,
            'day_to': day_to,
            'dosage': dosage
        })

        schemes_list = '\n'.join([f"  • Дни {s['day_from']}-{s['day_to']}: {s['dosage']}" 
                                  for s in context.user_data['dosage_schemes']])

        await update.message.reply_text(
            f"✅ Добавлено!\n\n<b>Схемы:</b>\n{schemes_list}\n\n"
            f"Добавьте ещё или <code>готово</code>",
            parse_mode='HTML'
        )

        return ADD_MED_DOSAGE_SCHEME

    except:
        await update.message.reply_text(
            "❌ Неверный формат!\n\nИспользуйте: <code>1-3: 2 таблетки</code>",
            parse_mode='HTML'
        )
        return ADD_MED_DOSAGE_SCHEME

async def show_confirmation(query, context):
    """Финальное подтверждение"""
    keyboard = [
        [InlineKeyboardButton("✅ Сохранить", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    schedule_info = ""
    if context.user_data['schedule_type'] == 'daily':
        schedule_info = "Каждый день"
    elif context.user_data['schedule_type'] == 'every_other':
        schedule_info = "Через день"
    elif context.user_data['schedule_type'] == 'weekdays':
        selected = [int(d) for d in context.user_data['weekdays'].split(',')]
        days_str = ', '.join([WEEKDAYS_SHORT[d] for d in sorted(selected)])
        schedule_info = days_str

    times_list = '\n'.join([f"  • {PERIODS[t['period']]}: {t['time']}" for t in context.user_data['times']])

    reminder_text = {30: "30 мин", 60: "1 час", 90: "1.5 часа", 120: "2 часа"}[context.user_data['reminder_interval']]

    start = context.user_data['med_start_date']
    end = context.user_data['med_end_date']

    text = f"✅ <b>Проверьте данные:</b>\n\n"
    text += f"💊 {context.user_data['med_name']}\n"
    text += f"📅 {context.user_data['med_duration']} дней ({start.strftime('%d.%m')} - {end.strftime('%d.%m')})\n"
    text += f"📋 {schedule_info}\n"
    text += f"🔢 {context.user_data['frequency']} раз в день\n\n"
    text += f"⏰ <b>Время:</b>\n{times_list}\n\n"
    text += f"🔔 Напоминать через: {reminder_text}\n\n"

    if context.user_data.get('has_dosage_scheme'):
        schemes_list = '\n'.join([f"  • Дни {s['day_from']}-{s['day_to']}: {s['dosage']}" 
                                  for s in context.user_data.get('dosage_schemes', [])])
        text += f"💊 <b>Схема:</b>\n{schemes_list}\n\n"

    text += "Всё верно?"

    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

    return ADD_MED_CONFIRM

async def show_confirmation_with_keyboard(message, context, reply_markup):
    """Подтверждение через message"""
    schedule_info = ""
    if context.user_data['schedule_type'] == 'daily':
        schedule_info = "Каждый день"
    elif context.user_data['schedule_type'] == 'every_other':
        schedule_info = "Через день"
    elif context.user_data['schedule_type'] == 'weekdays':
        selected = [int(d) for d in context.user_data['weekdays'].split(',')]
        days_str = ', '.join([WEEKDAYS_SHORT[d] for d in sorted(selected)])
        schedule_info = days_str

    times_list = '\n'.join([f"  • {PERIODS[t['period']]}: {t['time']}" for t in context.user_data['times']])
    reminder_text = {30: "30 мин", 60: "1 час", 90: "1.5 часа", 120: "2 часа"}[context.user_data['reminder_interval']]

    start = context.user_data['med_start_date']
    end = context.user_data['med_end_date']

    text = f"✅ <b>Проверьте данные:</b>\n\n"
    text += f"💊 {context.user_data['med_name']}\n"
    text += f"📅 {context.user_data['med_duration']} дней ({start.strftime('%d.%m')} - {end.strftime('%d.%m')})\n"
    text += f"📋 {schedule_info}\n"
    text += f"🔢 {context.user_data['frequency']} раз в день\n\n"
    text += f"⏰ <b>Время:</b>\n{times_list}\n\n"
    text += f"🔔 Напоминать через: {reminder_text}\n\n"

    if context.user_data.get('has_dosage_scheme'):
        schemes_list = '\n'.join([f"  • Дни {s['day_from']}-{s['day_to']}: {s['dosage']}" 
                                  for s in context.user_data.get('dosage_schemes', [])])
        text += f"💊 <b>Схема:</b>\n{schemes_list}\n\n"

    text += "Всё верно?"

    await message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    return ADD_MED_CONFIRM

async def confirm_medication(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение лекарства"""
    query = update.callback_query
    await query.answer()

    user_id = get_or_create_user(update.effective_user.id)

    try:
        with get_db() as conn:
            c = conn.cursor()

            # Создаём лекарство
            weekdays = context.user_data.get('weekdays')
            end_date = context.user_data['med_start_date'] + timedelta(
                days=context.user_data['med_duration'] - 1
            )

            c.execute('''INSERT INTO medications 
                         (user_id, name, duration_days, start_date, end_date, 
                          schedule_type, weekdays, has_dosage_scheme)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (user_id, context.user_data['med_name'], 
                       context.user_data['med_duration'],
                       context.user_data['med_start_date'].isoformat(),
                       end_date.isoformat(),
                       context.user_data['schedule_type'], weekdays,
                       context.user_data.get('has_dosage_scheme', False)))

            medication_id = c.lastrowid

            # Создаём расписания
            for time_data in context.user_data['times']:
                c.execute('''INSERT INTO schedules 
                             (medication_id, time, period, reminder_interval)
                             VALUES (?, ?, ?, ?)''',
                          (medication_id, time_data['time'], time_data['period'],
                           context.user_data['reminder_interval']))

            # Создаём схемы дозировки
            if context.user_data.get('has_dosage_scheme'):
                for scheme in context.user_data.get('dosage_schemes', []):
                    times_str = ','.join([t['time'] for t in context.user_data['times']])
                    c.execute('''INSERT INTO dosage_schemes 
                                 (medication_id, day_from, day_to, dosage, times)
                                 VALUES (?, ?, ?, ?, ?)''',
                              (medication_id, scheme['day_from'], scheme['day_to'],
                               scheme['dosage'], times_str))

            logger.info(f"✅ Лекарство {medication_id} создано с транзакцией")

    except Exception as e:
        logger.error(f"❌ Ошибка создания лекарства: {e}")
        # НЕ очищаем context.user_data, чтобы пользователь мог повторить попытку
        await query.message.edit_text(
            "❌ Произошла ошибка при сохранении. Попробуйте снова.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Попробовать снова", callback_data="confirm_yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")
            ]])
        )
        return ADD_MED_CONFIRM

    # Успешно создано
    keyboard = [
        [InlineKeyboardButton("💊 Посмотреть", callback_data="med_current")],
        [InlineKeyboardButton("➕ Добавить ещё", callback_data="add_medication")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"✅ <b>Лекарство добавлено!</b>\n\n"
        f"💊 {context.user_data['med_name']}\n"
        f"Я буду напоминать тебе о приёме! 💝",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_add_medication(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления лекарства"""
    query = update.callback_query
    if query:
        await query.answer()

    context.user_data.clear()

    text = "❌ Добавление лекарства отменено"
    keyboard = [[InlineKeyboardButton("🔙 В настройки", callback_data="settings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.message.edit_text(text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return ConversationHandler.END

# ============= ФУНКЦИИ НАВИГАЦИИ ДЛЯ РЕДАКТИРОВАНИЯ ЛЕКАРСТВ =============

async def cancel_edit_medication(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена редактирования лекарства"""
    query = update.callback_query
    if query:
        await query.answer()

    medication_id = context.user_data.get('editing_med_id')
    context.user_data.clear()

    if medication_id:
        keyboard = [[InlineKeyboardButton("🔙 К лекарству", callback_data=f"edit_med_{medication_id}")]]
    else:
        keyboard = [[InlineKeyboardButton("🔙 К редактированию", callback_data="edit_medications")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "❌ Редактирование отменено"

    if query:
        await query.message.edit_text(text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return ConversationHandler.END

async def go_back_edit_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат на предыдущий шаг при редактировании"""
    query = update.callback_query
    await query.answer()

    step_history = context.user_data.get('edit_step_history', [])
    medication_id = context.user_data.get('editing_med_id')

    if not step_history or len(step_history) < 2:
        return await cancel_edit_medication(update, context)

    step_history.pop()
    previous_step = step_history[-1]
    context.user_data['edit_step_history'] = step_history

    med = get_medication_by_id(medication_id)
    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return ConversationHandler.END

    # Возврат к соответствующему шагу
    if previous_step == EDIT_MED_NAME:
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="nav_back_edit"),
             InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            f"✏️ Текущее название: {med['name']}\n\nВведите новое название:",
            reply_markup=reply_markup
        )
        return EDIT_MED_NAME_INPUT

    elif previous_step == EDIT_MED_DURATION:
        keyboard = [
            [InlineKeyboardButton("3 дня", callback_data="edit_duration_3"),
             InlineKeyboardButton("5 дней", callback_data="edit_duration_5")],
            [InlineKeyboardButton("7 дней", callback_data="edit_duration_7"),
             InlineKeyboardButton("10 дней", callback_data="edit_duration_10")],
            [InlineKeyboardButton("14 дней", callback_data="edit_duration_14"),
             InlineKeyboardButton("21 день", callback_data="edit_duration_21")],
            [InlineKeyboardButton("30 дней", callback_data="edit_duration_30")],
            [InlineKeyboardButton("✏️ Своя длительность", callback_data="edit_duration_custom")],
            [InlineKeyboardButton("📅 Дата окончания", callback_data="edit_duration_date")],
            [InlineKeyboardButton("◀️ Назад", callback_data="nav_back_edit"),
             InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            f"📅 Текущая длительность: {med['duration_days']} дней\n\nВыберите новую длительность:",
            reply_markup=reply_markup
        )
        return EDIT_MED_DURATION

    elif previous_step == EDIT_MED_SCHEDULE_TYPE:
        schedule_info = ""
        if med['schedule_type'] == 'daily':
            schedule_info = "Каждый день"
        elif med['schedule_type'] == 'every_other':
            schedule_info = "Через день"
        elif med['schedule_type'] == 'weekdays' and med['weekdays']:
            weekdays_list = [int(d) for d in med['weekdays'].split(',')]
            days_str = ', '.join([WEEKDAYS_SHORT[d] for d in sorted(weekdays_list)])
            schedule_info = f"{days_str}"

        keyboard = [
            [InlineKeyboardButton("Каждый день", callback_data="edit_sched_daily")],
            [InlineKeyboardButton("Через день", callback_data="edit_sched_every_other")],
            [InlineKeyboardButton("По дням недели", callback_data="edit_sched_weekdays")],
            [InlineKeyboardButton("◀️ Назад", callback_data="nav_back_edit"),
             InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            f"📋 Текущее расписание: {schedule_info}\n\nВыберите новый тип расписания:",
            reply_markup=reply_markup
        )
        return EDIT_MED_SCHEDULE_TYPE

    return ConversationHandler.END

# ============= РЕДАКТИРОВАНИЕ ЛЕКАРСТВ =============

async def edit_medications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню редактирования"""
    query = update.callback_query
    await query.answer()

    user_id = get_or_create_user(update.effective_user.id)
    medications = get_active_medications(user_id)

    if not medications:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="settings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "У вас нет активных лекарств для редактирования.",
            reply_markup=reply_markup
        )
        return

    keyboard = []
    for med in medications:
        keyboard.append([InlineKeyboardButton(f"✏️ {med['name']}", callback_data=f"edit_med_{med['id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        "✏️ <b>Редактирование лекарств</b>\n\nВыберите лекарство:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def edit_medication_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Действия с лекарством"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return

    keyboard = [
        [InlineKeyboardButton("✏️ Изменить название", callback_data=f"edit_name_{medication_id}")],
        [InlineKeyboardButton("📅 Изменить длительность", callback_data=f"edit_duration_{medication_id}")],
        [InlineKeyboardButton("📋 Изменить тип расписания", callback_data=f"edit_schedule_type_{medication_id}")],
        [InlineKeyboardButton("🔢 Изменить частоту приёма", callback_data=f"edit_frequency_{medication_id}")],
        [InlineKeyboardButton("⏰ Изменить время приёмов", callback_data=f"edit_time_{medication_id}")],
        [InlineKeyboardButton("🔔 Изменить интервал напоминаний", callback_data=f"edit_reminder_{medication_id}")],
        [InlineKeyboardButton("➕ Продлить курс", callback_data=f"extend_{medication_id}")],
        [InlineKeyboardButton("✅ Завершить курс", callback_data=f"complete_{medication_id}")],
        [InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{medication_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="edit_medications")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"✏️ <b>{med['name']}</b>\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def edit_med_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования названия"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return ConversationHandler.END

    context.user_data['editing_med_id'] = medication_id
    context.user_data['edit_step_history'] = [EDIT_MED_NAME, EDIT_MED_NAME_INPUT]

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"✏️ Текущее название: {med['name']}\n\nВведите новое название:",
        reply_markup=reply_markup
    )

    return EDIT_MED_NAME_INPUT

async def edit_med_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод нового названия"""
    new_name = update.message.text.strip()
    med_id = context.user_data['editing_med_id']

    update_medication(med_id, name=new_name)

    await update.message.reply_text(
        f"✅ Название изменено на {new_name}!"
    )

    context.user_data.clear()
    return ConversationHandler.END

async def edit_med_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования длительности"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return ConversationHandler.END

    context.user_data['editing_med_id'] = medication_id
    context.user_data['editing_start_date'] = datetime.strptime(med['start_date'], '%Y-%m-%d').date()
    context.user_data['edit_step_history'] = [EDIT_MED_DURATION]

    keyboard = [
        [InlineKeyboardButton("3 дня", callback_data="edit_duration_3"),
         InlineKeyboardButton("5 дней", callback_data="edit_duration_5")],
        [InlineKeyboardButton("7 дней", callback_data="edit_duration_7"),
         InlineKeyboardButton("10 дней", callback_data="edit_duration_10")],
        [InlineKeyboardButton("14 дней", callback_data="edit_duration_14"),
         InlineKeyboardButton("21 день", callback_data="edit_duration_21")],
        [InlineKeyboardButton("30 дней", callback_data="edit_duration_30")],
        [InlineKeyboardButton("✏️ Своя длительность", callback_data="edit_duration_custom")],
        [InlineKeyboardButton("📅 Дата окончания", callback_data="edit_duration_date")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"📅 Текущая длительность: {med['duration_days']} дней\n\nВыберите новую длительность:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return EDIT_MED_DURATION

async def edit_med_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка новой длительности"""
    query = update.callback_query
    await query.answer()

    if query.data == "edit_duration_custom":
        context.user_data['edit_step_history'] = context.user_data.get('edit_step_history', []) + [EDIT_MED_DURATION_INPUT]

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="nav_back_edit"),
                     InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "📝 Введите новую длительность в днях (1-365):",
            reply_markup=reply_markup
        )
        return EDIT_MED_DURATION_INPUT

    elif query.data == "edit_duration_date":
        context.user_data['edit_step_history'] = context.user_data.get('edit_step_history', []) + [EDIT_MED_DURATION_INPUT]

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="nav_back_edit"),
                     InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "📅 Введите новую дату окончания (ДД.ММ.ГГГГ):\n"
            "Например: 25.12.2025",
            reply_markup=reply_markup
        )
        return EDIT_MED_DURATION_INPUT

    else:
        duration = int(query.data.split('_')[2])
        med_id = context.user_data['editing_med_id']
        start_date = context.user_data['editing_start_date']
        new_end_date = start_date + timedelta(days=duration - 1)

        update_medication(med_id, duration_days=duration, end_date=new_end_date.isoformat())

        await query.message.edit_text(
            f"✅ Длительность изменена на {duration} дней!"
        )

        return ConversationHandler.END

async def edit_med_duration_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод пользовательской длительности для редактирования"""
    text = update.message.text.strip()

    med_id = context.user_data['editing_med_id']
    start_date = context.user_data['editing_start_date']

    if '.' in text:
        try:
            new_end_date = datetime.strptime(text, '%d.%m.%Y').date()

            if new_end_date <= start_date:
                await update.message.reply_text("❌ Дата должна быть в будущем!")
                return EDIT_MED_DURATION_INPUT

            new_duration = (new_end_date - start_date).days + 1

            update_medication(med_id, duration_days=new_duration, end_date=new_end_date.isoformat())

            await update.message.reply_text(
                f"✅ Длительность изменена на {new_duration} дней!"
            )

            context.user_data.clear()
            return ConversationHandler.END

        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Используйте ДД.ММ.ГГГГ")
            return EDIT_MED_DURATION_INPUT

    try:
        new_duration = int(text)
        if new_duration < 1 or new_duration > 365:
            await update.message.reply_text("❌ Введите число от 1 до 365:")
            return EDIT_MED_DURATION_INPUT

        new_end_date = start_date + timedelta(days=new_duration - 1)

        update_medication(med_id, duration_days=new_duration, end_date=new_end_date.isoformat())

        await update.message.reply_text(
            f"✅ Длительность изменена на {new_duration} дней!"
        )

        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return EDIT_MED_DURATION_INPUT

"""
Недостающие функции редактирования для medication_bot.py
Эти функции нужно добавить в основной файл бота
"""

# ============= ДОПОЛНЕННЫЕ ФУНКЦИИ РЕДАКТИРОВАНИЯ =============

async def edit_schedule_type_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования типа расписания"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[3])  # edit_schedule_type_{id}
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return ConversationHandler.END

    context.user_data['editing_med_id'] = medication_id
    context.user_data['edit_step_history'] = [EDIT_MED_SCHEDULE_TYPE]

    # Показываем текущее расписание
    schedule_info = ""
    if med['schedule_type'] == 'daily':
        schedule_info = "Каждый день"
    elif med['schedule_type'] == 'every_other':
        schedule_info = "Через день"
    elif med['schedule_type'] == 'weekdays':
        if med['weekdays']:
            weekdays_list = [int(d) for d in med['weekdays'].split(',')]
            days_str = ', '.join([WEEKDAYS_SHORT[d] for d in sorted(weekdays_list)])
            schedule_info = f"{days_str}"

    keyboard = [
        [InlineKeyboardButton("Каждый день", callback_data="edit_sched_daily")],
        [InlineKeyboardButton("Через день", callback_data="edit_sched_every_other")],
        [InlineKeyboardButton("По дням недели", callback_data="edit_sched_weekdays")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"📋 Текущее расписание: {schedule_info}\n\nВыберите новый тип расписания:",
        reply_markup=reply_markup
    )

    return EDIT_MED_SCHEDULE_TYPE

async def edit_schedule_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нового типа расписания"""
    query = update.callback_query
    await query.answer()

    schedule_type = query.data.split('_')[2]  # edit_sched_{type}
    med_id = context.user_data['editing_med_id']

    if schedule_type == 'weekdays':
        context.user_data['edit_step_history'] = context.user_data.get('edit_step_history', []) + [EDIT_MED_WEEKDAYS]

        keyboard = []
        for day_num, day_name in WEEKDAYS_FULL.items():
            keyboard.append([InlineKeyboardButton(f"☐ {day_name}", callback_data=f"edit_weekday_{day_num}")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="edit_weekdays_done")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="nav_back_edit"),
                         InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['selected_weekdays'] = []

        await query.message.edit_text(
            "📆 Выберите дни недели (можно несколько):",
            reply_markup=reply_markup
        )

        return EDIT_MED_WEEKDAYS
    else:
        # Сохраняем новый тип расписания
        weekdays = None if schedule_type != 'weekdays' else ""
        update_medication(med_id, schedule_type=schedule_type, weekdays=weekdays)

        await query.message.edit_text(
            "✅ Тип расписания изменён!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К лекарству", callback_data=f"edit_med_{med_id}")
            ]])
        )

        context.user_data.clear()
        return ConversationHandler.END

async def edit_weekdays_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор дней недели для редактирования"""
    query = update.callback_query

    if query.data == "edit_weekdays_done":
        if not context.user_data.get('selected_weekdays'):
            await query.answer("❌ Выберите хотя бы один день!", show_alert=True)
            return EDIT_MED_WEEKDAYS

        await query.answer()
        med_id = context.user_data['editing_med_id']
        weekdays = ','.join(map(str, sorted(context.user_data['selected_weekdays'])))
        update_medication(med_id, schedule_type='weekdays', weekdays=weekdays)

        await query.message.edit_text(
            "✅ Дни недели изменены!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К лекарству", callback_data=f"edit_med_{med_id}")
            ]])
        )

        context.user_data.clear()
        return ConversationHandler.END

    day_num = int(query.data.split('_')[2])  # edit_weekday_{num}
    selected = context.user_data.get('selected_weekdays', [])

    if day_num in selected:
        selected.remove(day_num)
    else:
        selected.append(day_num)

    context.user_data['selected_weekdays'] = selected

    keyboard = []
    for d_num, d_name in WEEKDAYS_FULL.items():
        icon = "☑️" if d_num in selected else "☐"
        keyboard.append([InlineKeyboardButton(f"{icon} {d_name}", callback_data=f"edit_weekday_{d_num}")])
    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="edit_weekdays_done")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data=f"edit_med_{context.user_data['editing_med_id']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer()
    await query.message.edit_reply_markup(reply_markup=reply_markup)

    return EDIT_MED_WEEKDAYS

async def edit_frequency_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования частоты приёма"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])  # edit_frequency_{id}
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return ConversationHandler.END

    context.user_data['editing_med_id'] = medication_id
    context.user_data['edit_step_history'] = [EDIT_MED_FREQUENCY]

    # Получаем текущее количество приёмов
    schedules = get_medication_schedules(medication_id)
    current_freq = len(schedules)

    keyboard = [
        [InlineKeyboardButton("1 раз в день", callback_data="edit_freq_1")],
        [InlineKeyboardButton("2 раза в день", callback_data="edit_freq_2")],
        [InlineKeyboardButton("3 раза в день", callback_data="edit_freq_3")],
        [InlineKeyboardButton("4 раза в день", callback_data="edit_freq_4")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"🔢 Текущая частота: {current_freq} раз в день\n\nВыберите новую частоту:",
        reply_markup=reply_markup
    )

    return EDIT_MED_FREQUENCY

async def edit_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка новой частоты"""
    query = update.callback_query
    await query.answer()

    frequency = int(query.data.split('_')[2])  # edit_freq_{num}
    med_id = context.user_data['editing_med_id']

    # Удаляем старые расписания
    delete_medication_schedules(med_id)

    # Подготовка к созданию новых расписаний
    context.user_data['frequency'] = frequency
    context.user_data['times'] = []
    context.user_data['current_time_index'] = 0

    # Переходим к выбору времени для нового расписания
    return await edit_time_start(query, context)

async def edit_time_start(query, context):
    """Начало выбора времени для редактирования расписания"""
    current_index = context.user_data['current_time_index']
    total = context.user_data['frequency']

    keyboard = [
        [InlineKeyboardButton("🌅 Утро (6-11)", callback_data="edit_period_morning")],
        [InlineKeyboardButton("☀️ День (11-17)", callback_data="edit_period_day")],
        [InlineKeyboardButton("🌆 Вечер (17-22)", callback_data="edit_period_evening")],
        [InlineKeyboardButton("🌙 Ночь (22-6)", callback_data="edit_period_night")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"edit_med_{context.user_data['editing_med_id']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"⏰ Приём {current_index + 1}/{total}\n\nВыберите период дня:",
        reply_markup=reply_markup
    )

    return EDIT_MED_TIMES_PERIOD

async def ask_edit_time_period(query, context):
    """Запрос периода дня для редактирования"""
    current_index = context.user_data['current_time_index']
    total = context.user_data['frequency']

    keyboard = [
        [InlineKeyboardButton("🌅 Утро (6-11)", callback_data="edit_period_morning")],
        [InlineKeyboardButton("☀️ День (11-17)", callback_data="edit_period_day")],
        [InlineKeyboardButton("🌆 Вечер (17-22)", callback_data="edit_period_evening")],
        [InlineKeyboardButton("🌙 Ночь (22-6)", callback_data="edit_period_night")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"edit_med_{context.user_data['editing_med_id']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"⏰ Приём {current_index + 1}/{total}\n\nВыберите период дня:",
        reply_markup=reply_markup
    )

    return EDIT_MED_TIMES_PERIOD

async def edit_time_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка периода для редактирования"""
    query = update.callback_query
    await query.answer()

    period = query.data.split('_')[2]  # edit_period_{period}
    context.user_data['current_period'] = period

    time_options = {
        'morning': ['06:00', '07:00', '08:00', '09:00', '10:00'],
        'day': ['12:00', '13:00', '14:00', '15:00', '16:00'],
        'evening': ['18:00', '19:00', '20:00', '21:00'],
        'night': ['22:00', '23:00', '00:00']
    }

    keyboard = []
    for time_opt in time_options[period]:
        keyboard.append([InlineKeyboardButton(time_opt, callback_data=f"edit_time_{time_opt}")])

    keyboard.append([InlineKeyboardButton("✏️ Своё время", callback_data="edit_time_custom")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data=f"edit_med_{context.user_data['editing_med_id']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    period_names = {'morning': '🌅 Утро', 'day': '☀️ День', 'evening': '🌆 Вечер', 'night': '🌙 Ночь'}

    await query.message.edit_text(
        f"🕐 {period_names[period]}\n\nВыберите время:",
        reply_markup=reply_markup
    )

    return EDIT_MED_TIME_INPUT

async def edit_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени для редактирования"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "edit_time_custom":
            await query.message.edit_text(
                "⏰ Введите время (ЧЧ:ММ):\nНапример: 08:30"
            )
            return EDIT_MED_TIME_INPUT

        time_str = query.data.split('_')[2]  # edit_time_{time}
        context.user_data['times'].append({'time': time_str, 'period': context.user_data['current_period']})
        context.user_data['current_time_index'] += 1

        if context.user_data['current_time_index'] < context.user_data['frequency']:
            return await edit_time_start(query, context)
        else:
            return await ask_edit_reminder_interval(query, context)

    else:
        # Ввод пользовательского времени
        time_str = update.message.text.strip()

        try:
            datetime.strptime(time_str, '%H:%M')
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Используйте ЧЧ:ММ (например: 08:30)")
            return EDIT_MED_TIME_INPUT

        context.user_data['times'].append({'time': time_str, 'period': context.user_data['current_period']})
        context.user_data['current_time_index'] += 1

        if context.user_data['current_time_index'] < context.user_data['frequency']:
            keyboard = [
                [InlineKeyboardButton("🌅 Утро", callback_data="edit_period_morning")],
                [InlineKeyboardButton("☀️ День", callback_data="edit_period_day")],
                [InlineKeyboardButton("🌆 Вечер", callback_data="edit_period_evening")],
                [InlineKeyboardButton("🌙 Ночь", callback_data="edit_period_night")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            current_index = context.user_data['current_time_index']
            total = context.user_data['frequency']

            await update.message.reply_text(
                f"⏰ Приём {current_index + 1}/{total}\n\nВыберите период дня:",
                reply_markup=reply_markup
            )
            return EDIT_MED_TIMES_PERIOD
        else:
            keyboard = [
                [InlineKeyboardButton("⏰ 30 минут", callback_data="edit_reminder_int_30")],
                [InlineKeyboardButton("⏰ 1 час", callback_data="edit_reminder_int_60")],
                [InlineKeyboardButton("⏰ 1.5 часа", callback_data="edit_reminder_int_90")],
                [InlineKeyboardButton("⏰ 2 часа", callback_data="edit_reminder_int_120")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            times_list = '\n'.join([f"  • {PERIODS[t['period']]}: {t['time']}" for t in context.user_data['times']])

            await update.message.reply_text(
                f"⏰ Время:\n{times_list}\n\n🔔 Интервал напоминаний (если отложено)?",
                reply_markup=reply_markup
            )

            return EDIT_MED_REMINDER

async def ask_edit_reminder_interval(query, context):
    """Запрос интервала напоминаний для редактирования"""
    keyboard = [
        [InlineKeyboardButton("⏰ 30 минут", callback_data="edit_reminder_int_30")],
        [InlineKeyboardButton("⏰ 1 час", callback_data="edit_reminder_int_60")],
        [InlineKeyboardButton("⏰ 1.5 часа", callback_data="edit_reminder_int_90")],
        [InlineKeyboardButton("⏰ 2 часа", callback_data="edit_reminder_int_120")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    times_list = '\n'.join([f"  • {PERIODS[t['period']]}: {t['time']}" for t in context.user_data['times']])

    await query.message.edit_text(
        f"⏰ Время:\n{times_list}\n\n🔔 Интервал напоминаний?",
        reply_markup=reply_markup
    )

    return EDIT_MED_REMINDER

async def edit_reminder_interval_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение редактирования с сохранением новых расписаний"""
    query = update.callback_query
    await query.answer()

    reminder_minutes = int(query.data.split('_')[3])  # edit_reminder_int_{minutes}
    med_id = context.user_data['editing_med_id']

    # Создаём новые расписания
    for time_data in context.user_data['times']:
        create_schedule(
            medication_id=med_id,
            time_str=time_data['time'],
            period=time_data['period'],
            reminder_interval=reminder_minutes
        )

    await query.message.edit_text(
        "✅ Расписание приёмов обновлено!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 К лекарству", callback_data=f"edit_med_{med_id}")
        ]])
    )

    context.user_data.clear()
    return ConversationHandler.END

async def edit_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования интервала напоминаний"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])  # edit_reminder_{id}
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text("❌ Лекарство не найдено")
        return ConversationHandler.END

    context.user_data['editing_med_id'] = medication_id
    context.user_data['edit_step_history'] = [EDIT_MED_REMINDER]

    # Получаем текущий интервал
    schedules = get_medication_schedules(medication_id)
    current_interval = schedules[0]['reminder_interval'] if schedules else 60

    reminder_text = {30: "30 мин", 60: "1 час", 90: "1.5 часа", 120: "2 часа"}.get(current_interval, f"{current_interval} мин")

    keyboard = [
        [InlineKeyboardButton("⏰ 30 минут", callback_data="final_reminder_30")],
        [InlineKeyboardButton("⏰ 1 час", callback_data="final_reminder_60")],
        [InlineKeyboardButton("⏰ 1.5 часа", callback_data="final_reminder_90")],
        [InlineKeyboardButton("⏰ 2 часа", callback_data="final_reminder_120")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit_med")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"🔔 Текущий интервал: {reminder_text}\n\nВыберите новый интервал напоминаний:",
        reply_markup=reply_markup
    )

    return EDIT_MED_REMINDER

async def edit_reminder_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового интервала напоминаний"""
    query = update.callback_query
    await query.answer()

    reminder_minutes = int(query.data.split('_')[2])  # final_reminder_{minutes}
    med_id = context.user_data['editing_med_id']

    # Обновляем интервал для всех расписаний этого лекарства
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE schedules SET reminder_interval = ? WHERE medication_id = ?', 
              (reminder_minutes, med_id))
    conn.commit()
    conn.close()

    reminder_text = {30: "30 мин", 60: "1 час", 90: "1.5 часа", 120: "2 часа"}[reminder_minutes]

    await query.message.edit_text(
        f"✅ Интервал напоминаний изменён на {reminder_text}!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 К лекарству", callback_data=f"edit_med_{med_id}")
        ]])
    )

    context.user_data.clear()
    return ConversationHandler.END



# Аналогично реализуйте для других редактирований: edit_schedule_type_start, edit_frequency_start, edit_times_start, edit_reminder_start
# Они будут похожи на соответствующие add_ функции, но вместо create - update/delete old and create new (для schedules, например, delete_medication_schedules и create new)

async def extend_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продление курса"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[1])

    keyboard = [
        [InlineKeyboardButton("➕ 3 дня", callback_data=f"extend_days_{medication_id}_3")],
        [InlineKeyboardButton("➕ 7 дней", callback_data=f"extend_days_{medication_id}_7")],
        [InlineKeyboardButton("➕ 14 дней", callback_data=f"extend_days_{medication_id}_14")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"edit_med_{medication_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        "➕ На сколько продлить курс?",
        reply_markup=reply_markup
    )

async def extend_course_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Применение продления"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    medication_id = int(parts[2])
    days = int(parts[3])

    extend_medication_course(medication_id, days)

    await query.message.edit_text(
        f"✅ Курс продлён на {days} дней!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 К лекарствам", callback_data="med_current")
        ]])
    )

async def complete_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение курса"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[1])
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text(
            "❌ Лекарство не найдено.",
            parse_mode='HTML'
        )
        return

    keyboard = [
        [InlineKeyboardButton("✅ Да, завершить", callback_data=f"complete_confirm_{medication_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"edit_med_{medication_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"Завершить курс <b>{med['name']}</b>?",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def complete_course_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение завершения"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])
    deactivate_medication(medication_id)

    user_id = get_or_create_user(update.effective_user.id)
    unlocked = check_and_unlock_achievements(user_id, context)

    text = "✅ Курс завершён и перенесён в выпитые!"

    if unlocked:
        text += "\n\n🎉 <b>Новые достижения:</b>\n"
        for ach_type in unlocked:
            ach = ACHIEVEMENTS[ach_type]
            text += f"{ach['name']}\n"

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 К лекарствам", callback_data="med_current")
        ]]),
        parse_mode='HTML'
    )

async def delete_medication(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление лекарства"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[1])
    med = get_medication_by_id(medication_id)

    if not med:
        await query.message.edit_text(
            "❌ Лекарство не найдено.",
            parse_mode='HTML'
        )
        return

    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_confirm_{medication_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"edit_med_{medication_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(
        f"Удалить курс <b>{med['name']}</b>? Это действие нельзя отменить.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def delete_medication_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления"""
    query = update.callback_query
    await query.answer()

    medication_id = int(query.data.split('_')[2])
    delete_medication_by_id(medication_id)

    await query.message.edit_text(
        "✅ Курс удалён!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 К лекарствам", callback_data="med_current")
        ]])
    )

# ============= СТАТИСТИКА =============

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователя"""
    user_id = get_or_create_user(update.effective_user.id)
    stats = get_user_statistics(user_id)
    achievements = get_user_achievements(user_id)

    text = "📊 <b>Твоя статистика:</b>\n\n"
    text += f"✅ Курсов завершено: {stats['completed_courses']}\n"
    text += f"💊 Таблеток принято: {stats['total_taken']}\n"
    text += f"❌ Пропущено: {stats['total_missed']}\n"
    text += f"📈 Успешность: {stats['success_rate']}%\n"
    text += f"🔥 Серия без пропусков: {stats['current_streak']} дней\n\n"

    if achievements:
        text += "🏆 <b>Достижения:</b>\n"
        for ach in achievements[:8]:
            ach_info = ACHIEVEMENTS.get(ach['achievement_type'])
            if ach_info:
                text += f"{ach_info['name']}\n"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

# ============= КАЛЕНДАРЬ =============

async def show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Календарь приёмов"""
    user_id = get_or_create_user(update.effective_user.id)

    today = datetime.now(TIMEZONE).date()

    # Получаем данные за последние 14 дней
    calendar_text = "📅 <b>Календарь приёмов</b>\n\n"
    calendar_text += "За последние 14 дней:\n\n"

    for i in range(13, -1, -1):
        check_date = today - timedelta(days=i)
        logs = get_logs_for_date(user_id, check_date)

        if not logs:
            icon = "⭕️"
        else:
            taken = sum(1 for log in logs if log['status'] == 'taken')
            missed = sum(1 for log in logs if log['status'] == 'missed')

            if missed == 0:
                icon = "✅"
            elif missed == 1:
                icon = "⚠️"
            else:
                icon = "❌"

        date_str = check_date.strftime('%d.%m')
        weekday = WEEKDAYS_SHORT[check_date.weekday()]

        calendar_text += f"{icon} {weekday} {date_str}\n"

    calendar_text += "\n✅ - Все приёмы\n⚠️ - Пропущен 1\n❌ - Пропущено 2+\n⭕️ - Нет приёмов"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(calendar_text, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(calendar_text, reply_markup=reply_markup, parse_mode='HTML')

# ============= СИСТЕМА НАПОМИНАНИЙ =============

async def send_medication_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминаний о приёме"""
    # Получаем все активные лекарства
    conn = get_connection()
    c = conn.cursor()

    now = datetime.now(TIMEZONE)
    current_time = now.strftime('%H:%M')
    current_date = now.date()
    current_weekday = current_date.weekday()

    # Находим все расписания, которые должны сработать сейчас
    c.execute('''SELECT m.id as med_id, m.user_id, m.name, m.schedule_type, m.weekdays,
                        s.id as sched_id, s.time, s.period, s.reminder_interval,
                        u.telegram_id
                 FROM medications m
                 JOIN schedules s ON m.id = s.medication_id
                 JOIN users u ON m.user_id = u.id
                 WHERE m.is_active = 1 AND s.time = ?''', (current_time,))

    reminders = c.fetchall()
    conn.close()

    for reminder in reminders:
        med_id = reminder['med_id']
        user_telegram_id = reminder['telegram_id']
        med_name = reminder['name']
        schedule_type = reminder['schedule_type']
        weekdays = reminder['weekdays']
        sched_id = reminder['sched_id']
        reminder_interval = reminder['reminder_interval']

        # Проверяем, нужно ли отправлять сегодня
        should_send = False

        if schedule_type == 'daily':
            should_send = True
        elif schedule_type == 'every_other':
            med = get_medication_by_id(med_id)
            if not med:
                continue  # Лекарство было удалено, пропускаем

            start_date = datetime.strptime(med['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(med['end_date'], '%Y-%m-%d').date()

            # Проверяем, что сегодня в пределах курса
            if start_date <= current_date <= end_date:
                days_since_start = (current_date - start_date).days
                should_send = (days_since_start % 2 == 0)
            else:
                should_send = False
        elif schedule_type == 'weekdays':
            if weekdays:
                weekdays_list = [int(d) for d in weekdays.split(',')]
                should_send = current_weekday in weekdays_list

        if should_send:
            # Проверяем, не было ли уже напоминания в последние 5 минут
            with get_db() as check_conn:
                check_c = check_conn.cursor()
                five_min_ago = (now - timedelta(minutes=5)).isoformat()
                check_c.execute('''SELECT COUNT(*) as count FROM medication_logs 
                                  WHERE medication_id = ? AND schedule_id = ? 
                                  AND scheduled_date = ? AND created_at > ?''',
                              (med_id, sched_id, current_date.isoformat(), five_min_ago))

                if check_c.fetchone()['count'] > 0:
                    continue  # Пропускаем, уже было напоминание

            # Отправляем напоминание
            greeting = get_greeting_by_time()
            nickname = get_random_nickname()

            keyboard = [
                [InlineKeyboardButton("✅ Выпила", callback_data=f"taken_{med_id}_{sched_id}_{current_date.isoformat()}")],
                [InlineKeyboardButton("⏰ Отложить", callback_data=f"postpone_{med_id}_{sched_id}_{current_date.isoformat()}_{reminder_interval}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await context.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"{greeting}, {nickname}!\n\n💊 Пора принять <b>{med_name}</b>",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                
                # Создаём активное напоминание для автоповтора
                create_active_reminder(med_id, sched_id, user_telegram_id, current_date)
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания: {e}")

async def handle_taken(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия 'Выпила'"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    med_id = int(parts[1])
    sched_id = int(parts[2])
    scheduled_date = datetime.strptime(parts[3], '%Y-%m-%d').date()

    med = get_medication_by_id(med_id)

    # Проверяем, что лекарство активно
    if not med or not med['is_active']:
        await query.message.edit_text(
            "❌ Это лекарство больше не активно.",
            parse_mode='HTML'
        )
        return

    schedules = get_medication_schedules(med_id)
    sched = next((s for s in schedules if s['id'] == sched_id), None)

    if med and sched:
        log_medication_taken(med_id, sched_id, scheduled_date, sched['time'])
        
        # Удаляем активное напоминание (отменяем автоповтор)
        delete_active_reminder(med_id, sched_id, scheduled_date)

        user_id = get_or_create_user(update.effective_user.id)
        unlocked = check_and_unlock_achievements(user_id, context)

        praise = random.choice(PRAISE_MESSAGES)
        text = f"{praise}\n\n💊 {med['name']} - принято ✅"

        if unlocked:
            text += "\n\n🎉 <b>Новое достижение:</b>\n"
            for ach_type in unlocked:
                ach = ACHIEVEMENTS[ach_type]
                text += f"{ach['name']}\n"

        await query.message.edit_text(text, parse_mode='HTML')

async def handle_postpone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия 'Отложить'"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    med_id = int(parts[1])
    sched_id = int(parts[2])
    scheduled_date_str = parts[3]
    scheduled_date = datetime.strptime(scheduled_date_str, '%Y-%m-%d').date()
    reminder_interval = int(parts[4])

    med = get_medication_by_id(med_id)

    # Проверяем, что лекарство активно
    if not med or not med['is_active']:
        await query.message.edit_text(
            "❌ Это лекарство больше не активно.",
            parse_mode='HTML'
        )
        return

    if med:
        now = datetime.now(TIMEZONE)
        next_time = now + timedelta(minutes=reminder_interval)
        
        # Удаляем активное напоминание (отменяем автоповтор)
        delete_active_reminder(med_id, sched_id, scheduled_date)

        create_or_update_postponed_reminder(
            medication_id=med_id,
            schedule_id=sched_id,
            user_telegram_id=update.effective_user.id,
            scheduled_date=scheduled_date,
            original_time=now,
            next_time=next_time,
            reminder_interval=reminder_interval
        )

        postpone_msg = random.choice(POSTPONE_MESSAGES)
        interval_text = {30: "30 минут", 60: "час", 90: "1.5 часа", 120: "2 часа"}.get(reminder_interval, f"{reminder_interval} минут")

        await query.message.edit_text(
            f"{postpone_msg}\n\n💊 {med['name']}\n⏰ Напомню через {interval_text}",
            parse_mode='HTML'
        )

async def check_postponed_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверка отложенных напоминаний"""
    reminders = get_due_postponed_reminders()

    for reminder in reminders:
        med = get_medication_by_id(reminder['medication_id'])

        if not med or not med['is_active']:
            delete_postponed_reminder(reminder['id'])
            continue

        nickname = get_random_nickname()
        greeting = get_greeting_by_time()

        keyboard = [
            [InlineKeyboardButton("✅ Выпила", callback_data=f"taken_{reminder['medication_id']}_{reminder['schedule_id']}_{reminder['scheduled_date']}")],
            [InlineKeyboardButton("⏰ Отложить ещё", callback_data=f"postpone_{reminder['medication_id']}_{reminder['schedule_id']}_{reminder['scheduled_date']}_{reminder['reminder_interval']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=reminder['user_telegram_id'],
                text=f"{greeting}, {nickname}!\n\n💊 Напоминаю про <b>{med['name']}</b>\n⏰ Это {reminder['postpone_count']}-е напоминание",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

            delete_postponed_reminder(reminder['id'])
        except Exception as e:
            logger.error(f"Ошибка отправки отложенного напоминания: {e}")

async def check_unanswered_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверка неотвеченных напоминаний для автоповтора (каждые 15 мин, макс 5 раз)"""
    reminders = get_unanswered_reminders()
    
    for reminder in reminders:
        med = get_medication_by_id(reminder['medication_id'])
        
        if not med or not med['is_active']:
            delete_active_reminder(reminder['medication_id'], reminder['schedule_id'], 
                                  datetime.strptime(reminder['scheduled_date'], '%Y-%m-%d').date())
            continue
        
        nickname = get_random_nickname()
        greeting = get_greeting_by_time()
        
        # Получаем reminder_interval из schedules
        schedules = get_medication_schedules(reminder['medication_id'])
        sched = next((s for s in schedules if s['id'] == reminder['schedule_id']), None)
        reminder_interval = sched['reminder_interval'] if sched else 60
        
        keyboard = [
            [InlineKeyboardButton("✅ Выпила", callback_data=f"taken_{reminder['medication_id']}_{reminder['schedule_id']}_{reminder['scheduled_date']}")],
            [InlineKeyboardButton("⏰ Отложить", callback_data=f"postpone_{reminder['medication_id']}_{reminder['schedule_id']}_{reminder['scheduled_date']}_{reminder_interval}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        count = reminder['reminder_count'] + 1
        
        try:
            await context.bot.send_message(
                chat_id=reminder['user_telegram_id'],
                text=f"{greeting}, {nickname}!\n\n💊 Напоминаю принять <b>{med['name']}</b>\n🔔 Напоминание {count} из 5",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            # Обновляем счётчик или удаляем если достигли лимита
            if count >= 5:
                delete_active_reminder(reminder['medication_id'], reminder['schedule_id'], 
                                      datetime.strptime(reminder['scheduled_date'], '%Y-%m-%d').date())
            else:
                update_active_reminder_count(reminder['id'])
        except Exception as e:
            logger.error(f"Ошибка отправки автоповтора напоминания: {e}")

# ============= АДМИН-ПАНЕЛЬ =============

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель (только для ADMIN_ID)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет доступа к админ-панели")
        return

    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Общая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📨 Отправить сообщение", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💾 Скачать базу данных", callback_data="admin_download_db")],
        [InlineKeyboardButton("🔙 Закрыть", callback_data="admin_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "👨‍💼 <b>Админ-панель</b>\n\nВыберите действие:"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def admin_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список пользователей"""
    query = update.callback_query
    await query.answer()

    users = get_all_users()

    text = "👥 <b>Пользователи бота:</b>\n\n"

    for user in users:
        user_id = user['id']
        stats = get_user_statistics(user_id)
        active_meds = get_active_medications(user_id)

        text += f"<b>{user['name']}</b> (ID: {user['telegram_id']})\n"
        text += f"  💊 Активных: {len(active_meds)}\n"
        text += f"  ✅ Курсов: {stats['completed_courses']}\n"
        text += f"  📈 Успешность: {stats['success_rate']}%\n"
        text += f"  🔥 Серия: {stats['current_streak']} дней\n\n"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(text[:4000], reply_markup=reply_markup, parse_mode='HTML')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общая статистика"""
    query = update.callback_query
    await query.answer()

    users = get_all_users()

    total_users = len(users)
    total_medications = 0
    total_taken = 0
    total_courses = 0

    for user in users:
        stats = get_user_statistics(user['id'])
        active_meds = get_active_medications(user['id'])

        total_medications += len(active_meds)
        total_taken += stats['total_taken']
        total_courses += stats['completed_courses']

    text = "📊 <b>Общая статистика бота:</b>\n\n"
    text += f"👥 Пользователей: {total_users}\n"
    text += f"💊 Активных лекарств: {total_medications}\n"
    text += f"✅ Всего курсов завершено: {total_courses}\n"
    text += f"💊 Всего таблеток принято: {total_taken}\n"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки"""
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "📨 <b>Рассылка сообщения</b>\n\n"
        "Отправьте текст сообщения, которое получат все пользователи.\n"
        "Или отправьте /cancel для отмены.",
        parse_mode='HTML'
    )

    return ADMIN_BROADCAST

async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка рассылки"""
    text = update.message.text

    users = get_all_users()
    success = 0
    failed = 0

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user['telegram_id'],
                text=f"📢 <b>Сообщение от администратора:</b>\n\n{text}",
                parse_mode='HTML'
            )
            success += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user['telegram_id']}: {e}")
            failed += 1

    await update.message.reply_text(
        f"✅ Рассылка завершена!\n\n"
        f"Успешно: {success}\n"
        f"Ошибок: {failed}"
    )

    return ConversationHandler.END

async def admin_download_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить файл базы данных админу"""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ У вас нет доступа к этой функции", show_alert=True)
        return

    try:
        await query.message.edit_text("📦 Подготавливаю базу данных...")

        with open(DATABASE_NAME, 'rb') as db_file:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=db_file,
                filename=DATABASE_NAME,
                caption=f"💾 <b>База данных medications.db</b>\n\n📅 Создано: {datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M')}",
                parse_mode='HTML'
            )

        await query.message.edit_text(
            "✅ База данных успешно отправлена!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="admin_panel")
            ]])
        )
    except Exception as e:
        logger.error(f"❌ Ошибка отправки базы данных: {e}")
        await query.message.edit_text(
            f"❌ Ошибка при отправке базы данных: {e}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="admin_panel")
            ]])
        )

async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть админ-панель"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()

# ============= ОБРАБОТЧИКИ АВТОРИЗАЦИИ =============

async def handle_auth_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка разрешения доступа пользователю"""
    query = update.callback_query
    telegram_id = int(query.data.split('_')[-1])

    # Устанавливаем авторизацию
    set_user_authorization(telegram_id, True)

    # Получаем информацию о пользователе
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT name FROM users WHERE telegram_id = ?', (telegram_id,))
    result = c.fetchone()
    conn.close()

    user_name = result['name'] if result else 'Пользователь'

    await query.answer("✅ Доступ разрешён")
    await query.edit_message_text(
        f"✅ <b>Доступ разрешён</b>\n\n"
        f"👤 {user_name} (ID: {telegram_id}) теперь может использовать бота.",
        parse_mode='HTML'
    )

    # Уведомляем пользователя
    try:
        await context.bot.send_message(
            chat_id=telegram_id,
            text="✅ Ваш запрос на доступ одобрен!\n\n"
                 "Теперь вы можете использовать бота. Нажмите /start для начала."
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю: {e}")

async def handle_auth_deny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запрета доступа пользователю"""
    query = update.callback_query
    telegram_id = int(query.data.split('_')[-1])

    # Получаем информацию о пользователе
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT name FROM users WHERE telegram_id = ?', (telegram_id,))
    result = c.fetchone()
    conn.close()

    user_name = result['name'] if result else 'Пользователь'

    await query.answer("❌ Доступ запрещён")
    await query.edit_message_text(
        f"❌ <b>Доступ запрещён</b>\n\n"
        f"👤 {user_name} (ID: {telegram_id}) не получил доступ к боту.",
        parse_mode='HTML'
    )

    # Уведомляем пользователя
    try:
        await context.bot.send_message(
            chat_id=telegram_id,
            text="❌ К сожалению, ваш запрос на доступ был отклонён."
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю: {e}")

# ============= ОБРАБОТЧИКИ ТЕКСТОВЫХ СООБЩЕНИЙ =============

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых кнопок главного меню"""
    user = update.effective_user

    # Проверка авторизации
    if not is_user_authorized(user.id):
        await update.message.reply_text(
            "❌ У вас нет доступа к этому боту.\n\n"
            "Ваш запрос на доступ ожидает одобрения администратора."
        )
        return

    text = update.message.text

    if text == "💊 Лекарства":
        await medications_menu(update, context)
    elif text == "⚙️ Настройки":
        await settings_menu(update, context)
    elif text == "📊 Статистика":
        await show_statistics(update, context)
    elif text == "📅 Календарь":
        await show_calendar(update, context)
    elif text == "❓ Помощь":
        await help_command(update, context)

# ============= ОБРАБОТЧИКИ CALLBACK =============

async def handle_callback_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback-кнопок"""
    query = update.callback_query
    data = query.data
    user = update.effective_user

    # Обработка авторизации (без проверки доступа)
    if data.startswith("auth_approve_") or data.startswith("auth_deny_"):
        if data.startswith("auth_approve_"):
            await handle_auth_approve(update, context)
        elif data.startswith("auth_deny_"):
            await handle_auth_deny(update, context)
        return

    # Проверка авторизации для всех остальных callback
    if not is_user_authorized(user.id):
        await query.answer("❌ У вас нет доступа к этому боту", show_alert=True)
        return

    # Главное меню
    if data == "main_menu":
        await query.answer()
        await query.message.delete()
        await start_command(update, context)

    # Лекарства
    elif data == "medications":
        await medications_menu(update, context)
    elif data == "med_current":
        await show_current_medications(update, context)
    elif data == "med_completed":
        await show_completed_medications(update, context)
    elif data.startswith("med_detail_"):
        await show_medication_detail(update, context)

    # Настройки
    elif data == "settings":
        await settings_menu(update, context)
    elif data == "edit_medications":
        await edit_medications_menu(update, context)
    elif data.startswith("edit_med_"):
        await edit_medication_actions(update, context)

    # Редактирование
    elif data.startswith("edit_name_"):
        return await edit_med_name_start(update, context)
    elif data.startswith("edit_duration_"):
        return await edit_med_duration_start(update, context)
    elif data.startswith("edit_schedule_type_"):
        return await edit_schedule_type_start(update, context)
    elif data.startswith("edit_sched_"):
        return await edit_schedule_type(update, context)
    elif data.startswith("edit_weekday_") or data == "edit_weekdays_done":
        return await edit_weekdays_select(update, context)
    elif data.startswith("edit_frequency_"):
        return await edit_frequency_start(update, context)
    elif data.startswith("edit_freq_"):
        return await edit_frequency(update, context)
    elif data.startswith("edit_time_"):
        return await edit_frequency_start(update, context)  # Переход к частоте, а затем к времени
    elif data.startswith("edit_period_"):
        return await edit_time_period(update, context)
    elif data.startswith("edit_time_"):
        return await edit_time_input(update, context)
    elif data.startswith("edit_reminder_"):
        return await edit_reminder_start(update, context)
    elif data.startswith("final_reminder_"):
        return await edit_reminder_save(update, context)
    elif data.startswith("edit_reminder_int_"):
        return await edit_reminder_interval_complete(update, context)
    # Добавьте аналогичные для других edit_ (schedule_type, frequency, times, reminder)

    elif data.startswith("extend_"):
        if data.startswith("extend_days_"):
            await extend_course_days(update, context)
        else:
            await extend_course(update, context)
    elif data.startswith("complete_"):
        if data.startswith("complete_confirm_"):
            await complete_course_confirm(update, context)
        else:
            await complete_course(update, context)
    elif data.startswith("delete_"):
        if data.startswith("delete_confirm_"):
            await delete_medication_confirm(update, context)
        else:
            await delete_medication(update, context)

    elif data == "cancel_add_med":
        await cancel_add_medication(update, context)

    # Напоминания
    elif data.startswith("taken_"):
        await handle_taken(update, context)
    elif data.startswith("postpone_"):
        await handle_postpone(update, context)

    # Админ
    elif data == "admin_panel":
        await admin_panel(update, context)
    elif data == "admin_users":
        await admin_users_list(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "admin_broadcast":
        return await admin_broadcast_start(update, context)
    elif data == "admin_download_db":
        await admin_download_db(update, context)
    elif data == "admin_close":
        await admin_close(update, context)

    # Другие callback для add/edit (duration, schedule, etc.)
    elif data.startswith("duration_"):
        await add_medication_duration(update, context)
    elif data.startswith("schedule_"):
        await add_medication_schedule_type(update, context)
    elif data.startswith("weekday_") or data == "weekdays_done":
        await add_medication_weekdays(update, context)
    elif data.startswith("freq_"):
        await add_medication_frequency(update, context)
    elif data.startswith("period_"):
        await add_medication_time_period(update, context)
    elif data.startswith("time_"):
        await add_medication_time_input(update, context)
    elif data.startswith("reminder_"):
        await add_medication_reminder(update, context)
    elif data.startswith("dosage_"):
        await add_medication_dosage_choice(update, context)
    elif data == "confirm_yes":
        await confirm_medication(update, context)

# ============= ПРОВЕРКА ОКОНЧАНИЯ КУРСОВ =============

async def check_course_endings(context: ContextTypes.DEFAULT_TYPE):
    """Проверка заканчивающихся курсов"""
    conn = get_connection()
    c = conn.cursor()

    today = datetime.now(TIMEZONE).date()
    tomorrow = today + timedelta(days=1)

    # Курсы, которые заканчиваются завтра
    c.execute('''SELECT m.id, m.name, m.end_date, u.telegram_id
                 FROM medications m
                 JOIN users u ON m.user_id = u.id
                 WHERE m.is_active = 1 AND m.end_date = ?''', (tomorrow.isoformat(),))

    ending_soon = c.fetchall()

    for med in ending_soon:
        keyboard = [
            [InlineKeyboardButton("✅ Да, завершён", callback_data=f"complete_confirm_{med['id']}")],
            [InlineKeyboardButton("➕ Продлить", callback_data=f"extend_{med['id']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=med['telegram_id'],
                text=f"👋 Солнышко, завтра заканчивается курс <b>{med['name']}</b>\n\n"
                     f"Всё идёт по плану?",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об окончании: {e}")

    conn.close()

# ============= ГЛАВНАЯ ФУНКЦИЯ =============

def main():
    """Главная функция запуска бота"""

    # Инициализация БД
    init_database()

    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler для добавления/редактирования
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_schedule_type_start, pattern="^edit_schedule_type_"),
            CallbackQueryHandler(edit_frequency_start, pattern="^edit_frequency_"),
            CallbackQueryHandler(edit_time_input, pattern="^edit_time_"),
            CallbackQueryHandler(edit_reminder_start, pattern="^edit_reminder_"),
            CallbackQueryHandler(add_medication_start, pattern="add_medication"),
            CallbackQueryHandler(edit_med_name_start, pattern="^edit_name_"),
            CallbackQueryHandler(edit_med_duration_start, pattern="^edit_duration_"),
            CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")
        ],
        states={
            ADD_MED_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_name),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$")
            ],
            ADD_MED_DURATION: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_duration)
            ],
            ADD_MED_DURATION_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_duration_input),
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$")
            ],
            ADD_MED_SCHEDULE_TYPE: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_schedule_type)
            ],
            ADD_MED_WEEKDAYS: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_weekdays)
            ],
            ADD_MED_FREQUENCY: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_frequency)
            ],
            ADD_MED_TIMES_PERIOD: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_time_period)
            ],
            ADD_MED_TIME_INPUT: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_time_input),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_time_input)
            ],
            ADD_MED_REMINDER: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_reminder)
            ],
            ADD_MED_DOSAGE_CHOICE: [
                CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(add_medication_dosage_choice)
            ],
            ADD_MED_DOSAGE_SCHEME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_dosage_scheme),
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$")
            ],
            ADD_MED_CONFIRM: [
                CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
                CallbackQueryHandler(confirm_medication)
            ],
            EDIT_MED_NAME_INPUT: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_med_name_input)
            ],
            EDIT_MED_DURATION: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                CallbackQueryHandler(edit_med_duration)
            ],
            EDIT_MED_DURATION_INPUT: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_med_duration_input)
            ],
            EDIT_MED_SCHEDULE_TYPE: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                CallbackQueryHandler(edit_schedule_type)
            ],
            EDIT_MED_WEEKDAYS: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                CallbackQueryHandler(edit_weekdays_select)
            ],
            EDIT_MED_FREQUENCY: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                CallbackQueryHandler(edit_frequency)
            ],
            EDIT_MED_TIMES_PERIOD: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                CallbackQueryHandler(edit_time_period)
            ],
            EDIT_MED_TIME_INPUT: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                CallbackQueryHandler(edit_time_input),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_time_input)
            ],
            EDIT_MED_REMINDER: [
                CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
                CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
                CallbackQueryHandler(edit_reminder_interval_complete, pattern="^edit_reminder_int_"),
                CallbackQueryHandler(edit_reminder_save, pattern="^final_reminder_")
            ],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$"),
            CallbackQueryHandler(cancel_edit_medication, pattern="^cancel_edit_med$"),
            CallbackQueryHandler(go_back_step, pattern="^nav_back$"),
            CallbackQueryHandler(go_back_edit_step, pattern="^nav_back_edit$"),
            CommandHandler("cancel", cancel_add_medication)
        ],
    )



    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(conv_handler)
    # Обработчики callback
    application.add_handler(CallbackQueryHandler(handle_callback_queries))

    # Обработчики текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    # Задачи по расписанию
    job_queue = application.job_queue

    # Проверка напоминаний каждую минуту
    job_queue.run_repeating(send_medication_reminder, interval=60, first=10)

    # Проверка отложенных напоминаний каждые 5 минут
    job_queue.run_repeating(check_postponed_reminders, interval=300, first=30)
    
    # Проверка неотвеченных напоминаний каждые 15 минут для автоповтора
    job_queue.run_repeating(check_unanswered_reminders, interval=900, first=60)

    # Проверка окончания курсов раз в день в 20:00
    job_queue.run_daily(check_course_endings, time=dt_time(20, 0, 0, tzinfo=TIMEZONE))

    # Запуск бота
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
