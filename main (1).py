import sys
import logging
# استخدام python-telegram-bot بدلاً من telegram
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.ext._utils.types import BD, BT, CD, UD
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

# إعداد التسجيل للأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
from yt_dlp import YoutubeDL
import os
import logging
import subprocess
import tempfile

TOKEN = '6767447234:AAHODYTwpqlNl0mbeGLK9qAtgKVHfHC0e40'
DOWNLOAD_FOLDER = 'downloads'  # مجلد التنزيلات

# إنشاء مجلد التنزيلات إذا لم يكن موجودًا
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# التحقق من وجود ffmpeg
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
    await query.answer()  # Acknowledge the button press

    if query.data == 'download_video':
        await query.message.reply_text('Please send me the YouTube link to download the video.')
        context.user_data['action'] = 'download_video'  # Store action
    elif query.data == 'convert_video_to_audio':
        await query.message.reply_text('Please send me the YouTube link to convert to audio.')
        context.user_data['action'] = 'convert_video_to_audio'  # Store action

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_action = context.user_data.get('action')

    if user_action == 'download_video':
        await download_video(update, context)
    elif user_action == 'convert_video_to_audio':
        await convert_video_to_audio(update, context)
    else:
        await update.message.reply_text('Please select an option using the buttons.')

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    youtube_url = update.message.text  # الحصول على رابط يوتيوب من الرسالة

    if not HAS_FFMPEG:
        await update.message.reply_text("ffmpeg غير مثبت. لا يمكن تنزيل الفيديو.")
        return

    # تحقق أفضل من الرابط وتنظيفه
    youtube_url = youtube_url.strip()
    if ('youtube.com' in youtube_url or 'youtu.be' in youtube_url) and ('http://' in youtube_url or 'https://' in youtube_url):
        status_message = await update.message.reply_text("جاري التحقق من الرابط وتنزيل الفيديو... يرجى الانتظار")
        try:
            # محاولة أولى بصيغة أكثر مرونة
            ydl_opts = {
                'format': 'best[ext=mp4]/best',  # تبسيط الصيغة
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': False,
                'verbose': True,  # لطباعة معلومات تشخيصية أكثر
                'no_warnings': False,
                'ignoreerrors': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'cookiefile': None,
                'extractor_retries': 5,  # زيادة محاولات الاستخراج
                'socket_timeout': 60,  # زيادة مهلة الانتظار
                'concurrent_fragment_downloads': 1,  # لتجنب مشاكل التنزيل المتزامن
                'external_downloader_args': ['--proxy', ''],  # تجنب استخدام البروكسي الافتراضي
                'force_ipv4': True,  # إجبار استخدام IPv4
                'source_address': '0.0.0.0',  # إجبار استخدام DNS عام - هذا مهم لبيئة Replit
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                },
                'extractor': 'youtube'  # استخدام مستخرج يوتيوب بشكل صريح
            }

            try:
                # محاولة أولى - استراتيجية 1
                with YoutubeDL(ydl_opts) as ydl:
                    # استخدم extract_info مع verbose=True لطباعة المزيد من المعلومات
                    info_dict = ydl.extract_info(youtube_url, download=False)
                    
                    if info_dict is None:
                        raise Exception("فشل في استخراج معلومات الفيديو")
                    
                    # بعد التأكد من صحة البيانات، قم بالتنزيل
                    info_dict = ydl.extract_info(youtube_url, download=True)
                    video_file_path = ydl.prepare_filename(info_dict)
            except Exception as e:
                # محاولة ثانية - استراتيجية 2
                logger.warning(f"فشلت المحاولة الأولى: {str(e)}")
                
                try:
                    # تعديل الخيارات للمحاولة الثانية
                    ydl_opts['format'] = 'best'  # تبسيط الصيغة
                    ydl_opts['force_generic_extractor'] = True  # استخدام مستخرج عام
                    ydl_opts['youtube_include_dash_manifest'] = False  # تعطيل DASH
                    ydl_opts['cachedir'] = False  # تعطيل الكاش
                    
                    with YoutubeDL(ydl_opts) as ydl:
                        info_dict = ydl.extract_info(youtube_url, download=True)
                        if info_dict is None:
                            raise Exception("فشل في استخراج معلومات الفيديو حتى مع المحاولة الثانية")
                        video_file_path = ydl.prepare_filename(info_dict)
                except Exception as e2:
                    # محاولة ثالثة - استراتيجية 3
                    logger.warning(f"فشلت المحاولة الثانية: {str(e2)}")
                    
                    try:
                        # تغيير استراتيجية الاستخراج تماماً
                        ydl_opts['extract_flat'] = True  # استخراج سطحي
                        ydl_opts['skip_download'] = False
                        ydl_opts['format'] = 'worstvideo+worstaudio/worst'  # محاولة تنزيل أقل جودة
                        
                        with YoutubeDL(ydl_opts) as ydl:
                            info_dict = ydl.extract_info(youtube_url, download=True)
                            if info_dict is None:
                                raise Exception("فشل في استخراج معلومات الفيديو")
                            
                            video_file_path = ydl.prepare_filename(info_dict)
                            
                            # التحقق من وجود الملف
                            if not os.path.exists(video_file_path):
                                # البحث عن الملف المناسب
                                for file in os.listdir(DOWNLOAD_FOLDER):
                                    if file.endswith('.mp4'):
                                        video_file_path = os.path.join(DOWNLOAD_FOLDER, file)
                                        break
                    except Exception as e3:
                        # فشلت جميع المحاولات
                        logger.error(f"فشلت جميع محاولات التنزيل: {str(e3)}")
                        raise Exception(f"تعذر تنزيل الفيديو بعد عدة محاولات. قد يكون السبب قيود الاستضافة على Replit أو مشكلة في الرابط.")
                    
                # التحقق من وجود الملف فعلياً
                if not os.path.exists(video_file_path):
                    raise Exception(f"لم يتم العثور على الملف: {video_file_path}")
                
                # التحقق من حجم الملف (حد تليجرام هو 50 ميجابايت)
                file_size = os.path.getsize(video_file_path) / (1024 * 1024)  # بالميجابايت
                
                if file_size > 50:
                    await status_message.edit_text(f"حجم الفيديو كبير جدًا ({file_size:.1f} MB). تليجرام يدعم حتى 50 MB.")
                    os.remove(video_file_path)
                    return

            await status_message.edit_text("اكتمل التنزيل، جاري الإرسال...")
            with open(video_file_path, 'rb') as video_file:
                await context.bot.send_video(chat_id=chat_id, video=video_file)
                
            await status_message.delete()
            os.remove(video_file_path)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"خطأ في معالجة رابط YouTube: {error_msg}")
            
            # تقديم رسالة خطأ مفصلة للمستخدم
            if "403" in error_msg or "Forbidden" in error_msg or "proxy" in error_msg.lower():
                await status_message.edit_text("خطأ في الوصول لخدمة يوتيوب. بسبب قيود الاستضافة في Replit، قد تكون خدمة يوتيوب محجوبة. حاول استخدام رابط فيديو آخر.")
            elif "Unable to extract" in error_msg or "extractor" in error_msg.lower() or "Failed to extract" in error_msg:
                await status_message.edit_text("لم يستطع البوت استخراج معلومات الفيديو بسبب قيود الاستضافة. جرب استخدام رابط آخر أو فيديو أصغر حجما.")
            elif "geo-restriction" in error_msg.lower():
                await status_message.edit_text("هذا الفيديو غير متاح في منطقتك بسبب قيود جغرافية.")
            elif "private video" in error_msg.lower():
                await status_message.edit_text("هذا فيديو خاص غير متاح للتنزيل.")
            elif "copyright" in error_msg.lower():
                await status_message.edit_text("هذا الفيديو محمي بحقوق النشر ولا يمكن تنزيله.")
            elif "sign in" in error_msg.lower() or "login" in error_msg.lower():
                await status_message.edit_text("هذا الفيديو يتطلب تسجيل الدخول لمشاهدته ولا يمكن تنزيله.")
            elif "premiere" in error_msg.lower():
                await status_message.edit_text("هذا بث مباشر أو فيديو premiere غير متاح للتنزيل حاليًا.")
            elif "unsupported URL" in error_msg:
                await status_message.edit_text("الرابط غير صالح أو غير مدعوم. تأكد من إرسال رابط يوتيوب صحيح.")
            elif "unavailable" in error_msg.lower():
                await status_message.edit_text("هذا الفيديو غير متاح للمشاهدة أو التنزيل حاليًا.")
            else:
                await status_message.edit_text(f"حدث خطأ أثناء معالجة رابط YouTube:\n{error_msg[:100]}...\nيرجى المحاولة برابط آخر أو استخدام فيديو أقصر.")
    else:
        await update.message.reply_text("يرجى تقديم رابط YouTube صالح.")

async def convert_video_to_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    youtube_url = update.message.text  # الحصول على رابط يوتيوب من الرسالة

    if not HAS_FFMPEG:
        await update.message.reply_text("ffmpeg غير مثبت. لا يمكن تحويل الفيديو إلى صوت.")
        return

    if 'youtube.com' in youtube_url or 'youtu.be' in youtube_url:
        status_message = await update.message.reply_text("جاري تحويل الفيديو إلى صوت... يرجى الانتظار")
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'ignoreerrors': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'cookiefile': None,
                'extractor_retries': 5,
                'socket_timeout': 60,
                'external_downloader_args': ['--proxy', ''],
                'force_ipv4': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                },
                'extractor': 'youtube'
            }

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    # التحقق من معلومات الفيديو أولاً قبل التنزيل
                    info_dict = ydl.extract_info(youtube_url, download=False)
                    
                    if info_dict is None:
                        raise Exception("فشل في استخراج معلومات الفيديو")
                    
                    # بعد التأكد من صحة البيانات، قم بالتنزيل
                    info_dict = ydl.extract_info(youtube_url, download=True)
            except Exception as e:
                # محاولة بخيارات بديلة
                logger.warning(f"فشلت المحاولة الأولى للتحويل: {e}")
                
                # تعديل الخيارات للمحاولة الثانية
                ydl_opts['format'] = 'bestaudio'  # تبسيط الصيغة
                ydl_opts['force_generic_extractor'] = True  # استخدام مستخرج عام
                
                with YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(youtube_url, download=True)
                    if info_dict is None:
                        raise Exception("فشل في استخراج معلومات الفيديو حتى مع المحاولة الثانية")
                title = info_dict.get('title', 'audio')
                mp3_file_path = os.path.join(DOWNLOAD_FOLDER, f"{title}.mp3")
                
                # التحقق من وجود الملف بالاسم المتوقع
                if not os.path.exists(mp3_file_path):
                    # البحث عن ملف mp3 في مجلد التنزيلات
                    for file in os.listdir(DOWNLOAD_FOLDER):
                        if file.endswith('.mp3'):
                            mp3_file_path = os.path.join(DOWNLOAD_FOLDER, file)
                            break

                # التحقق من حجم الملف (حد تليجرام هو 50 ميجابايت)
                file_size = os.path.getsize(mp3_file_path) / (1024 * 1024)  # بالميجابايت
                if file_size > 50:
                    await status_message.edit_text(f"حجم الملف الصوتي كبير جدًا ({file_size:.1f} MB). تليجرام يدعم حتى 50 MB.")
                    os.remove(mp3_file_path)
                    return

            await status_message.edit_text("اكتمل التحويل، جاري الإرسال...")
            with open(mp3_file_path, 'rb') as audio_file:
                await context.bot.send_audio(
                    chat_id=chat_id, 
                    audio=audio_file,
                    title=title,
                    performer="YouTube"
                )
                
            await status_message.delete()
            os.remove(mp3_file_path)

        except Exception as e:
            logger.error(f"خطأ في معالجة رابط YouTube: {e}")
            await status_message.edit_text("حدث خطأ أثناء تحويل الفيديو إلى صوت. يرجى المحاولة مرة أخرى.")
    else:
        await update.message.reply_text("يرجى تقديم رابط YouTube صالح.")

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