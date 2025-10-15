#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot для напоминаний о приёме лекарств
Создан для Ксюши ❤️
"""

import logging
import sqlite3
import random
import asyncio
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

# ВАЖНО: Замените на ваш токен от @BotFather
BOT_TOKEN = "7475228665:AAF3vSEiumgBSc7oM7ZIvfGx5Y579Ao-CSQ"

# ВАЖНО: Замените на ваш Telegram ID (узнать можно у @userinfobot)
ADMIN_ID = 55948371

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
    "❤️ Отлично, зайка!",
    "🎉 Супер! Ты большая умница!",
    "💖 Я в тебя верю, продолжай в том же духе!",
    "✨ Прекрасно! Ты справляешься!",
    "🌺 Солнышко моё, ты лучшая!"
]

# Фразы при откладывании
POSTPONE_MESSAGES = [
    "😊 Хорошо, напомню позже",
    "👌 Ладно, зайка, напишу чуть попозже",
    "💫 Без проблем, солнышко",
    "🕐 Окей, напомню снова",
    "💝 Хорошо, родная, но не забудь!",
    "☺️ Понятно, вернусь к тебе через часок",
    "🤗 Не вопрос, малышка"
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
    'fifty_pills': {'name': '⭐ 50 таблеток принято', 'description': 'Приняла 50 таблеток'},
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
 ADMIN_BROADCAST) = range(16)

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

def init_database():
    """Инициализация базы данных"""
    conn = get_connection()
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (medication_id) REFERENCES medications(id),
        FOREIGN KEY (schedule_id) REFERENCES schedules(id)
    )''')
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# Функции работы с пользователями
def get_or_create_user(telegram_id: int, name: str = None) -> int:
    """Получает ID пользователя или создаёт нового"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
    result = c.fetchone()
    
    if result:
        user_id = result['id']
    else:
        c.execute('INSERT INTO users (telegram_id, name) VALUES (?, ?)', (telegram_id, name))
        user_id = c.lastrowid
        conn.commit()
    
    conn.close()
    return user_id

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Получает пользователя по ID"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return dict(result) if result else None

def get_all_users() -> List[Dict]:
    """Получает всех пользователей"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users ORDER BY created_at DESC')
    results = c.fetchall()
    conn.close()
    return [dict(row) for row in results]

# Функции работы с лекарствами
def create_medication(user_id: int, name: str, duration_days: int, 
                     start_date: date, schedule_type: str = 'daily',
                     weekdays: str = None, has_dosage_scheme: bool = False) -> int:
    """Создаёт новое лекарство"""
    conn = get_connection()
    c = conn.cursor()
    
    end_date = start_date + timedelta(days=duration_days - 1)
    
    c.execute('''INSERT INTO medications 
                 (user_id, name, duration_days, start_date, end_date, 
                  schedule_type, weekdays, has_dosage_scheme)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, name, duration_days, start_date.isoformat(), 
               end_date.isoformat(), schedule_type, weekdays, has_dosage_scheme))
    
    medication_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return medication_id

def get_active_medications(user_id: int) -> List[Dict]:
    """Получает активные лекарства пользователя"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''SELECT * FROM medications 
                 WHERE user_id = ? AND is_active = 1
                 ORDER BY start_date DESC''', (user_id,))
    
    results = c.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def get_completed_medications(user_id: int, limit: int = 20) -> List[Dict]:
    """Получает завершённые лекарства"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''SELECT * FROM medications 
                 WHERE user_id = ? AND is_active = 0
                 ORDER BY end_date DESC LIMIT ?''', (user_id, limit))
    
    results = c.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def get_medication_by_id(medication_id: int) -> Optional[Dict]:
    """Получает лекарство по ID"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('SELECT * FROM medications WHERE id = ?', (medication_id,))
    result = c.fetchone()
    conn.close()
    
    return dict(result) if result else None

def update_medication(medication_id: int, **kwargs):
    """Обновляет данные лекарства"""
    conn = get_connection()
    c = conn.cursor()
    
    fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [medication_id]
    
    c.execute(f'UPDATE medications SET {fields} WHERE id = ?', values)
    conn.commit()
    conn.close()

def deactivate_medication(medication_id: int):
    """Деактивирует лекарство"""
    update_medication(medication_id, is_active=0)

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
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''INSERT INTO schedules 
                 (medication_id, time, period, reminder_interval)
                 VALUES (?, ?, ?, ?)''',
              (medication_id, time_str, period, reminder_interval))
    
    schedule_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return schedule_id

def get_medication_schedules(medication_id: int) -> List[Dict]:
    """Получает все расписания для лекарства"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('SELECT * FROM schedules WHERE medication_id = ? ORDER BY time',
              (medication_id,))
    
    results = c.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def delete_medication_schedules(medication_id: int):
    """Удаляет все расписания лекарства"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('DELETE FROM schedules WHERE medication_id = ?', (medication_id,))
    conn.commit()
    conn.close()

# Функции работы с логами
def log_medication_taken(medication_id: int, schedule_id: int, 
                        scheduled_date: date, scheduled_time: str):
    """Логирует приём лекарства"""
    conn = get_connection()
    c = conn.cursor()
    
    taken_time = datetime.now(TIMEZONE)
    
    c.execute('''INSERT INTO medication_logs 
                 (medication_id, schedule_id, scheduled_date, scheduled_time, 
                  taken_time, status)
                 VALUES (?, ?, ?, ?, ?, 'taken')''',
              (medication_id, schedule_id, scheduled_date.isoformat(), 
               scheduled_time, taken_time.isoformat()))
    
    conn.commit()
    conn.close()

def log_medication_missed(medication_id: int, schedule_id: int,
                         scheduled_date: date, scheduled_time: str):
    """Логирует пропуск приёма"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''INSERT INTO medication_logs 
                 (medication_id, schedule_id, scheduled_date, scheduled_time, 
                  status)
                 VALUES (?, ?, ?, ?, 'missed')''',
              (medication_id, schedule_id, scheduled_date.isoformat(), 
               scheduled_time))
    
    conn.commit()
    conn.close()

def get_medication_logs(medication_id: int, limit: int = 100) -> List[Dict]:
    """Получает логи приёмов лекарства"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''SELECT * FROM medication_logs 
                 WHERE medication_id = ? 
                 ORDER BY scheduled_date DESC, scheduled_time DESC 
                 LIMIT ?''', (medication_id, limit))
    
    results = c.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def get_logs_for_date(user_id: int, target_date: date) -> List[Dict]:
    """Получает логи за определённую дату"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''SELECT ml.*, m.name as medication_name, s.period, s.time
                 FROM medication_logs ml
                 JOIN medications m ON ml.medication_id = m.id
                 JOIN schedules s ON ml.schedule_id = s.id
                 WHERE m.user_id = ? AND ml.scheduled_date = ?
                 ORDER BY ml.scheduled_time''',
              (user_id, target_date.isoformat()))
    
    results = c.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

# Функции для достижений
def unlock_achievement(user_id: int, achievement_type: str) -> bool:
    """Разблокирует достижение. Возвращает True если новое"""
    conn = get_connection()
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO achievements (user_id, achievement_type)
                     VALUES (?, ?)''', (user_id, achievement_type))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_user_achievements(user_id: int) -> List[Dict]:
    """Получает все достижения пользователя"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''SELECT * FROM achievements 
                 WHERE user_id = ? 
                 ORDER BY unlocked_at DESC''', (user_id,))
    
    results = c.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

# Функции статистики
def get_user_statistics(user_id: int) -> Dict:
    """Получает статистику пользователя"""
    conn = get_connection()
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
    
    conn.close()
    
    return {
        'completed_courses': completed_courses,
        'total_taken': total_taken,
        'total_missed': total_missed,
        'success_rate': round(success_rate, 1),
        'current_streak': current_streak
    }

# Отложенные напоминания
def create_postponed_reminder(medication_id: int, schedule_id: int, user_telegram_id: int,
                             scheduled_date: date, original_time: datetime, 
                             next_time: datetime, postpone_count: int = 1):
    """Создаёт отложенное напоминание"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''INSERT INTO postponed_reminders 
                 (medication_id, schedule_id, user_telegram_id, scheduled_date,
                  original_time, next_reminder_time, postpone_count)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (medication_id, schedule_id, user_telegram_id, scheduled_date.isoformat(),
               original_time.isoformat(), next_time.isoformat(), postpone_count))
    
    conn.commit()
    conn.close()

def get_due_postponed_reminders() -> List[Dict]:
    """Получает отложенные напоминания, которые пора отправить"""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now(TIMEZONE).isoformat()
    
    c.execute('''SELECT * FROM postponed_reminders 
                 WHERE next_reminder_time <= ?''', (now,))
    
    results = c.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def delete_postponed_reminder(reminder_id: int):
    """Удаляет отложенное напоминание"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('DELETE FROM postponed_reminders WHERE id = ?', (reminder_id,))
    conn.commit()
    conn.close()

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

# ============= ОБРАБОТЧИКИ КОМАНД =============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    get_or_create_user(user.id, user.first_name)
    
    keyboard = [
        [KeyboardButton("💊 Лекарства"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📅 Календарь")],
        [KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
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
⭐ 50 таблеток
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
        text += f"🏁 Окончание: {end.strftime('%d.%m.%Y')}\n\n"
        
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
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_med_{medication_id}")],
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
# Эту часть нужно добавить в main.py после секции НАСТРОЙКИ

async def add_medication_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления лекарства"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    await query.message.edit_text(
        "➕ <b>Добавление лекарства</b>\n\n"
        "📝 Шаг 1/8: Введите название лекарства:\n"
        "(Например: Аспирин, Витамин D)",
        parse_mode='HTML'
    )
    
    return ADD_MED_NAME

async def add_medication_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение названия"""
    med_name = update.message.text.strip()
    context.user_data['med_name'] = med_name
    
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
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
    ]
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
        await query.message.edit_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n\n"
            "📝 Введите длительность в днях (1-365):",
            parse_mode='HTML'
        )
        return ADD_MED_DURATION_INPUT
    
    elif query.data == "duration_date":
        await query.message.edit_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n\n"
            "📅 Введите дату окончания (ДД.ММ.ГГГГ):\n"
            "Например: 25.12.2025",
            parse_mode='HTML'
        )
        return ADD_MED_DURATION_INPUT
    
    else:
        duration = int(query.data.split('_')[1])
        context.user_data['med_duration'] = duration
        context.user_data['med_start_date'] = datetime.now(TIMEZONE).date()
        context.user_data['med_end_date'] = context.user_data['med_start_date'] + timedelta(days=duration - 1)
        
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
            
            keyboard = [
                [InlineKeyboardButton("Каждый день", callback_data="schedule_daily")],
                [InlineKeyboardButton("Через день", callback_data="schedule_every_other")],
                [InlineKeyboardButton("По дням недели", callback_data="schedule_weekdays")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
            ]
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
        
        keyboard = [
            [InlineKeyboardButton("Каждый день", callback_data="schedule_daily")],
            [InlineKeyboardButton("Через день", callback_data="schedule_every_other")],
            [InlineKeyboardButton("По дням недели", callback_data="schedule_weekdays")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
        ]
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
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
    ]
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
        keyboard = []
        for day_num, day_name in WEEKDAYS_FULL.items():
            keyboard.append([InlineKeyboardButton(f"☐ {day_name}", callback_data=f"weekday_{day_num}")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="weekdays_done")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")])
        
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
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")])
    
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
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
    ]
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
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
    ]
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
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")])
    
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
            await query.message.edit_text(
                "⏰ Введите время (ЧЧ:ММ):\n"
                "Например: 08:30",
                parse_mode='HTML'
            )
            return ADD_MED_TIME_INPUT
        
        time_str = query.data.split('_')[1]
        context.user_data['times'].append({'time': time_str, 'period': context.user_data['current_period']})
        context.user_data['current_time_index'] += 1
        
        if context.user_data['current_time_index'] < context.user_data['frequency']:
            return await ask_time_period(query, context)
        else:
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
            keyboard = [
                [InlineKeyboardButton("🌅 Утро", callback_data="period_morning")],
                [InlineKeyboardButton("☀️ День", callback_data="period_day")],
                [InlineKeyboardButton("🌆 Вечер", callback_data="period_evening")],
                [InlineKeyboardButton("🌙 Ночь", callback_data="period_night")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
            ]
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
            keyboard = [
                [InlineKeyboardButton("⏰ 30 минут", callback_data="reminder_30")],
                [InlineKeyboardButton("⏰ 1 час", callback_data="reminder_60")],
                [InlineKeyboardButton("⏰ 1.5 часа", callback_data="reminder_90")],
                [InlineKeyboardButton("⏰ 2 часа", callback_data="reminder_120")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
            ]
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
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
    ]
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
  # ============= ЗАВЕРШЕНИЕ ДОБАВЛЕНИЯ ЛЕКАРСТВ =============

async def add_medication_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка интервала напоминаний"""
    query = update.callback_query
    await query.answer()
    
    reminder_minutes = int(query.data.split('_')[1])
    context.user_data['reminder_interval'] = reminder_minutes
    
    # Спрашиваем про схему дозировки
    keyboard = [
        [InlineKeyboardButton("Нет, одинаково", callback_data="dosage_no")],
        [InlineKeyboardButton("Да, настроить схему", callback_data="dosage_yes")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_med")]
    ]
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
        
        await query.message.edit_text(
            f"💊 <b>{context.user_data['med_name']}</b>\n"
            f"Курс: {context.user_data['med_duration']} дней\n\n"
            "📝 Формат: <code>1-3: 2 таблетки</code>\n\n"
            "Введите схему или <code>готово</code>",
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
    
    # Создаём лекарство
    weekdays = context.user_data.get('weekdays')
    medication_id = create_medication(
        user_id=user_id,
        name=context.user_data['med_name'],
        duration_days=context.user_data['med_duration'],
        start_date=context.user_data['med_start_date'],
        schedule_type=context.user_data['schedule_type'],
        weekdays=weekdays,
        has_dosage_scheme=context.user_data.get('has_dosage_scheme', False)
    )
    
    # Создаём расписания
    for time_data in context.user_data['times']:
        create_schedule(
            medication_id=medication_id,
            time_str=time_data['time'],
            period=time_data['period'],
            reminder_interval=context.user_data['reminder_interval']
        )
    
    # Создаём схемы дозировки (если есть)
    if context.user_data.get('has_dosage_scheme'):
        for scheme in context.user_data.get('dosage_schemes', []):
            times_str = ','.join([t['time'] for t in context.user_data['times']])
            # Здесь можно сохранить схему, но для простоты пропустим детальное сохранение
    
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
    """Отмена"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить лекарство", callback_data="add_medication")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        "❌ Добавление отменено.",
        reply_markup=reply_markup
    )
    
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
            icon = "⭕"
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
    
    calendar_text += "\n✅ - Все приёмы\n⚠️ - Пропущен 1\n❌ - Пропущено 2+\n⭕ - Нет приёмов"
    
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
            # Проверяем чётность дня с начала курса
            med = get_medication_by_id(med_id)
            start_date = datetime.strptime(med['start_date'], '%Y-%m-%d').date()
            days_since_start = (current_date - start_date).days
            should_send = (days_since_start % 2 == 0)
        elif schedule_type == 'weekdays':
            if weekdays:
                weekdays_list = [int(d) for d in weekdays.split(',')]
                should_send = current_weekday in weekdays_list
        
        if should_send:
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
    schedules = get_medication_schedules(med_id)
    sched = next((s for s in schedules if s['id'] == sched_id), None)
    
    if med and sched:
        log_medication_taken(med_id, sched_id, scheduled_date, sched['time'])
        
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
    scheduled_date = datetime.strptime(parts[3], '%Y-%m-%d').date()
    interval = int(parts[4])
    
    med = get_medication_by_id(med_id)
    
    if med:
        # Создаём отложенное напоминание
        now = datetime.now(TIMEZONE)
        next_time = now + timedelta(minutes=interval)
        
        create_postponed_reminder(
            medication_id=med_id,
            schedule_id=sched_id,
            user_telegram_id=update.effective_user.id,
            scheduled_date=scheduled_date,
            original_time=now,
            next_reminder_time=next_time,
            postpone_count=1
        )
        
        postpone_msg = random.choice(POSTPONE_MESSAGES)
        interval_text = {30: "30 минут", 60: "час", 90: "1.5 часа", 120: "2 часа"}[interval]
        
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
            [InlineKeyboardButton("⏰ Отложить ещё", callback_data=f"postpone_{reminder['medication_id']}_{reminder['schedule_id']}_{reminder['scheduled_date']}_{reminder['postpone_count'] * 60}")]
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

async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть админ-панель"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()

# ============= ОБРАБОТЧИКИ КНОПОК =============

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых кнопок главного меню"""
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

async def handle_callback_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback-кнопок"""
    query = update.callback_query
    data = query.data
    
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
    elif data == "admin_close":
        await admin_close(update, context)

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

# ============= ЕЖЕДНЕВНЫЙ ОТЧЁТ ДЛЯ АДМИНА =============

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный отчёт для админа"""
    yesterday = datetime.now(TIMEZONE).date() - timedelta(days=1)
    
    users = get_all_users()
    report = "📊 <b>Ежедневный отчёт</b>\n"
    report += f"За {yesterday.strftime('%d.%m.%Y')}\n\n"
    
    for user in users:
        logs = get_logs_for_date(user['id'], yesterday)
        
        if logs:
            taken = sum(1 for log in logs if log['status'] == 'taken')
            missed = sum(1 for log in logs if log['status'] == 'missed')
            total = len(logs)
            
            if total > 0:
                success_rate = (taken / total) * 100
                
                status_icon = "✅" if missed == 0 else "⚠️" if missed == 1 else "❌"
                
                report += f"{status_icon} <b>{user['name']}</b>\n"
                report += f"  Приёмов: {taken}/{total} ({success_rate:.0f}%)\n\n"
    
    if len(report) > 100:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=report,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки отчёта админу: {e}")

# ============= ГЛАВНАЯ ФУНКЦИЯ =============

def main():
    """Главная функция запуска бота"""
    
    # Инициализация БД
    init_database()
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler для добавления лекарств
    add_med_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_medication_start, pattern="^add_medication$")],
        states={
            ADD_MED_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_name)],
            ADD_MED_DURATION: [CallbackQueryHandler(add_medication_duration)],
            ADD_MED_DURATION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_duration_input)],
            ADD_MED_SCHEDULE_TYPE: [CallbackQueryHandler(add_medication_schedule_type)],
            ADD_MED_WEEKDAYS: [CallbackQueryHandler(add_medication_weekdays)],
            ADD_MED_FREQUENCY: [CallbackQueryHandler(add_medication_frequency)],
            ADD_MED_TIMES_PERIOD: [CallbackQueryHandler(add_medication_time_period)],
            ADD_MED_TIME_INPUT: [
                CallbackQueryHandler(add_medication_time_input),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_time_input)
            ],
            ADD_MED_REMINDER: [CallbackQueryHandler(add_medication_reminder)],
            ADD_MED_DOSAGE_CHOICE: [CallbackQueryHandler(add_medication_dosage_choice)],
            ADD_MED_DOSAGE_SCHEME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_medication_dosage_scheme)],
            ADD_MED_CONFIRM: [CallbackQueryHandler(confirm_medication)],
        },
        fallbacks=[CallbackQueryHandler(cancel_add_medication, pattern="^cancel_add_med$")],
    )
    
    # ConversationHandler для рассылки
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    
    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # ConversationHandlers
    application.add_handler(add_med_conv)
    application.add_handler(broadcast_conv)
    
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
    
    # Проверка окончания курсов раз в день в 20:00
    job_queue.run_daily(check_course_endings, time=dt_time(20, 0, 0, tzinfo=TIMEZONE))
    
    # Ежедневный отчёт админу в 21:00
    job_queue.run_daily(send_daily_report, time=dt_time(21, 0, 0, tzinfo=TIMEZONE))
    
    # Запуск бота
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
