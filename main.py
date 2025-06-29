import os
import subprocess
import logging
from yt_dlp import YoutubeDL
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    # ضغط الفيديو مع الحفاظ على جودة مقبولة
    command = [
        'ffmpeg', '-i', input_path,
        '-vcodec', 'libx264', '-crf', '28',  # crf بين 18-28، كلما زاد الرقم قل الحجم وجودة أقل
        '-preset', 'fast',
        output_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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

# باقي كود البوت (الأوامر، المعالجات، إلخ) كما هو

def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))  # Handler for /start command
    application.add_handler(CallbackQueryHandler(button_handler))  # Handler for button presses
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # Handle messages

    application.run_polling()

if __name__ == '__main__':
    main()


from keep_alive import keep_alive

if __name__ == '__main__':
    keep_alive()  # تشغيل خادم Flask
    main()  # تشغيل بوت التلغرام
