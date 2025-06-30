import sys
import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

# إعداد التسجيل للأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
from yt_dlp import YoutubeDL
import os
import subprocess

TOKEN = '6767447234:AAHODYTwpqlNl0mbeGLK9qAtgKVHfHC0e40'
DOWNLOAD_FOLDER = 'downloads'
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB

def ensure_download_folder():
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
ensure_download_folder()

# التحقق من وجود ffmpeg
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except Exception:
        logger.error("ffmpeg غير مثبت.")
        return False

HAS_FFMPEG = check_ffmpeg()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[
        InlineKeyboardButton("📹 فيديو عالية", callback_data='download_video_hq'),
        InlineKeyboardButton("📱 فيديو متوسطة", callback_data='download_video_mq')
    ],
    [InlineKeyboardButton("🎵 صوت", callback_data='convert_video_to_audio')]
    ]
    await update.message.reply_text('اختر:', reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    mapping = {
        'download_video_hq': 'high',
        'download_video_mq': 'medium',
        'convert_video_to_audio': 'audio'
    }
    context.user_data['action'] = mapping.get(q.data)
    prompts = {
        'high': '📹 أرسل رابط فيديو عالي الجودة',
        'medium': '📱 أرسل رابط فيديو متوسط الجودة',
        'audio': '🎵 أرسل رابط لتحويله إلى صوت'
    }
    await q.message.reply_text(prompts.get(context.user_data['action'], ''))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    action = context.user_data.get('action')
    if action in ['high', 'medium']:
        await download_video(update, context, quality=action)
    elif action == 'audio':
        await convert_video_to_audio(update, context)
    else:
        await update.message.reply_text('الرجاء اختيار خيار أولاً.')

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str) -> None:
    chat_id = update.effective_chat.id
    url = update.message.text.strip()

    if not HAS_FFMPEG:
        return await update.message.reply_text('ffmpeg مفقود.')
    if not url.startswith(('http://', 'https://')):
        return await update.message.reply_text('رابط غير صالح.')

    status = await update.message.reply_text('⏳ جاري التنزيل...')

    # إعداد تنسيق التنزيل بناءً على الجودة المطلوبة
    if quality == 'high':
        fmt = 'bestvideo[ext=mp4]+bestaudio/best'
    else:
        fmt = 'bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]'

    ydl_opts = {
        'format': fmt,
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'socket_timeout': 300,
        'http_chunk_size': 10 * 1024 * 1024,
        'concurrent_fragment_downloads': 4,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        size = os.path.getsize(path)
        await status.edit_text(f'✅ تم التنزيل ({size / (1024 * 1024):.1f} MB)')
    except Exception as e:
        logger.error('خطأ في التنزيل: %s', e)
        return await status.edit_text(f'خطأ في التنزيل: {str(e)}')

    # إذا كان الفيديو كبيراً، ننزل نسخة منخفضة الدقة
    original_path = path
    if size > MAX_VIDEO_SIZE:
        await status.edit_text('📉 الفيديو كبير، جاري تنزيل نسخة منخفضة الدقة...')

        # تنسيق جديد لنسخة منخفضة الدقة (360p)
        low_res_fmt = 'bestvideo[height<=360][ext=mp4]+bestaudio/best[height<=360]'
        ydl_opts['format'] = low_res_fmt

        try:
            # حذف الملف الأصلي
            if os.path.exists(original_path):
                os.remove(original_path)

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
            size = os.path.getsize(path)
            await status.edit_text(f'✅ تم تنزيل نسخة منخفضة الدقة ({size / (1024 * 1024):.1f} MB)')
        except Exception as e:
            logger.error('خطأ في تنزيل النسخة المنخفضة: %s', e)
            await status.edit_text(f'خطأ في تنزيل النسخة المنخفضة: {str(e)}')
            if os.path.exists(original_path):
                os.remove(original_path)
            return

    # إرسال الملف
    try:
        if size <= MAX_VIDEO_SIZE:
            await context.bot.send_video(chat_id, video=open(path, 'rb'), 
                                      read_timeout=300, write_timeout=300,
                                      caption=f"📹 {info.get('title', '')}")
        else:
            await context.bot.send_document(chat_id, document=open(path, 'rb'),
                                         read_timeout=300, write_timeout=300,
                                         caption=f"📁 {info.get('title', '')} ({size / (1024 * 1024):.1f} MB)")

        await status.delete()
    except Exception as e:
        logger.error('خطأ في الإرسال: %s', e)
        await status.edit_text(f'خطأ في الإرسال: {str(e)}')
    finally:
        if os.path.exists(path):
            os.remove(path)

async def convert_video_to_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    url = update.message.text.strip()

    if not HAS_FFMPEG:
        return await update.message.reply_text('ffmpeg مفقود.')
    if not url.startswith(('http://', 'https://')):
        return await update.message.reply_text('رابط غير صالح.')

    status = await update.message.reply_text('⏳ جاري التحويل...')
    aopts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192'
        }],
        'noplaylist': True,
        'socket_timeout': 300,
    }

    try:
        with YoutubeDL(aopts) as ydl:
            info = ydl.extract_info(url, download=True)
        mp3_path = os.path.join(DOWNLOAD_FOLDER, f"{info.get('title', 'audio')}.mp3")
        size = os.path.getsize(mp3_path)
        await status.edit_text(f'✅ تم التحويل ({size / (1024 * 1024):.1f} MB)')
    except Exception as e:
        logger.error('خطأ في التحويل: %s', e)
        return await status.edit_text(f'خطأ في التحويل: {str(e)}')

    # إرسال الملف الصوتي
    try:
        if size <= MAX_VIDEO_SIZE:
            await context.bot.send_audio(chat_id, audio=open(mp3_path, 'rb'),
                                         read_timeout=300, write_timeout=300,
                                         title=info.get('title', ''))
        else:
            await context.bot.send_document(chat_id, document=open(mp3_path, 'rb'),
                                           read_timeout=300, write_timeout=300,
                                           caption=f"🎵 {info.get('title', '')} ({size / (1024 * 1024):.1f} MB)")

        await status.delete()
    except Exception as e:
        logger.error('خطأ في إرسال الصوت: %s', e)
        await status.edit_text(f'خطأ في إرسال الصوت: {str(e)}')
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).read_timeout(300).write_timeout(300).pool_timeout(300).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
