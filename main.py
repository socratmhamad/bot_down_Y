import sys
import logging
import os
import subprocess
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from yt_dlp import YoutubeDL

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("6767447234:AAHODYTwpqlNl0mbeGLK9qAtgKVHfHC0e40")
DOWNLOAD_FOLDER = 'downloads'

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("ffmpeg غير مثبت في النظام. الرجاء تثبيته لتتمكن من تنزيل وتحويل الفيديوهات.")
        return False

HAS_FFMPEG = check_ffmpeg()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("Download Video", callback_data='download_video'),
            InlineKeyboardButton("Convert Video to Audio", callback_data='convert_video_to_audio'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Choose an option:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == 'download_video':
        await query.message.reply_text('Please send me the YouTube link to download the video.')
        context.user_data['action'] = 'download_video'
    elif query.data == 'convert_video_to_audio':
        await query.message.reply_text('Please send me the YouTube link to convert to audio.')
        context.user_data['action'] = 'convert_video_to_audio'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_action = context.user_data.get('action')
    if user_action == 'download_video':
        await update.message.reply_text("ميزة التنزيل لم تُنقل بالكامل إلى النسخة المعدلة بعد.")
    elif user_action == 'convert_video_to_audio':
        await update.message.reply_text("ميزة التحويل لم تُنقل بالكامل إلى النسخة المعدلة بعد.")
    else:
        await update.message.reply_text('Please select an option using the buttons.')

def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
