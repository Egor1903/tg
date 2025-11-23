import os
import logging
import uuid
import asyncio
import tempfile
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import yadisk
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
import textwrap
import requests
import io
from reportlab.lib import colors
import aiohttp
import re
import json

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Определяем абсолютный путь к логотипу
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logo.png')

# Токены для разных Яндекс.Дисков
YANDEX_DISKS = {
    "main": {
        "name": "📁 Основной диск",
        "token": 'y0__xDh-a-6CBjQ3Togl8K-zxQwvevu7QfZ2jaKix2rNGJBVOZ-1WVdVmdecQ'
    },
    "backup": {
        "name": "📁 Резервный диск",
        "token": 'y0__xDh-a-6CBjQ3Togl8K-zxQwvevu7QfZ2jaKix2rNGJBVOZ-1WVdVmdecQ'
    },
    "archive": {
        "name": "📁 Архивный диск",
        "token": 'y0__xDh-a-6CBjQ3Togl8K-zxQwvevu7QfZ2jaKix2rNGJBVOZ-1WVdVmdecQ'
    }
}

BOT_TOKEN = '8372183872:AAFJrDSUpUkjY4whA7S0ggjQ5q3Q8W1RHhM'

# Проверка токенов
if not BOT_TOKEN:
    raise ValueError("Не установлен BOT_TOKEN")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Инициализация Яндекс.Дисков
y_disks = {}
for disk_id, disk_info in YANDEX_DISKS.items():
    try:
        y = yadisk.YaDisk(token=disk_info["token"])
        if y.check_token():
            y_disks[disk_id] = y
            logger.info(f"Подключение к {disk_info['name']} установлено успешно")
        else:
            logger.error(f"Неверный токен для {disk_info['name']}")
    except Exception as e:
        logger.error(f"Ошибка подключения к {disk_info['name']}: {e}")

if not y_disks:
    raise ValueError("Не удалось подключиться ни к одному Яндекс.Диску")

# Категории на русском с нумерацией
CATEGORIES = {
    "1. Маркировки": "1. Маркировки",
    "2. Кузов": "2. Кузов",
    "3. Колеса": "3. Колеса",
    "4. Диагностика": "4. Диагностика",
    "5. Салон": "5. Салон",
    "6. Моторный отсек": "6. Моторный отсек",
    "7. Остекление": "7. Остекление",
    "8. Автотека": "8. Автотека",
    "9. Краткий вывод": "9. Краткий вывод",
    "10. Создать папку": "10. Создать папку"
}

# Многоязычные тексты - ОБНОВЛЕНО ДЛЯ LITTERBOX
MULTILANGUAGE_TEXTS = {
    "ru": {
        "welcome": "🚗 Добро пожаловать в AutoCheckAssistent_PRO!",
        "choose_language": "🌍 Выберите язык:",
        "choose_disk": "📁 Выберите Яндекс.Диск для работы:",
        "disk_selected": "✅ Выбран диск: <b>{disk_name}</b>",
        "start_project": "📝 Введите название проекта (марка и модель автомобиля):\nНапример: Mercedes-Benz E-Class 2023",
        "project_created": "✅ Проект '{project_name}' создан!\n📁 Диск: {disk_name}",
        "choose_category": "Выберите категорию для загрузки:",
        "category_selected": "📂 Категория: <b>{category}</b>\n\nТеперь отправляйте фотографии. Они будут собраны в альбом и загружены пакетом.",
        "instruction": """
📖 <b>AutoCheckAssistent_PRO - Полная инструкция</b>

🚀 <b>Быстрый старт:</b>
1. Нажмите <b>🚀 Start</b>
2. Выберите Яндекс.Диск
3. Введите название автомобиля
4. Выберите категорию
5. Загружайте файлы!

📁 <b>Доступные Яндекс.Диски:</b>
• Основной диск - для текущих проектов
• Резервный диск - для бэкапов  
• Архивный диск - для хранения

📂 <b>Основные категории:</b>
1. Маркировки - VIN, номера
2. Кузов - повреждения, состояние
3. Колеса - шины, диски
4. Диагностика - ошибки, сканер
5. Салон - интерьер, кресла
6. Моторный отсек - двигатель
7. Остекление - стекла
8. Автотека - документы
9. Краткий вывод - отчет PDF
10. Создать папку - своя категория

📷 <b>Работа с файлами:</b>
• <b>Фото</b> - отправляйте несколько сразу
• <b>Видео</b> - все форматы (до 2 ГБ через Telegram)
• <b>Документы</b> - PDF, Word, Excel
• <b>Текст</b> - авто-конвертация в PDF

🎯 <b>Советы:</b>
• Группируйте фото по зонам авто
• Используйте текстовые заметки
• Создавайте custom папки
• Выбирайте подходящий диск для разных типов проектов

🔗 <b>Поделиться проектом:</b>
После завершения работы с проектом используйте кнопку "🔗 Получить ссылку" чтобы получить публичную ссылку для передачи другим пользователям.

📞 <b>Поддержка:</b>
@GOSNOMER_AI | +7 9871370894
        """,
        "support": "📞 Поддержка\n\n💬 Telegram: @GOSNOMER_AI\n📱 Телефон: +7 9871370894\n🕒 24/7",
        "back": "🔙 Назад",
        "support_btn": "📞 Поддержка",
        "instruction_btn": "📋 Инструкция",
        "language_btn": "🌐 Язык",
        "disk_btn": "📁 Сменить диск",
        "link_btn": "🔗 Получить ссылку",
        "text_input": "📝 Введите текст для сохранения в PDF:\n\nТекст будет автоматически преобразован в PDF файл и сохранен в текущей категории.",
        "text_saved": "✅ Текст сохранен в формате PDF!",
        "brief_conclusion": "📝 Напишите краткий вывод по техническому состоянию автомобиля:\n\n• Общее состояние\n• Основные проблемы\n• Рекомендации\n• Итоговая оценка",
        "brief_saved": "✅ Краткий вывод сохранен в формате PDF!",
        "custom_folder": "📝 Введите название для новой папки:",
        "folder_created": "✅ Папка '{folder_name}' создана!",
        "photo_uploaded": "✅ Загружено {count} фото в '{category}'",
        "video_uploaded": "✅ Видео сохранено в '{category}'",
        "document_uploaded": "✅ Документ '{filename}' сохранен в '{category}'",
        "error_no_project": "❌ Сначала создайте проект через /start",
        "error_no_category": "❌ Сначала выберите проект и категорию",
        "error_upload": "❌ Ошибка при загрузке файла",
        "error_project": "❌ Ошибка при создании проекта. Попробуйте еще раз.",
        "error_general": "❌ Произошла ошибка. Попробуйте еще раз.",
        "error_no_disk": "❌ Сначала выберите Яндекс.Диск",
        "access_denied": "❌ Доступ запрещен",
        "getting_link": "🔄 Получаю публичную ссылку на проект...",
        "link_created": "🔗 <b>Публичная ссылка на проект:</b>\n\n{link}\n\n📁 <b>Проект:</b> {project_name}\n⏰ <b>Ссылка действительна:</b> 6 месяцев\n⚠️ <b>Внимание:</b> Все файлы в папке будут доступны по этой ссылку",
        "link_error": "❌ Не удалось получить публичную ссылку. Попробуйте позже.",
        "photo_ready": "📸 Теперь можете отправлять фотографии. Они будут автоматически сохранены в текущей категории.",
        "video_ready": "🎥 Теперь можете отправлять видеофайлы. Они будут автоматически сохранены в текущей категории.",
        "document_ready": "📄 Теперь можете отправлять документы (PDF, Word, Excel и другие). Они будут автоматически сохранены в текущей категории.",
        "text_ready": "📝 Теперь можете вводить текст для сохранения в формате PDF. Текст будет автоматически преобразован и сохранен в текущей категории.",
        # ОБНОВЛЕНО: Заменен на Litterbox
        "video_upload_choice": "🎥 <b>Выберите способ загрузки видео:</b>\n\n• <b>📤 Загрузить через Telegram</b> - для видео до 20 Мб\n• <b>🔗 Загрузить по ссылке Litterbox</b> - для больших видео",
        "upload_via_telegram": "📤 Загрузить через Telegram",
        "upload_via_link": "🔗 Загрузить по ссылке",
        "video_too_big": """
📹 Видео файл слишком большой для загрузки через Telegram.

🔗 Пожалуйста, загрузите ваше видео на Litterbox и пришлите мне ссылку для скачивания.

📝 <b>Инструкция по загрузке на Litterbox:</b>

1. Перейдите на https://litterbox.catbox.moe
2. Нажмите "Choose File" и выберите ваше видео
3. Нажмите "Upload"
4. Дождитесь загрузки файла
5. Скопируйте ссылку для скачивания и пришлите её мне

⚠️ <b>Ссылка должна выглядеть примерно так:</b> 
• https://files.catbox.moe/abc123.mp4
• https://litter.catbox.moe/abc123.mp4  
• https://litterbox.catbox.moe/abc123.mp4
        """,
        "video_link_instruction": """
🔗 <b>Загрузка видео по ссылке Litterbox</b>

📝 <b>Инструкция по загрузке на Litterbox:</b>

1. Перейдите на https://litterbox.catbox.moe
2. Нажмите "Choose File" и выберите ваше видео
3. Нажмите "Upload"
4. Дождитесь загрузки файла
5. Скопируйте ссылку для скачивания и пришлите её мне

⚠️ <b>Ссылка может выглядеть так:</b>
• https://files.catbox.moe/abc123.mp4
• https://litter.catbox.moe/abc123.mp4  
• https://litterbox.catbox.moe/abc123.mp4
        """,
        "downloading_video": "🔄 Скачиваю видео по вашей ссылке...",
        "video_download_success": "✅ Видео успешно загружено на Яндекс.Диск!",
        "video_download_error": "❌ Не удалось скачать видео по указанной ссылке. Проверьте ссылку и попробуйте еще раз.",
        "invalid_url": "❌ Это не похоже на валидную ссылку Litterbox. Пожалуйста, пришлите ссылку в одном из форматов:\n• https://files.catbox.moe/abc123.mp4\n• https://litter.catbox.moe/abc123.mp4\n• https://litterbox.catbox.moe/abc123.mp4",
        "service_unavailable": "❌ Litterbox временно недоступен. Попробуйте загрузить видео через Telegram.",
        "file_too_large": "❌ Файл слишком большой.",
        # ОБНОВЛЕНО: Инструкция для Litterbox
        "litterbox_upload_instruction": """
📤 <b>Загрузка на Litterbox</b>

1. Перейдите на https://litterbox.catbox.moe
2. Нажмите "Choose File" и выберите ваше видео
3. Нажмите "Upload"
4. Дождитесь загрузки файла (может занять несколько минут для больших файлов)
5. Скопируйте ссылку для скачивания
6. Пришлите мне эту ссылку

⚠️ <b>Ссылка должна выглядеть так:</b> 
• https://files.catbox.moe/abc123.mp4
• https://litter.catbox.moe/abc123.mp4  
• https://litterbox.catbox.moe/abc123.mp4

💡 <b>Особенности Litterbox:</b>
• Максимальный размер файла: 1 ГБ
• Файлы хранятся 24 часа
• Не требует регистрации
• Быстрая загрузка
• Прямые ссылки на скачивание
        """
    },
    "en": {
        "welcome": "🚗 Welcome to AutoCheckAssistent_PRO!",
        "choose_language": "🌍 Choose language:",
        "choose_disk": "📁 Choose Yandex.Disk for work:",
        "disk_selected": "✅ Selected disk: <b>{disk_name}</b>",
        "start_project": "📝 Enter project name (car brand and model):\nExample: Mercedes-Benz E-Class 2023",
        "project_created": "✅ Project '{project_name}' created!\n📁 Disk: {disk_name}",
        "choose_category": "Choose category for upload:",
        "category_selected": "📂 Category: <b>{category}</b>\n\nNow send photos. They will be grouped into albums and uploaded in batches.",
        "instruction": """
📖 <b>AutoCheckAssistent_PRO - Complete Guide</b>

🚀 <b>Quick Start:</b>
1. Click <b>🚀 Start</b>
2. Choose Yandex.Disk
3. Enter vehicle name
4. Select category
5. Upload files!

📁 <b>Available Yandex.Disks:</b>
• Main disk - for current projects
• Backup disk - for backups
• Archive disk - for storage

📂 <b>Main Categories:</b>
1. Markings - VIN, labels
2. Body - damages, condition
3. Wheels - tires, rims
4. Diagnostics - errors, scanner
5. Interior - seats, dashboard
6. Engine Bay - engine
7. Glass - windows
8. Documentation - papers
9. Brief Report - PDF summary
10. Create Folder - custom category

📷 <b>File Management:</b>
• <b>Photos</b> - send multiple at once
• <b>Videos</b> - all formats (up to 2 GB via Telegram)
• <b>Documents</b> - PDF, Word, Excel
• <b>Text</b> - auto-converted to PDF

🎯 <b>Tips:</b>
• Group photos by vehicle zones
• Use text notes for comments
• Create custom folders
• Choose appropriate disk for different project types

🔗 <b>Share project:</b>
After finishing work with project, use "🔗 Get link" button to get public link for sharing with other users.

📞 <b>Support:</b>
@GOSNOMER_AI | +7 9871370894
        """,
        "support": "📞 Support\n\n💬 Telegram: @GOSNOMER_AI\n📱 Phone: +7 9871370894\n🕒 24/7",
        "back": "🔙 Back",
        "support_btn": "📞 Support",
        "instruction_btn": "📋 Guide",
        "language_btn": "🌐 Language",
        "disk_btn": "📁 Change disk",
        "link_btn": "🔗 Get link",
        "text_input": "📝 Enter text to save as PDF:\n\nText will be automatically converted to PDF and saved in current category.",
        "text_saved": "✅ Text saved as PDF!",
        "brief_conclusion": "📝 Write brief conclusion about vehicle technical condition:\n\n• General condition\n• Main problems\n• Recommendations\n• Final assessment",
        "brief_saved": "✅ Brief conclusion saved as PDF!",
        "custom_folder": "📝 Enter name for new folder:",
        "folder_created": "✅ Folder '{folder_name}' created!",
        "photo_uploaded": "✅ Uploaded {count} photos to '{category}'",
        "video_uploaded": "✅ Video saved to '{category}'",
        "document_uploaded": "✅ Document '{filename}' saved to '{category}'",
        "error_no_project": "❌ First create project via /start",
        "error_no_category": "❌ First select project and category",
        "error_upload": "❌ Error uploading file",
        "error_project": "❌ Error creating project. Please try again.",
        "error_general": "❌ An error occurred. Please try again.",
        "error_no_disk": "❌ First select Yandex.Disk",
        "access_denied": "❌ Access denied",
        "getting_link": "🔄 Getting public link to project...",
        "link_created": "🔗 <b>Public project link:</b>\n\n{link}\n\n📁 <b>Project:</b> {project_name}\n⏰ <b>Link valid:</b> 6 months\n⚠️ <b>Warning:</b> All files in folder will be accessible via this link",
        "link_error": "❌ Failed to get public link. Please try later.",
        "photo_ready": "📸 Now you can send photos. They will be automatically saved in current category.",
        "video_ready": "🎥 Now you can send video files. They will be automatically saved in current category.",
        "document_ready": "📄 Now you can send documents (PDF, Word, Excel and others). They will be automatically saved in current category.",
        "text_ready": "📝 Now you can enter text to save as PDF. Text will be automatically converted and saved in current category.",
        # ОБНОВЛЕНО: Заменен на Litterbox
        "video_upload_choice": "🎥 <b>Choose video upload method:</b>\n\n• <b>📤 Upload via Telegram</b> - for videos up to 2 GB\n• <b>🔗 Upload via Litterbox link</b> - for larger videos",
        "upload_via_telegram": "📤 Upload via Telegram",
        "upload_via_link": "🔗 Upload via link",
        "video_too_big": """
📹 Video file is too large for uploading via Telegram.

🔗 Please upload your video to Litterbox and send me the download link.

📝 <b>Instructions for Litterbox:</b>

1. Go to https://litterbox.catbox.moe
2. Click "Choose File" and select your video
3. Click "Upload"
4. Wait for the upload to complete
5. Copy the download link and send it to me

⚠️ <b>The link should look like:</b> 
• https://files.catbox.moe/abc123.mp4
• https://litter.catbox.moe/abc123.mp4
• https://litterbox.catbox.moe/abc123.mp4
        """,
        "video_link_instruction": """
🔗 <b>Upload video via Litterbox link</b>

📝 <b>Instructions for Litterbox:</b>

1. Go to https://litterbox.catbox.moe
2. Click "Choose File" and select your video
3. Click "Upload"
4. Wait for the upload to complete
5. Copy the download link and send it to me

⚠️ <b>The link can look like:</b>
• https://files.catbox.moe/abc123.mp4
• https://litter.catbox.moe/abc123.mp4
• https://litterbox.catbox.moe/abc123.mp4
        """,
        "downloading_video": "🔄 Downloading video from your link...",
        "video_download_success": "✅ Video successfully uploaded to Yandex.Disk!",
        "video_download_error": "❌ Could not download video from the provided link. Check the link and try again.",
        "invalid_url": "❌ This doesn't look like a valid Litterbox link. Please send a link in one of these formats:\n• https://files.catbox.moe/abc123.mp4\n• https://litter.catbox.moe/abc123.mp4\n• https://litterbox.catbox.moe/abc123.mp4",
        "service_unavailable": "❌ Litterbox is temporarily unavailable. Try uploading via Telegram.",
        "file_too_large": "❌ File is too large.",
        # ОБНОВЛЕНО: Инструкция для Litterbox
        "litterbox_upload_instruction": """
📤 <b>Upload to Litterbox</b>

1. Go to https://litterbox.catbox.moe
2. Click "Choose File" and select your video
3. Click "Upload"
4. Wait for upload to complete (may take several minutes for large files)
5. Copy the download link
6. Send me this link

⚠️ <b>The link should look like:</b> 
• https://files.catbox.moe/abc123.mp4
• https://litter.catbox.moe/abc123.mp4
• https://litterbox.catbox.moe/abc123.mp4

💡 <b>Litterbox features:</b>
• Maximum file size: 1 GB
• Files stored for 24 hours
• No registration required
• Fast uploads
• Direct download links
        """
    }
}

# Состояния FSM
class Form(StatesGroup):
    waiting_language = State()
    waiting_disk_selection = State()
    waiting_project_name = State()
    waiting_custom_folder = State()
    waiting_brief_conclusion = State()
    waiting_text_input = State()
    waiting_video_link = State()

# Путь для временных файлов
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# Пул потоков для асинхронных операций с Яндекс.Диском
thread_pool = ThreadPoolExecutor(max_workers=10)

# Разрешенные пользователи
allowed_users = [1366036245, 6638394042, 1171178308,883570655,7555275027,1171178308,1367582466,883570655,1428448179, 502782112]

# Словари для хранения информации
user_files = {}
user_sessions = {}
user_languages = {}
user_disks = {}
user_analytics = {}
user_projects = {}

def check_access(user_id: int) -> bool:
    """Проверка доступа пользователя"""
    return user_id in allowed_users

def create_language_keyboard():
    """Клавиатура для выбора языка"""
    buttons = [
        [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇺🇸 English")],
        [KeyboardButton(text="🇰🇿 Қазақ")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def create_disk_keyboard():
    """Клавиатура для выбора Яндекс.Диска"""
    buttons = []
    for disk_id, disk_info in YANDEX_DISKS.items():
        buttons.append([KeyboardButton(text=disk_info["name"])])
    buttons.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def create_main_keyboard(language="ru"):
    """Создание основной клавиатуры с учетом языка"""
    texts = MULTILANGUAGE_TEXTS.get(language, MULTILANGUAGE_TEXTS["ru"])

    buttons = [
        [KeyboardButton(text="🚀 Start"), KeyboardButton(text=texts["support_btn"])],
        [KeyboardButton(text=category) for category in list(CATEGORIES.keys())[:4]],
        [KeyboardButton(text=category) for category in list(CATEGORIES.keys())[4:8]],
        [KeyboardButton(text=category) for category in list(CATEGORIES.keys())[8:]],
        [KeyboardButton(text=texts["instruction_btn"]), KeyboardButton(text=texts["link_btn"])],
        [KeyboardButton(text=texts["language_btn"]), KeyboardButton(text=texts["disk_btn"])]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def create_file_keyboard(language="ru"):
    """Клавиатура для управления файлами"""
    texts = MULTILANGUAGE_TEXTS.get(language, MULTILANGUAGE_TEXTS["ru"])

    buttons = [
        [KeyboardButton(text="📸 Фото"), KeyboardButton(text="🎥 Видео")],
        [KeyboardButton(text="📄 Документы"), KeyboardButton(text="📝 Текст")],
        [KeyboardButton(text=texts["back"]), KeyboardButton(text="🚀 Start")],
        [KeyboardButton(text=texts["language_btn"]), KeyboardButton(text=texts["disk_btn"])]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def create_video_choice_keyboard(language="ru"):
    """Клавиатура для выбора способа загрузки видео"""
    texts = MULTILANGUAGE_TEXTS.get(language, MULTILANGUAGE_TEXTS["ru"])
    
    buttons = [
        [KeyboardButton(text=texts["upload_via_telegram"])],
        [KeyboardButton(text=texts["upload_via_link"])],
        [KeyboardButton(text=texts["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def track_user_action(user_id: int, action: str, details: str = ""):
    """Отслеживание действий пользователя"""
    if user_id not in user_analytics:
        user_analytics[user_id] = {
            'first_seen': datetime.now(),
            'language': 'ru',
            'disk': 'main',
            'actions': [],
            'projects_created': 0,
            'files_uploaded': 0,
            'last_activity': datetime.now()
        }

    user_analytics[user_id]['actions'].append({
        'timestamp': datetime.now(),
        'action': action,
        'details': details
    })

    user_analytics[user_id]['last_activity'] = datetime.now()

    if action == "project_created":
        user_analytics[user_id]['projects_created'] += 1
    elif action in ["photo_uploaded", "video_uploaded", "document_uploaded", "text_uploaded"]:
        user_analytics[user_id]['files_uploaded'] += 1
    elif action == "language_selected":
        user_analytics[user_id]['language'] = details
    elif action == "disk_selected":
        user_analytics[user_id]['disk'] = details

async def ensure_project_folders(user_id: int, project_path: str):
    """Создание папок проекта на выбранном Яндекс.Диске"""
    try:
        disk_id = user_disks.get(user_id, "main")
        y = y_disks.get(disk_id)

        if not y:
            return False

        logger.info(f"Попытка создания папки проекта: {project_path} на диске {disk_id}")

        # Создаем основную папку проекта
        if not await run_in_thread(y.exists, project_path):
            await run_in_thread(y.mkdir, project_path)
            logger.info(f"Создана папка проекта: {project_path} на диске {disk_id}")
        else:
            logger.info(f"Папка проекта уже существует: {project_path} на диске {disk_id}")

        # Создаем подпапки для категорий в правильном порядке
        for category_name, folder_name in CATEGORIES.items():
            if folder_name not in ["10. Создать папку", "9. Краткий вывод"]:
                category_path = f"{project_path}/{folder_name}"
                if not await run_in_thread(y.exists, category_path):
                    await run_in_thread(y.mkdir, category_path)
                    logger.info(f"Создана папка категории: {category_path} на диске {disk_id}")

        # Создаем папку для кратких выводов отдельно
        brief_conclusion_path = f"{project_path}/9. Краткий вывод"
        if not await run_in_thread(y.exists, brief_conclusion_path):
            await run_in_thread(y.mkdir, brief_conclusion_path)
            logger.info(f"Создана папка для выводов: {brief_conclusion_path} на диске {disk_id}")

        return True
    except Exception as e:
        logger.error(f"Ошибка создания папок проекта на диске {disk_id}: {e}")
        return False

async def run_in_thread(func, *args, **kwargs):
    """Запуск синхронной функции в отдельном потоке"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, lambda: func(*args, **kwargs))

async def get_public_link(user_id: int, project_path: str):
    """Получение публичной ссылки на проект"""
    try:
        disk_id = user_disks.get(user_id, "main")
        y = y_disks.get(disk_id)

        if not y:
            return None

        # Публикуем папку
        await run_in_thread(y.publish, project_path)

        # Получаем информацию о папке
        resource = await run_in_thread(y.get_meta, project_path)

        if hasattr(resource, 'public_url') and resource.public_url:
            return resource.public_url
        else:
            try:
                download_url = await run_in_thread(y.get_download_link, project_path)
                return download_url
            except:
                return None

    except Exception as e:
        logger.error(f"Ошибка получения публичной ссылки: {e}")
        return None

async def save_photo_batch_async(photos_batch: List[Dict], user_id: int, category: str):
    """Асинхронное сохранение пакета фотографий на Яндекс.Диск"""
    try:
        disk_id = user_disks.get(user_id, "main")
        y = y_disks.get(disk_id)

        if not y:
            return False

        uploaded_files = []

        for photo_data in photos_batch:
            file_content = photo_data['file_content']
            remote_path = photo_data['remote_path']
            filename = photo_data['filename']

            file_like_object = io.BytesIO(file_content)
            await run_in_thread(y.upload, file_like_object, remote_path)

            if user_id not in user_files:
                user_files[user_id] = {}

            file_uuid = str(uuid.uuid4())
            user_files[user_id][file_uuid] = {
                'remote_path': remote_path,
                'filename': filename,
                'category': category,
                'disk_id': disk_id,
                'upload_time': datetime.now()
            }

            uploaded_files.append({
                'file_uuid': file_uuid,
                'filename': filename
            })

        await track_user_action(user_id, "photo_uploaded", f"{len(uploaded_files)} photos to {category} on {disk_id}")

        return True

    except Exception as e:
        logger.error(f"Ошибка сохранения пакета фото на Яндекс.Диск: {e}")
        lang = user_languages.get(user_id, "ru")
        texts = MULTILANGUAGE_TEXTS[lang]

        await bot.send_message(
            user_id,
            f"❌ {texts['error_upload']}: {str(e)}"
        )
        return False

async def save_to_yandex(user_id: int, file_content: bytes, remote_path: str) -> bool:
    """Сохранение файла на выбранный Яндекс.Диск"""
    try:
        disk_id = user_disks.get(user_id, "main")
        y = y_disks.get(disk_id)

        if not y:
            return False

        file_like_object = io.BytesIO(file_content)
        await run_in_thread(y.upload, file_like_object, remote_path)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения на Яндекс.Диск {disk_id}: {e}")
        return False

async def save_pdf_to_yandex(user_id: int, pdf_content: bytes, remote_path: str):
    """Сохранение PDF файла на выбранный Яндекс.Диск"""
    try:
        disk_id = user_disks.get(user_id, "main")
        y = y_disks.get(disk_id)

        if not y:
            return False

        file_like_object = io.BytesIO(pdf_content)
        await run_in_thread(y.upload, file_like_object, remote_path)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения PDF на Яндекс.Диск {disk_id}: {e}")
        return False

def create_pdf_from_text(text: str, title: str = "Текстовый документ") -> bytes:
    """Создание PDF файла из текста с логотипом компании"""
    temp_filename = None
    try:
        if not os.path.exists(LOGO_PATH):
            raise FileNotFoundError(f"Логотип не найден по пути: {LOGO_PATH}")

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_filename = temp_file.name

        c = canvas.Canvas(temp_filename, pagesize=A4)
        width, height = A4

        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/verdana.ttf",
            "C:/Windows/Fonts/times.ttf",
        ]

        font_name = "Helvetica"
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font_base_name = os.path.splitext(os.path.basename(font_path))[0]
                    pdfmetrics.registerFont(TTFont(font_base_name, font_path))
                    font_name = font_base_name
                    break
                except:
                    continue

        logo_width = 80
        logo_height = 22

        logo_x = width - logo_width - 50
        logo_y = height - logo_height - 40

        c.drawImage(LOGO_PATH, logo_x, logo_y,
                    width=logo_width, height=logo_height,
                    preserveAspectRatio=True, mask='auto')

        c.setFont(font_name, 10)
        c.setFillColor(colors.darkblue)
        slogan = "#Пацаныработаютлюдивкурсе!"
        c.drawString(50, height - 40, slogan)
        c.setFillColor(colors.black)

        c.setFont(font_name, 14)
        c.drawString(50, height - 80, title)
        c.line(50, height - 90, width - 50, height - 90)

        c.setFont(font_name, 10)
        c.drawString(50, height - 110, f"Создано: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        c.setFont(font_name, 10)
        y_position = height - 140
        line_height = 15

        paragraphs = text.split('\n')

        for paragraph in paragraphs:
            if paragraph.strip():
                lines = textwrap.wrap(paragraph, width=80)
                for line in lines:
                    if y_position < 50:
                        c.showPage()
                        c.setFont(font_name, 10)
                        c.drawImage(LOGO_PATH, logo_x, logo_y,
                                    width=logo_width, height=logo_height,
                                    preserveAspectRatio=True, mask='auto')
                        c.setFont(font_name, 10)
                        c.setFillColor(colors.darkblue)
                        c.drawString(50, height - 40, slogan)
                        c.setFillColor(colors.black)
                        y_position = height - 70
                    c.drawString(50, y_position, line)
                    y_position -= line_height
                y_position -= line_height / 2

        c.save()

        with open(temp_filename, 'rb') as f:
            pdf_bytes = f.read()

        return pdf_bytes

    except Exception as e:
        logger.error(f"Ошибка создания PDF: {e}")
        raise
    finally:
        if temp_filename and os.path.exists(temp_filename):
            os.unlink(temp_filename)

async def process_user_session(user_id: int):
    """Обработка сессии пользователя - загрузка собранных фотографий"""
    if user_id not in user_sessions:
        return

    session = user_sessions[user_id]

    await asyncio.sleep(2)

    if not session['photos']:
        return

    photos_to_process = session['photos'].copy()
    session['photos'].clear()

    asyncio.create_task(
        save_photo_batch_async(
            photos_to_process,
            user_id,
            session['category']
        )
    )

async def send_welcome_message(user_id: int, username: str = "", language: str = "ru"):
    """Отправка приветственного сообщения"""
    welcome_texts = {
        "ru": f"""
👋 Добро пожаловать, {username if username else 'друг'}!

🤖 <b>AutoCheckAssistent_PRO</b> - профессиональный помощник для проверки автомобилей.

🎯 <b>Новые возможности:</b>
• <b>Выбор Яндекс.Диска</b> - работайте с несколькими дисками
• <b>Публичные ссылки</b> - делитесь проектами с другими
• Основной диск - для текущих проектов
• Резервный диск - для важных данных  
• Архивный диск - для долгосрочного хранения

🚀 <b>Чтобы начать:</b>
1. Выберите язык
2. Выберите Яндекс.Диск
3. Создайте проект

💡 <b>Совет:</b> Используйте кнопку "🔗 Получить ссылку" для передачи проекта другим пользователям

📞 <b>Поддержка:</b> @GOSNOMER_AI
        """,
        "en": f"""
👋 Welcome, {username if username else 'friend'}!

🤖 <b>AutoCheckAssistent_PRO</b> - professional car inspection assistant.

🎯 <b>New features:</b>
• <b>Yandex.Disk selection</b> - work with multiple disks
• <b>Public links</b> - share projects with others
• Main disk - for current projects
• Backup disk - for important data
• Archive disk - for long-term storage

🚀 <b>To start:</b>
1. Choose language
2. Select Yandex.Disk
3. Create project

💡 <b>Tip:</b> Use "🔗 Get link" button to share project with other users

📞 <b>Support:</b> @GOSNOMER_AI
        """
    }

    await bot.send_message(user_id, welcome_texts[language], parse_mode="HTML")

async def download_video_from_url(url: str, max_size: int = 2 * 1024 * 1024 * 1024) -> str:
    """
    Скачивает видео по URL и сохраняет во временный файл
    max_size: максимальный размер файла в байтах (по умолчанию 2 ГБ)
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://litterbox.catbox.moe/'
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")

                # Проверяем размер контента
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > max_size:
                    raise Exception(f"Файл слишком большой: {content_length} байт")

                # Скачиваем файл
                downloaded_size = 0
                with open(temp_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(8192):
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size:
                            raise Exception(f"Файл превышает максимальный размер {max_size} байт")
                        file.write(chunk)

                # Проверяем, что файл не пустой
                if downloaded_size == 0:
                    raise Exception("Файл пустой или не был загружен")

                return temp_path

    except Exception as e:
        # Удаляем временный файл в случае ошибки
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise e

# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========

@router.message(Command("start"))
@router.message(F.text == "🚀 Start")
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start и кнопки Start"""
    if not check_access(message.from_user.id):
        await message.answer("❌ Access denied / Доступ запрещен")
        return

    user_id = message.from_user.id

    if user_id in user_sessions:
        del user_sessions[user_id]

    await state.clear()

    await send_welcome_message(user_id, message.from_user.username, "ru")

    await message.answer(
        "🌍 <b>AutoCheckAssistent_PRO - International</b>\n\n"
        "Please choose your language / Пожалуйста, выберите язык:",
        parse_mode="HTML",
        reply_markup=create_language_keyboard()
    )

    await state.set_state(Form.waiting_language)
    await track_user_action(user_id, "started")

@router.message(Form.waiting_language)
@router.message(F.text.in_(["🇷🇺 Русский", "🇺🇸 English", "🇰🇿 Қазақ"]))
async def language_handler(message: Message, state: FSMContext):
    """Обработка выбора языка"""
    user_id = message.from_user.id
    language_map = {
        "🇷🇺 Русский": "ru",
        "🇺🇸 English": "en",
        "🇰🇿 Қазақ": "kz"
    }

    selected_language = language_map[message.text]
    user_languages[user_id] = selected_language

    texts = MULTILANGUAGE_TEXTS[selected_language]

    await message.answer(
        texts["choose_disk"],
        reply_markup=create_disk_keyboard()
    )
    await state.set_state(Form.waiting_disk_selection)

    await track_user_action(user_id, "language_selected", selected_language)

@router.message(Form.waiting_disk_selection)
async def disk_selection_handler(message: Message, state: FSMContext):
    """Обработка выбора Яндекс.Диска"""
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    selected_disk_id = None
    for disk_id, disk_info in YANDEX_DISKS.items():
        if message.text == disk_info["name"]:
            selected_disk_id = disk_id
            break

    if selected_disk_id:
        user_disks[user_id] = selected_disk_id
        disk_name = YANDEX_DISKS[selected_disk_id]["name"]

        await message.answer(
            texts["disk_selected"].format(disk_name=disk_name),
            reply_markup=create_main_keyboard(lang)
        )

        await message.answer(
            texts["start_project"],
            reply_markup=create_main_keyboard(lang)
        )
        await state.set_state(Form.waiting_project_name)

        await track_user_action(user_id, "disk_selected", selected_disk_id)
    elif message.text == "🔙 Назад":
        await message.answer(
            texts["choose_language"],
            reply_markup=create_language_keyboard()
        )
        await state.set_state(Form.waiting_language)
    else:
        await message.answer(
            "❌ Пожалуйста, выберите диск из предложенных вариантов",
            reply_markup=create_disk_keyboard()
        )

@router.message(F.text.in_(["📁 Сменить диск", "📁 Change disk", "📁 Дискіні өзгерту"]))
async def change_disk_handler(message: Message, state: FSMContext):
    """Смена Яндекс.Диска"""
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    await message.answer(
        texts["choose_disk"],
        reply_markup=create_disk_keyboard()
    )
    await state.set_state(Form.waiting_disk_selection)

@router.message(F.text.in_(["🔗 Получить ссылку", "🔗 Get link", "🔗 Сілтеме алу"]))
async def get_project_link(message: Message, state: FSMContext):
    """Получение публичной ссылки на проект"""
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    user_data = await state.get_data()
    current_project = user_data.get('current_project')
    project_name = user_data.get('project_name', 'Неизвестный проект')

    if not current_project:
        await message.answer(texts["error_no_project"])
        return

    if user_id not in user_projects:
        user_projects[user_id] = {}

    user_projects[user_id][project_name] = {
        'path': current_project,
        'disk_id': user_disks.get(user_id, "main"),
        'created_at': datetime.now()
    }

    await message.answer(texts["getting_link"])

    public_link = await get_public_link(user_id, current_project)

    if public_link:
        await message.answer(
            texts["link_created"].format(link=public_link, project_name=project_name),
            parse_mode="HTML"
        )
        await track_user_action(user_id, "link_created", project_name)
    else:
        await message.answer(texts["link_error"])

@router.message(F.text.in_(["📞 Поддержка", "📞 Support", "📞 Қолдау"]))
async def support_handler(message: Message):
    """Обработка кнопки Поддержка"""
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]
    await message.answer(texts["support"])

@router.message(F.text.in_(["📋 Инструкция", "📋 Guide", "📋 Нұсқаулық"]))
async def instruction_handler(message: Message):
    """Обработка кнопки Инструкция"""
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]
    await message.answer(texts["instruction"], parse_mode="HTML")

@router.message(F.text.in_(["🌐 Язык", "🌐 Language", "🌐 Тіл"]))
async def change_language_handler(message: Message, state: FSMContext):
    """Смена языка"""
    await message.answer(
        "🌍 Choose your language / Выберите язык:",
        reply_markup=create_language_keyboard()
    )
    await state.set_state(Form.waiting_language)

@router.message(F.text == "🔙 Назад")
@router.message(F.text == "🔙 Back")
@router.message(F.text == "🔙 Артқа")
async def back_handler(message: Message, state: FSMContext):
    """Обработка кнопки Назад"""
    current_state = await state.get_state()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    if current_state == Form.waiting_project_name:
        await message.answer("Вы уже в начале работы с ботом")
        return
    elif current_state in [Form.waiting_custom_folder, Form.waiting_brief_conclusion, Form.waiting_text_input,
                           Form.waiting_video_link]:
        await state.set_state(None)
        await message.answer("Возврат в главное меню", reply_markup=create_main_keyboard(lang))
    else:
        await state.set_state(None)
        await message.answer("Главное меню", reply_markup=create_main_keyboard(lang))

@router.message(Form.waiting_project_name)
async def process_project_name(message: Message, state: FSMContext):
    """Обработка названия проекта"""
    project_name = message.text.strip()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    if user_id not in user_disks:
        texts = MULTILANGUAGE_TEXTS[lang]
        await message.answer(texts["error_no_disk"])
        return

    safe_project_name = project_name
    project_path = f"/{safe_project_name}"

    disk_id = user_disks[user_id]
    disk_name = YANDEX_DISKS[disk_id]["name"]

    logger.info(f"Создание проекта: {project_name} на диске {disk_id}")

    if await ensure_project_folders(user_id, project_path):
        await state.update_data(
            current_project=project_path,
            project_name=project_name,
            safe_project_name=safe_project_name
        )
        await state.set_state(None)

        texts = MULTILANGUAGE_TEXTS[lang]
        await message.answer(
            texts["project_created"].format(project_name=project_name, disk_name=disk_name),
            reply_markup=create_main_keyboard(lang)
        )

        if user_id not in user_projects:
            user_projects[user_id] = {}

        user_projects[user_id][project_name] = {
            'path': project_path,
            'disk_id': disk_id,
            'created_at': datetime.now()
        }

        await track_user_action(user_id, "project_created", f"{project_name} on {disk_id}")
    else:
        texts = MULTILANGUAGE_TEXTS[lang]
        await message.answer(
            texts["error_project"],
            reply_markup=create_main_keyboard(lang)
        )

@router.message(F.text == "10. Создать папку")
async def create_custom_folder_handler(message: Message, state: FSMContext):
    """Обработка создания пользовательской папки"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    if not user_data.get('current_project'):
        await message.answer(texts["error_no_project"])
        return

    await state.set_state(Form.waiting_custom_folder)
    await message.answer(texts["custom_folder"])

@router.message(F.text == "9. Краткий вывод")
async def brief_conclusion_handler(message: Message, state: FSMContext):
    """Обработка краткого вывода"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    if not user_data.get('current_project'):
        await message.answer(texts["error_no_project"])
        return

    await state.set_state(Form.waiting_brief_conclusion)
    await message.answer(texts["brief_conclusion"])

@router.message(Form.waiting_custom_folder)
async def process_custom_folder(message: Message, state: FSMContext):
    """Обработка названия пользовательской папки"""
    folder_name = message.text.strip()
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    project_path = user_data['current_project']

    safe_folder_name = folder_name
    folder_path = f"{project_path}/{safe_folder_name}"

    try:
        disk_id = user_disks.get(user_id, "main")
        y = y_disks.get(disk_id)

        if not y:
            await message.answer(texts["error_general"])
            return

        if not await run_in_thread(y.exists, folder_path):
            await run_in_thread(y.mkdir, folder_path)
            logger.info(f"Создана пользовательская папка: {folder_path}")

        await state.update_data(current_category=safe_folder_name)
        await state.set_state(None)

        disk_name = YANDEX_DISKS[disk_id]["name"]
        await message.answer(
            f"{texts['folder_created'].format(folder_name=folder_name)}\n📁 Диск: {disk_name}",
            reply_markup=create_main_keyboard(lang)
        )

        await track_user_action(user_id, "custom_folder_created", folder_name)
    except Exception as e:
        logger.error(f"Ошибка создания папки: {e}")
        await message.answer(texts["error_general"])

@router.message(Form.waiting_brief_conclusion)
async def process_brief_conclusion(message: Message, state: FSMContext):
    """Обработка текста краткого вывода с созданием PDF"""
    conclusion_text = message.text
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    project_path = user_data['current_project']
    project_name = user_data.get('project_name', 'Неизвестный проект')

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"краткий_вывод_{timestamp}.pdf"
    remote_path = f"{project_path}/9. Краткий вывод/{pdf_filename}"

    try:
        pdf_content = create_pdf_from_text(conclusion_text, project_name)

        if await save_pdf_to_yandex(user_id, pdf_content, remote_path):
            disk_id = user_disks[user_id]
            disk_name = YANDEX_DISKS[disk_id]["name"]

            await state.set_state(None)
            await message.answer(
                f"{texts['brief_saved']}\n📁 Диск: {disk_name}",
                reply_markup=create_main_keyboard(lang)
            )
            await track_user_action(user_id, "brief_report_created", project_name)
        else:
            await message.answer(texts["error_upload"])

    except Exception as e:
        await message.answer(texts["error_general"])
        logger.error(f"Ошибка создания PDF: {e}")

@router.message(F.text.in_(CATEGORIES.keys()))
async def category_selection_handler(message: Message, state: FSMContext):
    """Обработка выбора категории"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    if not user_data.get('current_project'):
        await message.answer(texts["error_no_project"])
        return

    if user_id not in user_disks:
        await message.answer(texts["error_no_disk"])
        return

    category_text = message.text
    category_key = CATEGORIES[category_text]

    await state.update_data(current_category=category_key)

    user_sessions[user_id] = {
        'category': category_key,
        'project': user_data['current_project'],
        'photos': [],
        'last_activity': datetime.now()
    }

    if category_key == "9. Краткий вывод":
        await brief_conclusion_handler(message, state)
    elif category_key == "10. Создать папку":
        await create_custom_folder_handler(message, state)
    else:
        disk_id = user_disks[user_id]
        disk_name = YANDEX_DISKS[disk_id]["name"]

        await message.answer(
            f"{texts['category_selected'].format(category=category_text)}\n📁 Диск: {disk_name}",
            reply_markup=create_file_keyboard(lang)
        )

# ========== ОБРАБОТЧИКИ КНОПОК УПРАВЛЕНИЯ ФАЙЛАМИ ==========

@router.message(F.text.in_(["📸 Фото", "📸 Photo", "📸 Фотосурет"]))
async def photo_button_handler(message: Message, state: FSMContext):
    """Обработка нажатия кнопки Фото"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    await message.answer(
        texts["photo_ready"],
        reply_markup=create_file_keyboard(lang)
    )
    await track_user_action(user_id, "photo_button_clicked", current_category)

@router.message(F.text.in_(["🎥 Видео", "🎥 Video", "🎥 Бейне"]))
async def video_button_handler(message: Message, state: FSMContext):
    """Обработка нажатия кнопки Видео"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    await message.answer(
        texts["video_upload_choice"],
        parse_mode="HTML",
        reply_markup=create_video_choice_keyboard(lang)
    )
    await track_user_action(user_id, "video_button_clicked", current_category)

@router.message(F.text.in_(["📤 Загрузить через Telegram", "📤 Upload via Telegram", "📤 Telegram арқылы жүктеу"]))
async def video_telegram_handler(message: Message, state: FSMContext):
    """Обработка выбора загрузки видео через Telegram"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    await message.answer(
        texts["video_ready"],
        reply_markup=create_file_keyboard(lang)
    )
    await track_user_action(user_id, "video_telegram_chosen", current_category)

@router.message(F.text.in_(["🔗 Загрузить по ссылке", "🔗 Upload via link", "🔗 Сілтеме бойынша жүктеу"]))
async def video_link_handler(message: Message, state: FSMContext):
    """Обработка выбора загрузки видео по ссылке"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    await message.answer(
        texts["video_link_instruction"],
        parse_mode="HTML",
        reply_markup=create_file_keyboard(lang)
    )
    
    await state.set_state(Form.waiting_video_link)
    await track_user_action(user_id, "video_link_chosen", current_category)

@router.message(F.text.in_(["📄 Документы", "📄 Documents", "📄 Құжаттар"]))
async def document_button_handler(message: Message, state: FSMContext):
    """Обработка нажатия кнопки Документы"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    await message.answer(
        texts["document_ready"],
        reply_markup=create_file_keyboard(lang)
    )
    await track_user_action(user_id, "document_button_clicked", current_category)

@router.message(F.text.in_(["📝 Текст", "📝 Text", "📝 Мәтін"]))
async def text_button_handler(message: Message, state: FSMContext):
    """Обработка нажатия кнопки Текст"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    await state.set_state(Form.waiting_text_input)
    await message.answer(
        texts["text_input"],
        reply_markup=create_file_keyboard(lang)
    )
    await track_user_action(user_id, "text_button_clicked", current_category)

@router.message(Form.waiting_text_input)
async def process_text_input(message: Message, state: FSMContext):
    """Обработка текстового ввода с созданием PDF"""
    text = message.text
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')
    project_name = user_data.get('project_name', 'Текстовый документ')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"текст_{timestamp}.pdf"
    remote_path = f"{current_project}/{current_category}/{pdf_filename}"

    try:
        pdf_content = create_pdf_from_text(text, project_name)

        if await save_pdf_to_yandex(user_id, pdf_content, remote_path):
            disk_id = user_disks.get(user_id, "main")
            disk_name = YANDEX_DISKS[disk_id]["name"]

            await state.set_state(None)
            await message.answer(
                f"{texts['text_saved']}\n📁 Диск: {disk_name}",
                reply_markup=create_main_keyboard(lang)
            )
            await track_user_action(user_id, "text_uploaded", f"PDF to {current_category}")
        else:
            await message.answer(texts["error_upload"])

    except Exception as e:
        await message.answer(texts["error_general"])
        logger.error(f"Ошибка создания PDF из текста: {e}")

@router.message(F.photo)
async def handle_photos(message: Message, state: FSMContext):
    """Обработка фотографий с группировкой в альбом"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    if user_id not in user_disks:
        await message.answer(texts["error_no_disk"])
        return

    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'category': current_category,
            'project': current_project,
            'photos': [],
            'last_activity': datetime.now()
        }

    try:
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await bot.get_file(file_id)
        file_content = await bot.download_file(file.file_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
        remote_path = f"{current_project}/{current_category}/{filename}"

        user_sessions[user_id]['photos'].append({
            'file_content': file_content.read(),
            'remote_path': remote_path,
            'filename': filename,
            'category': current_category
        })

        user_sessions[user_id]['last_activity'] = datetime.now()

        asyncio.create_task(process_user_session(user_id))

    except Exception as e:
        await message.answer(texts["error_upload"])
        logger.error(f"Ошибка обработки фото: {e}")

@router.message(F.document)
async def handle_documents(message: Message, state: FSMContext):
    """Обработка документов (PDF, Word, Excel и т.д.)"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    if user_id not in user_disks:
        await message.answer(texts["error_no_disk"])
        return

    try:
        document = message.document
        file_id = document.file_id
        file = await bot.get_file(file_id)
        file_content = await bot.download_file(file.file_path)

        if document.file_name:
            file_extension = document.file_name.split('.')[-1].lower()
            if file_extension in ['jpg', 'jpeg', 'png', 'heic', 'heif', 'webp']:
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{file_extension}"
            else:
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
        else:
            mime_type = document.mime_type or ''
            if 'image' in mime_type:
                if 'jpeg' in mime_type or 'jpg' in mime_type:
                    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
                elif 'png' in mime_type:
                    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.png"
                elif 'heic' in mime_type:
                    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.heic"
                else:
                    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
            else:
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.file"

        remote_path = f"{current_project}/{current_category}/{filename}"

        if await save_to_yandex(user_id, file_content.read(), remote_path):
            disk_id = user_disks[user_id]

            file_type = "документ"
            if 'image' in (document.mime_type or ''):
                file_type = "фото (оригинальное качество)"

            await track_user_action(user_id, "document_uploaded", f"{file_type} to {current_category} on {disk_id}")
        else:
            await message.answer(texts["error_upload"])

    except Exception as e:
        await message.answer(texts["error_upload"])
        logger.error(f"Ошибка обработки файла: {e}")

@router.message(F.video)
async def handle_videos(message: Message, state: FSMContext):
    """Обработка видео через Telegram"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        return

    if user_id not in user_disks:
        await message.answer(texts["error_no_disk"])
        return

    try:
        video = message.video
        file_id = video.file_id
        file = await bot.get_file(file_id)
        
        # Проверяем размер файла
        file_size = video.file_size or 0
        
        # Если файл больше 2 ГБ, предлагаем альтернативы
        if file_size > 2 * 1024 * 1024 * 1024:
            await message.answer(
                texts["video_too_big"],
                parse_mode="HTML",
                reply_markup=create_video_choice_keyboard(lang)
            )
            return

        await message.answer(texts["downloading_video"])
        
        file_content = await bot.download_file(file.file_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.mp4"
        remote_path = f"{current_project}/{current_category}/{filename}"

        if await save_to_yandex(user_id, file_content.read(), remote_path):
            disk_id = user_disks[user_id]

            await track_user_action(user_id, "video_uploaded", f"video to {current_category} on {disk_id}")
            await message.answer(
                f"✅ {texts['video_download_success']}\n"
                f"📁 Категория: {current_category}\n"
                f"📁 Диск: {YANDEX_DISKS[disk_id]['name']}",
                reply_markup=create_main_keyboard(lang)
            )
        else:
            await message.answer(texts["error_upload"])

    except Exception as e:
        if "file is too big" in str(e):
            await message.answer(
                texts["video_too_big"],
                parse_mode="HTML",
                reply_markup=create_video_choice_keyboard(lang)
            )
        else:
            await message.answer(texts["error_upload"])
            logger.error(f"Ошибка обработки видео: {e}")

@router.message(Form.waiting_video_link)
async def handle_video_link(message: Message, state: FSMContext):
    """Обработка ссылки на видео с Litterbox"""
    user_data = await state.get_data()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    texts = MULTILANGUAGE_TEXTS[lang]

    current_project = user_data.get('current_project')
    current_category = user_data.get('current_category')

    if not current_project or not current_category:
        await message.answer(texts["error_no_category"])
        await state.clear()
        return

    video_url = message.text.strip()

    # Более гибкая проверка Litterbox ссылок
    litterbox_patterns = [
        r'^https?://files\.catbox\.moe/',
        r'^https?://litter\.catbox\.moe/',
        r'^https?://litterbox\.catbox\.moe/',
    ]
    
    is_valid_litterbox_url = any(re.match(pattern, video_url) for pattern in litterbox_patterns)
    
    if not is_valid_litterbox_url:
        await message.answer(texts["invalid_url"])
        return

    await message.answer(texts["downloading_video"])

    try:
        # Скачиваем видео напрямую - Litterbox предоставляет прямые ссылки
        temp_video_path = await download_video_from_url(video_url)

        if not temp_video_path:
            await message.answer(texts["video_download_error"])
            return

        # Получаем оригинальное имя файла из URL или создаем временное
        original_filename = os.path.basename(video_url)
        if not original_filename or '.' not in original_filename:
            original_filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}_{original_filename}"
        remote_path = f"{current_project}/{current_category}/{filename}"

        # Читаем файл и загружаем на Яндекс.Диск
        with open(temp_video_path, 'rb') as file:
            file_content = file.read()

        if await save_to_yandex(user_id, file_content, remote_path):
            disk_id = user_disks[user_id]

            await track_user_action(user_id, "video_uploaded", f"video (via Litterbox) to {current_category} on {disk_id}")
            await message.answer(
                f"✅ {texts['video_download_success']}\n"
                f"📁 Категория: {current_category}\n"
                f"📁 Диск: {YANDEX_DISKS[disk_id]['name']}",
                reply_markup=create_main_keyboard(lang)
            )
        else:
            await message.answer(texts["error_upload"])

        # Удаляем временный файл
        if os.path.exists(temp_video_path):
            os.unlink(temp_video_path)

    except aiohttp.ClientError as e:
        logger.error(f"Ошибка сети при скачивании видео: {e}")
        await message.answer(f"❌ {texts['service_unavailable']}")
    except Exception as e:
        logger.error(f"Ошибка обработки видео по ссылке: {e}")
        error_message = str(e).lower()
        if "too large" in error_message or "big" in error_message:
            await message.answer(f"❌ {texts['file_too_large']}")
        else:
            await message.answer(f"❌ {texts['video_download_error']}: {str(e)}")



async def cleanup_sessions():
    """Очистка старых сессий"""
    while True:
        await asyncio.sleep(300)
        current_time = datetime.now()
        expired_sessions = []

        for user_id, session in user_sessions.items():
            if (current_time - session['last_activity']).total_seconds() > 1800:
                expired_sessions.append(user_id)

        for user_id in expired_sessions:
            del user_sessions[user_id]
            logger.info(f"Очищена сессия пользователя {user_id}")

async def cleanup_analytics():
    """Очистка старых аналитических данных"""
    while True:
        await asyncio.sleep(3600)
        current_time = datetime.now()
        expired_users = []

        for user_id, analytics in user_analytics.items():
            if (current_time - analytics['last_activity']).total_seconds() > 604800:
                expired_users.append(user_id)

        for user_id in expired_users:
            del user_analytics[user_id]
            if user_id in user_disks:
                del user_disks[user_id]
            if user_id in user_languages:
                del user_languages[user_id]
            if user_id in user_projects:
                del user_projects[user_id]
            logger.info(f"Очищены данные пользователя {user_id}")

async def main():
    """Основная функция"""
    if not os.path.exists(LOGO_PATH):
        logger.error(f"Логотип не найден по пути: {LOGO_PATH}")
        logger.error("Пожалуйста, поместите файл 'logo.png' в ту же директорию, где находится скрипт бота")
        return

    logger.info(f"Логотип найден: {LOGO_PATH}")
    logger.info("Бот запущен")

    asyncio.create_task(cleanup_sessions())
    asyncio.create_task(cleanup_analytics())

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
    finally:
        thread_pool.shutdown(wait=True)

if __name__ == "__main__":
    asyncio.run(main())