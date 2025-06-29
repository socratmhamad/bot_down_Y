import os
import subprocess
import logging
from yt_dlp import YoutubeDL
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

# إعداد التسجيل للأخطاء
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = 'YOUR_BOT_TOKEN'
DOWNLOAD_FOLDER = 'downloads'

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("ffmpeg غير مثبت. يرجى تثبيته.")
        return False

HAS_FFMPEG = check_ffmpeg()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Download Video", callback_data='download_video'),
         InlineKeyboardButton("Convert Video to Audio", callback_data='convert_video_to_audio')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('اختر خياراً:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'download_video':
        await query.message.reply_text('أرسل رابط YouTube لتنزيل الفيديو.')
        context.user_data['action'] = 'download_video'
    elif query.data == 'convert_video_to_audio':
        await query.message.reply_text('أرسل رابط YouTube لتحويل الفيديو إلى صوت.')
        context.user_data['action'] = 'convert_video_to_audio'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action')
    if action == 'download_video':
        await download_video(update, context)
    elif action == 'convert_video_to_audio':
        await convert_video_to_audio(update, context)
    else:
        await update.message.reply_text('يرجى اختيار خيار أولاً.')

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HAS_FFMPEG:
        await update.message.reply_text("ffmpeg غير مثبت، لا يمكن تنزيل الفيديو.")
        return

    url = update.message.text.strip()
    chat_id = update.message.chat_id

    if not ('youtube.com' in url or 'youtu.be' in url):
        await update.message.reply_text("الرابط غير صالح. يرجى إرسال رابط YouTube صحيح.")
        return

    status_msg = await update.message.reply_text("جاري تنزيل الفيديو...")

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'socket_timeout': 60,
        'force_ipv4': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise Exception("فشل في استخراج معلومات الفيديو.")
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise Exception("لم يتم العثور على ملف الفيديو بعد التنزيل.")

        size_mb = os.path.getsize(filename) / (1024 * 1024)
        if size_mb > 50:
            await status_msg.edit_text(f"حجم الفيديو ({size_mb:.1f} MB) أكبر من الحد المسموح به (50 MB). يرجى اختيار فيديو أصغر.")
            os.remove(filename)
            return

        await status_msg.edit_text("تم التنزيل، جاري الإرسال...")
        with open(filename, 'rb') as f:
            await context.bot.send_video(chat_id=chat_id, video=f)
        await status_msg.delete()
        os.remove(filename)

    except Exception as e:
        logger.error(f"خطأ في تنزيل الفيديو: {e}")
        await status_msg.edit_text(f"حدث خطأ أثناء تنزيل الفيديو:\n{str(e)}\nيرجى المحاولة برابط آخر أو فيديو أقصر.")

async def convert_video_to_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HAS_FFMPEG:
        await update.message.reply_text("ffmpeg غير مثبت، لا يمكن تحويل الفيديو إلى صوت.")
        return

    url = update.message.text.strip()
    chat_id = update.message.chat_id

    if not ('youtube.com' in url or 'youtu.be' in url):
        await update.message.reply_text("الرابط غير صالح. يرجى إرسال رابط YouTube صحيح.")
        return

    status_msg = await update.message.reply_text("جاري تحويل الفيديو إلى صوت...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'socket_timeout': 60,
        'force_ipv4': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise Exception("فشل في استخراج معلومات الفيديو.")
            title = info.get('title', 'audio')
            mp3_path = os.path.join(DOWNLOAD_FOLDER, f"{title}.mp3")

        if not os.path.exists(mp3_path):
            # البحث عن ملف mp3 في المجلد
            for file in os.listdir(DOWNLOAD_FOLDER):
                if file.endswith('.mp3'):
                    mp3_path = os.path.join(DOWNLOAD_FOLDER, file)
                    break

        size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
        if size_mb > 50:
            await status_msg.edit_text(f"حجم الملف الصوتي ({size_mb:.1f} MB) أكبر من الحد المسموح به (50 MB). يرجى اختيار ملف أصغر.")
            os.remove(mp3_path)
            return

        await status_msg.edit_text("تم التحويل، جاري الإرسال...")
        with open(mp3_path, 'rb') as f:
            await context.bot.send_audio(chat_id=chat_id, audio=f, title=title, performer="YouTube")
        await status_msg.delete()
        os.remove(mp3_path)

    except Exception as e:
        logger.error(f"خطأ في تحويل الفيديو إلى صوت: {e}")
        await status_msg.edit_text(f"حدث خطأ أثناء التحويل:\n{str(e)}\nيرجى المحاولة برابط آخر أو فيديو أقصر.")

# إضافة باقي إعدادات البوت (start, handlers, إلخ) هنا...
