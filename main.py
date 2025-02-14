"""
Telegram Bot для отображения меню "BREMOR".

Бот предоставляет пользователям возможность получить меню на завтрак или обед.
Он использует Inline-кнопки для выбора и отправляет соответствующие файлы .xls,
если они доступны в указанной директории. Также бот логирует все действия
и ошибки в файлы логов.

Основные функции:
- /start: Отправляет пользователю меню с кнопками выбора.
- Завтрак и Обед: При выборе соответствующей кнопки отправляется
  файл с меню (если он существует в директории, указанной в MENU_PATH).
- Логирование: Все действия и ошибки записываются в файл logs/bot.log.

Файлы меню должны быть размещены в директории, указанной в переменной
окружения MENU_PATH (например, в формате /app/venv/bin), и иметь названия:
- breakfast.xls — для завтрака
- lunch.xls — для обеда
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# подгружаю данные из .env
load_dotenv()

# логирование
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)  # если нет папки, то будет

# Отключаем INFO-логи
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.request").setLevel(logging.ERROR)

# Настройка ротации логов
log_handler = TimedRotatingFileHandler(
    f"{LOG_DIR}/bot.log", when="midnight", interval=30, backupCount=3
)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)
log_handler.setLevel(logging.INFO)

# Конфигурируем логирование
logging.basicConfig(
    level=logging.INFO,
    handlers=[log_handler, logging.StreamHandler()]  # Добавляем оба обработчика
)

logger = logging.getLogger(__name__)

# файлы меню
MENU_PATH = os.getenv("MENU_PATH")


# клавиатура
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, query_message=None) -> None:
    """
    Отправляет меню с кнопками "Завтрак" и "Обед" пользователю.

    Args:
        update (Update): Объект обновления от Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст исполнения команды.
        query_message (Optional[Message]): Сообщение, вызвавшее команду. Используется для обновления кнопок.
    """
    keyboard = [
        [
            InlineKeyboardButton("Завтрак", callback_data='breakfast'),
            InlineKeyboardButton("Обед", callback_data='lunch'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if query_message:
            await query_message.reply_text("BREMOR меню:", reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text("BREMOR меню:", reply_markup=reply_markup)
    except NetworkError:
        logger.error("Ошибка сети. NetworkError")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram API: {e}")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка: {e}")


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start и отправляет меню с кнопками пользователю.

    Args:
        update (Update): Объект обновления от Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст исполнения команды.
    """
    logger.info(f"Пользователь с ID {update.effective_user.id} запустил /start.")
    await send_menu(update, context)


# Обработка нажатия кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает нажатие на кнопки меню ("Завтрак" или "Обед").
    Отправляет соответствующий файл пользователю.

    Args:
        update (Update): Объект обновления от Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст исполнения команды.
    """
    query = update.callback_query
    user = update.effective_user
    await query.answer()

    file_map = {
        'breakfast': 'breakfast.xls',
        'lunch': 'lunch.xls'
    }
    file_name = file_map.get(query.data)

    if file_name:
        file_path = os.path.join(MENU_PATH, file_name)
        try:
            if os.path.exists(file_path):
                modification_time = os.path.getmtime(file_path)
                creation_date = datetime.fromtimestamp(modification_time).strftime('%d.%m.%Y %H:%M')
                with open(file_path, 'rb') as file:
                    await query.message.reply_document(
                        document=file,
                        caption=f"От {creation_date}"
                    )
                    logger.info(f"Файл {file_name} отправлен пользователю ID {user.id} {datetime.now()}.")
            else:
                logger.warning(f"Файл {file_name} не найден! (запрос от {user.id})")
                await query.message.reply_text("Файл не найден!")

            await send_menu(update, context, query_message=query.message)
        except NetworkError:
            logger.error("Ошибка сети при отправке документа.")
            await query.message.reply_text("Ошибка сети. Проверьте подключение к интернету.")
        except TelegramError as e:
            logger.error(f"Ошибка Telegram API: {str(e)}")
            await query.message.reply_text(f"Ошибка Telegram API: {e}")
        except Exception as e:
            logger.exception(f"Неизвестная ошибка при отправке документа: {e}")
            await query.message.reply_text(f"Неизвестная ошибка: {e}")
    else:
        logger.warning(
            f"Некорректный callback_data: {query.data} от {user.id}")  # когда несоответствие между названиями и file_map
        await query.message.reply_text("Что-то пошло не так!")


def main():
    """
    Основная точка входа в приложение.
    Инициализирует бота, добавляет обработчики команд и запускает polling.
    """
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        logger.critical("Токен бота отсутствует! Укажите его в переменных окружения.")
        return

    application = Application.builder().token(TOKEN).build()

    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Бот запущен...")

    try:
        application.run_polling()
    except NetworkError:
        logger.error("Ошибка сети при запуске бота. Проверьте подключение к интернету.")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram API при запуске: {e}")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при запуске: {e}")


if __name__ == "__main__":
    main()
