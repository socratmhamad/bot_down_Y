import os
import subprocess
import logging
from yt_dlp import YoutubeDL
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = '6767447234:AAHODYTwpqlNl0mbeGLK9qAtgKVHfHC0e40'  # ضع توكن البوت هنا
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        logger.error("ffmpeg غير مثبت. يرجى تثبيته.")
        return False

HAS_FFMPEG = check_ffmpeg()

def compress_video(input_path, output_path):
    command = [
        'ffmpeg', '-i', input_path,
        '-vcodec', 'libx264', '-crf', '28',  # جودة متوسطة مع ضغط جيد
        '-preset', 'fast',
        output_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("تنزيل فيديو", callback_data='download_video'),
         InlineKeyboardButton("تحويل فيديو إلى صوت", callback_data='convert_video_to_audio')]
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

    status_msg = await update.message.reply_text("جاري تنزيل الفيديو بجودة 480p...")

    ydl_opts = {
        'format': 'best[height<=480][ext=mp4]/worst',
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

        compressed_path = filename.replace('.mp4', '_compressed.mp4')
        compress_video(filename, compressed_path)

        size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
        if size_mb > 50:
            await status_msg.edit_text(f"حجم الفيديو المضغوط ({size_mb:.1f} MB) ما زال أكبر من الحد المسموح به (50MB). يرجى اختيار فيديو أصغر.")
            os.remove(filename)
            os.remove(compressed_path)
            return

        await status_msg.edit_text("تم التنزيل والضغط، جاري الإرسال كملف وثيقة...")
        with open(compressed_path, 'rb') as f:
            await context.bot.send_document(chat_id=chat_id, document=f, filename=os.path.basename(compressed_path))
        await status_msg.delete()

        os.remove(filename)
        os.remove(compressed_path)

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
            'preferredquality': '192',
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

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("البوت يعمل...")
    app.run_polling()

if __name__ == '__main__':
    main()
