import telebot
from telebot import types
from datetime import datetime, timedelta
import time
import threading
import random
import sqlite3
import requests
from bs4 import BeautifulSoup
import os
import re
import logging
import traceback
from requests.adapters import HTTPAdapter 
from urllib3.util.retry import Retry

# إعدادات البوت الأساسية
token = '7957161922:AAHPUdaW7MHU5YB2__x9IUl_Oa5QFN7H4SE'  # توكن البوت
OWNER_ID = 7701080191  # أي دي المالك
owner_user = "ML_F_P"  # يوزر المالك بدون @
LOG_CHANNEL = "@MM_IP7"  # قناة السجلات والخطأ
STORAGE_CHANNEL = "@MM_IP7"  # قناة تخزين الأخبار

urlacc = "https://t.me/" + owner_user
SOLO = telebot.TeleBot(token, threaded=True, num_threads=10)

# إعداد السجلات
logging.basicConfig(
    filename='bot_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# جلسة طلبات مع إعادة المحاولة
session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=(500, 502, 504),
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
session.mount('http://', adapter)
session.mount('https://', adapter)

# قوائم البيانات
activation_codes = {}
activated_users = {}
bot_locked = False
deleted_codes = []
banned_users = []
CHANNELS = []
admins = {OWNER_ID: "owner"}  # تخزين الأدمن مع رتبهم

# زخارف للنشر
DECORATIONS = [
    "✨", "🌟", "⚡", "🔥", "🎬", "📺", "📚", "🎭", "💫", "🌸",
    "🍥", "🗾", "🎋", "🎏", "🎎", "🏮", "📜", "🎐", "🎌", "🎮"
]

# مصدر تلقائي للأخبار (مواقع أنمي ومانجا - محدثة وسريعة وموثوقة)
ANIME_NEWS_SOURCES = [
    "https://www.animenewsnetwork.com/news",      # موثوق جدًا
    "https://myanimelist.net/news",               # جيد
    "https://www.crunchyroll.com/news"            # سريع ورسمي
]

MANGA_NEWS_SOURCES = [
    "https://myanimelist.net/news/manga",         # جيد
    "https://www.mangaupdates.com/news.html"      # سريع جدًا في تحديثات المانجا
]

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    
    # جدول الأخبار
    c.execute('''CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        image_url TEXT,
        source TEXT,
        publish_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # جدول الإعدادات
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # جدول أوقات النشر
    c.execute('''CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY,
        hour INTEGER NOT NULL,
        minute INTEGER NOT NULL
    )''')
    
    # جدول قنوات النشر
    c.execute('''CREATE TABLE IF NOT EXISTS publish_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL UNIQUE
    )''')
    
    # جدول المشرفين
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        role TEXT NOT NULL
    )''')
    
    # إعدادات افتراضية
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('publishing_enabled', '1')")
    c.execute("INSERT OR IGNORE INTO schedule (id, hour, minute) VALUES (1, 12, 0)")  # وقت الأنمي
    c.execute("INSERT OR IGNORE INTO schedule (id, hour, minute) VALUES (2, 15, 0)")  # وقت المانجا
    c.execute("INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, ?)", (OWNER_ID, "owner"))
    
    # تحديث قائمة المشرفين
    global admins
    c.execute("SELECT user_id, role FROM admins")
    admins = {row[0]: row[1] for row in c.fetchall()}
    
    conn.commit()
    conn.close()

# تهيئة قاعدة البيانات عند البدء
init_db()

# وظائف مساعدة لقاعدة البيانات
def get_setting(key):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def set_setting(key, value):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def save_news(news_type, title, content, image_url="", source=""):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute('''INSERT INTO news 
                 (type, title, content, image_url, source) 
                 VALUES (?, ?, ?, ?, ?)''',
              (news_type, title, content, image_url, source))
    conn.commit()
    conn.close()

def get_news(news_type, limit=10):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("SELECT * FROM news WHERE type = ? ORDER BY id DESC LIMIT ?", (news_type, limit))
    result = c.fetchall()
    conn.close()
    return result

def get_news_count(news_type):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM news WHERE type = ?", (news_type,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def delete_news(news_id):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("DELETE FROM news WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()

def get_schedule(news_type):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    schedule_id = 1 if news_type == 'anime' else 2
    c.execute("SELECT hour, minute FROM schedule WHERE id = ?", (schedule_id,))
    result = c.fetchone()
    conn.close()
    return result if result else (12, 0)  # وقت افتراضي

def set_schedule(news_type, hour, minute):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    schedule_id = 1 if news_type == 'anime' else 2
    c.execute("INSERT OR REPLACE INTO schedule (id, hour, minute) VALUES (?, ?, ?)", 
              (schedule_id, hour, minute))
    conn.commit()
    conn.close()

def add_publish_channel(channel):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO publish_channels (channel) VALUES (?)", (channel,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_publish_channel(channel):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("DELETE FROM publish_channels WHERE channel = ?", (channel,))
    conn.commit()
    conn.close()

def get_publish_channels():
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("SELECT channel FROM publish_channels")
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result

def get_admins():
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("SELECT user_id, role FROM admins")
    result = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return result

def add_admin(user_id, role="admin"):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO admins (user_id, role) VALUES (?, ?)", (user_id, role))
    conn.commit()
    conn.close()
    
    # تحديث المتغير العالمي
    global admins
    admins[user_id] = role

def remove_admin(user_id):
    conn = sqlite3.connect('anime_news.db')
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    # تحديث المتغير العالمي
    global admins
    if user_id in admins:
        del admins[user_id]

# وظيفة للتحقق من الاشتراكات
def check_subscriptions(user_id):
    for channel in CHANNELS:
        try:
            member = SOLO.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

# وظيفة إرسال إشعار التفعيل
def send_activation_notification(user_id, username, code):
    notify_message = (
        f"تم تفعيل كود من قبل مستخدم:\n"
        f"ID: {user_id}\n"
        f"Username: @{username}\n"
        f"Code: {code}\n"
        f"Date: {datetime.now()}"
    )
    SOLO.send_message(OWNER_ID, notify_message)

# وظيفة التحقق من تفعيل المستخدم
def is_user_activated(user_id):
    if user_id in activated_users:
        if activated_users[user_id]['expiry_date'] > datetime.now():
            return True
        else:
            del activated_users[user_id]
            return False
    return False

# إصلاح روابط الصور
def fix_image_url(url, source):
    if url.startswith('http'):
        return url
    elif url.startswith('//'):
        return 'https:' + url
    elif url.startswith('/'):
        domain = source.split('//')[1].split('/')[0]
        return 'https://' + domain + url
    else:
        return ""

# وظيفة جلب أخبار من المواقع (محدثة)
def fetch_news(news_type):
    sources = ANIME_NEWS_SOURCES if news_type == 'anime' else MANGA_NEWS_SOURCES
    news_items = []
    
    for source_url in sources:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = session.get(source_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # معالجة مختلفة لكل موقع
            if "animenewsnetwork" in source_url:
                articles = soup.select('.herald.box.news')
                for article in articles[:5]:
                    title_elem = article.select_one('h3 a')
                    if not title_elem:
                        continue
                        
                    title = title_elem.text.strip()
                    content_elem = article.select_one('.preview')
                    content = content_elem.text.strip() if content_elem else title
                    
                    image_elem = article.select_one('img')
                    image_url = image_elem['src'] if image_elem and 'src' in image_elem.attrs else ""
                    
                    if not image_url:
                        image_elem = article.select_one('.thumbnail')
                        if image_elem and 'data-src' in image_elem.attrs:
                            image_url = image_elem['data-src']
                    
                    news_items.append({
                        'title': title,
                        'content': content,
                        'image_url': image_url,
                        'source': source_url
                    })
            
            elif "myanimelist" in source_url:
                articles = soup.select('.news-unit')
                for article in articles[:5]:
                    title_elem = article.select_one('.title')
                    if not title_elem:
                        continue
                        
                    title = title_elem.text.strip()
                    content_elem = article.select_one('.text')
                    content = content_elem.text.strip() if content_elem else title
                    
                    image_elem = article.select_one('img')
                    image_url = image_elem['src'] if image_elem and 'src' in image_elem.attrs else ""
                    
                    news_items.append({
                        'title': title,
                        'content': content,
                        'image_url': image_url,
                        'source': source_url
                    })
            
        except Exception as e:
            error_msg = f"Error fetching news from {source_url}: {str(e)}"
            logging.error(error_msg)
            try:
                SOLO.send_message(LOG_CHANNEL, error_msg)
            except:
                pass
    
    return news_items

# التحقق من وجود قنوات نشر
def check_publish_channels():
    try:
        channels = get_publish_channels()
        if not channels:
            msg = "⚠️ لم يتم تعيين أي قنوات نشر!"
            SOLO.send_message(OWNER_ID, msg)
            return False
            
        return True
    except Exception as e:
        error_msg = f"❌ خطأ في فحص القنوات: {str(e)}"
        SOLO.send_message(OWNER_ID, error_msg)
        return False

# وظيفة بدء النشر التلقائي (محدثة)
def start_publishing():
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # تسجيل وقت التحقق
            if now.minute % 5 == 0:  # كل 5 دقائق
                status_msg = f"⏰ البوت يعمل، الوقت الحالي: {current_time}"
                try:
                    SOLO.send_message(OWNER_ID, status_msg)
                except:
                    pass
            
            if get_setting('publishing_enabled') == '1' and not bot_locked:
                # تحقق من وجود قنوات نشر
                if not check_publish_channels():
                    time.sleep(600)  # انتظر 10 دقائق قبل المحاولة مجدداً
                    continue
                
                # نشر الأنمي حسب الجدول
                anime_hour, anime_minute = get_schedule('anime')
                if now.hour == anime_hour and now.minute == anime_minute:
                    anime_news = get_news('anime', 1)
                    if anime_news:
                        news_id, news_type, title, content, image_url, source, publish_time = anime_news[0]
                        send_news({
                            'title': title,
                            'content': content,
                            'image_url': image_url,
                            'source': source
                        }, 'anime')
                        delete_news(news_id)
                
                # نشر المانجا حسب الجدول
                manga_hour, manga_minute = get_schedule('manga')
                if now.hour == manga_hour and now.minute == manga_minute:
                    manga_news = get_news('manga', 1)
                    if manga_news:
                        news_id, news_type, title, content, image_url, source, publish_time = manga_news[0]
                        send_news({
                            'title': title,
                            'content': content,
                            'image_url': image_url,
                            'source': source
                        }, 'manga')
                        delete_news(news_id)
            
            time.sleep(60)
        except Exception as e:
            error_msg = f"Error in publishing thread: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            try:
                SOLO.send_message(LOG_CHANNEL, error_msg)
            except:
                pass
            time.sleep(300)

# وظيفة إرسال الخبر (محدثة لدعم قنوات متعددة)
def send_news(news_item, news_type):
    try:
        title = news_item.get('title', '')
        content = news_item.get('content', '')
        image_url = news_item.get('image_url', '')
        source = news_item.get('source', '')
        
        # إصلاح رابط الصورة
        if image_url and not image_url.startswith('http'):
            image_url = fix_image_url(image_url, source)
        
        # تنظيف المحتوى من الروابط غير المرغوب فيها
        content = re.sub(r'http\S+', '', content)
        
        decoration = random.choice(DECORATIONS)
        channels = get_publish_channels()
        
        if not channels:
            error_msg = "No publishing channels set"
            logging.warning(error_msg)
            try:
                SOLO.send_message(LOG_CHANNEL, error_msg)
            except:
                pass
            return
            
        # تنسيق الخبر بشكل احترافي
        caption = f"<b>{decoration} {title} {decoration}</b>\n\n"
        caption += f"<i>{content}</i>\n\n"
        caption += f"📅 <b>التاريخ:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        
        if source:
            source_name = "Anime News Network" if "animenewsnetwork" in source else "MyAnimeList"
            caption += f"📌 <b>المصدر:</b> {source_name}\n"
            
        caption += f"🏷️ <b>التصنيف:</b> #{'أنمي' if news_type == 'anime' else 'مانجا'}"
        
        # التحقق من صحة التنسيق
        if len(caption) > 1024:
            caption = caption[:1000] + "... [تم اختصار النص]"
            
        if not title.strip():
            try:
                SOLO.send_message(OWNER_ID, "⚠️ عنوان الخبر فارغ!")
            except:
                pass
            return
        
        # حفظ نسخة في قناة التخزين
        try:
            if image_url and image_url.startswith('http'):
                SOLO.send_photo(STORAGE_CHANNEL, image_url, caption=caption, parse_mode='HTML')
            else:
                SOLO.send_message(STORAGE_CHANNEL, caption, parse_mode='HTML')
        except Exception as e:
            error_msg = f"Error saving to storage: {str(e)}"
            logging.error(error_msg)
            try:
                SOLO.send_message(LOG_CHANNEL, error_msg)
            except:
                pass
        
        # إرسال إلى قنوات النشر
        for channel in channels:
            try:
                # إرسال مع صورة إذا وجدت
                if image_url and image_url.startswith('http'):
                    SOLO.send_photo(channel, image_url, caption=caption, parse_mode='HTML')
                # إرسال بدون صورة
                else:
                    SOLO.send_message(channel, caption, parse_mode='HTML')
                
                # تسجيل نجاح الإرسال
                success_msg = f"✅ تم النشر بنجاح في {channel}"
                logging.info(success_msg)
                
                # تأخير بين الإرسال
                time.sleep(2)
                
            except Exception as e:
                error_msg = f"❌ فشل النشر في {channel}: {str(e)}"
                logging.error(error_msg)
                try:
                    SOLO.send_message(OWNER_ID, error_msg)
                except:
                    pass
                
    except Exception as e:
        error_msg = f"🔥 خطأ جسيم في الإرسال: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        try:
            SOLO.send_message(LOG_CHANNEL, error_msg)
        except:
            pass

# قسم الأوامر الأساسية
@SOLO.message_handler(commands=['start'])
def send_welcome(message):
    global bot_locked, admins
    
    # تحديث قائمة المشرفين
    admins = get_admins()
    
    user_id = message.from_user.id
    
    if user_id in banned_users:
        SOLO.send_message(user_id, "عذرًا، تم حظرك من استخدام البوت.")
    elif user_id in admins:
        show_admin_panel(message)
    elif bot_locked:
        SOLO.reply_to(message, "🔮عذرا،\n🔧🪛البوت مغلق عند الجميع حاليا للصيانة🔨🪚\nسيتم اعادة تشغيل البوت عند الانتهاء من الصيانة.🔌")
    elif check_subscriptions(user_id):
        if is_user_activated(user_id):
            SOLO.reply_to(message, "مرحبا بك عزيزي المستخدم\n💡البوت مفعل لديك💡")
        else:
            show_activation_options(message)
    else:
        show_subscription_required(message)

# اختبار النشر
@SOLO.message_handler(commands=['test'])
def test_publish(message):
    if message.from_user.id != OWNER_ID:
        return
        
    test_msg = "🔊 هذا اختبار للنشر في القنوات!"
    channels = get_publish_channels()
    
    if not channels:
        SOLO.reply_to(message, "⚠️ لا توجد قنوات نشر محددة!")
        return
        
    for channel in channels:
        try:
            SOLO.send_message(channel, test_msg)
            SOLO.reply_to(message, f"✅ تم الإرسال إلى {channel}")
            time.sleep(1)
        except Exception as e:
            SOLO.reply_to(message, f"❌ فشل الإرسال إلى {channel}: {str(e)}")

# عرض لوحة التحكم للمشرفين (محدثة)
def show_admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("💰قسم الاشتراك المدفوع💰", callback_data="subscription"),
        types.InlineKeyboardButton("✨قفل | فتح البوت✨", callback_data="un_lock"),
        types.InlineKeyboardButton("📵قسم الحظر📵", callback_data="banding"),
        types.InlineKeyboardButton("♟️قسم الاشتراك الإجباري♟️", callback_data="subchannels"),
        types.InlineKeyboardButton("📣الإذاعة📣", callback_data="broadcasting"),
        types.InlineKeyboardButton("🎌قسم الأنمي والمانجا🎌", callback_data="anime_manga_section"),
        types.InlineKeyboardButton("🔄 تحديث الأخبار تلقائيًا", callback_data="fetch_auto_news"),
        types.InlineKeyboardButton("📝 السجلات والأخطاء", callback_data="logs_section")
    ]
    
    if message.from_user.id == OWNER_ID:
        buttons.extend([
            types.InlineKeyboardButton("👥قسم الأدمن👥", callback_data="adminsplace"),
            types.InlineKeyboardButton("⚙️ الإعدادات المتقدمة", callback_data="advanced_settings")
        ])
    
    buttons.append(types.InlineKeyboardButton("🔄 تحديث", callback_data="admin_menu"))
    markup.add(*buttons)
    
    # حالة البوت
    status = "🟢 قيد التشغيل" if not bot_locked else "🔴 متوقف للصيانة"
    publishing_status = "🟢 نشط" if get_setting('publishing_enabled') == '1' else "🔴 متوقف"
    anime_hour, anime_minute = get_schedule('anime')
    manga_hour, manga_minute = get_schedule('manga')
    anime_time = f"{anime_hour}:{anime_minute:02d}"
    manga_time = f"{manga_hour}:{manga_minute:02d}"
    publish_channels = get_publish_channels()
    channel_list = "\n".join(publish_channels) if publish_channels else "لم يتم تعيين"
    
    welcome_msg = (
        f"⛓️‍💥 أهلاً وسهلاً بك عزيزي المشرف\n"
        f"🛠️ لوحة التحكم الرئيسية\n\n"
        f"📊 حالة البوت: {status}\n"
        f"📢 حالة النشر: {publishing_status}\n"
        f"⏰ وقت نشر الأنمي: {anime_time}\n"
        f"⏳ وقت نشر المانجا: {manga_time}\n"
        f"📺 أخبار الأنمي المخزنة: {get_news_count('anime')}\n"
        f"📚 أخبار المانجا المخزنة: {get_news_count('manga')}\n"
        f"📢 قنوات النشر:\n{channel_list}"
    )
    
    SOLO.reply_to(message, welcome_msg, reply_markup=markup)

# عرض خيارات التفعيل
def show_activation_options(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰شراء كود التفعيل💰", url=urlacc))
    markup.add(types.InlineKeyboardButton("✨ادخل كود التفعيل✨", callback_data="enter_code"))
    
    if message.from_user.username:
        photo_url = f"https://t.me/{message.from_user.username}"
        namess = f"[{message.from_user.first_name}]({photo_url})"
    else:
        namess = message.from_user.first_name
        
    text = f"⚠️ اهلا بك عزيزي ✨{namess}✨ في البوت\n للأسف انت غير مشترك حاليا في البوت للاشتراك يرجى التواصل مع مالك البوت"
    SOLO.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

# عرض رسالة الاشتراك المطلوب
def show_subscription_required(message):
    subscription_message = "الرجاء الاشتراك بقنوات البوت للمتابعة:\n"
    for channel in CHANNELS:
        subscription_message += f"رابط القناة هنا: https://t.me/{channel[1:]}\n"
    subscription_message += "\nبعد الاشتراك اضغط /start للتحقق من اشتراكك."
    SOLO.reply_to(message, subscription_message)

# قسم السجلات والأخطاء الجديد
def handle_logs_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📋 عرض آخر الأخطاء", callback_data="view_errors"),
        types.InlineKeyboardButton("🧹 مسح السجلات", callback_data="clear_logs"),
        types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_menu")
    )
    
    SOLO.edit_message_text(
        "📝 قسم السجلات والأخطاء:\n"
        "هنا يمكنك إدارة سجلات البوت والأخطاء",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@SOLO.callback_query_handler(func=lambda call: call.data == "view_errors")
def view_errors(call):
    try:
        with open('bot_errors.log', 'r') as f:
            logs = f.read()
            if len(logs) > 3000:
                logs = logs[-3000:]  # آخر 3000 حرف
            SOLO.send_message(call.from_user.id, f"<pre>{logs}</pre>", parse_mode='HTML')
    except Exception as e:
        SOLO.send_message(call.from_user.id, f"خطأ في قراءة السجلات: {str(e)}")

@SOLO.callback_query_handler(func=lambda call: call.data == "clear_logs")
def clear_logs(call):
    try:
        open('bot_errors.log', 'w').close()
        SOLO.send_message(call.from_user.id, "تم مسح سجلات الأخطاء بنجاح")
    except Exception as e:
        SOLO.send_message(call.from_user.id, f"خطأ في مسح السجلات: {str(e)}")

# قسم معالجة الأزرار
@SOLO.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    global bot_locked
    
    user_id = call.from_user.id
    if not is_user_activated(user_id) and user_id not in admins:
        SOLO.answer_callback_query(call.id, "عذرًا، يجب تفعيل اشتراكك أولاً.")
        return
    
    # قسم الاشتراك المدفوع
    if call.data == "subscription":
        handle_subscription_section(call)
    
    # قسم قفل/فتح البوت
    elif call.data == "un_lock":
        handle_lock_section(call)
    
    # قسم الحظر
    elif call.data == "banding":
        handle_ban_section(call)
    
    # قسم الاشتراك الإجباري
    elif call.data == "subchannels":
        handle_channels_section(call)
    
    # قسم الإذاعة
    elif call.data == "broadcasting":
        handle_broadcast_section(call)
    
    # قسم الأنمي والمانجا
    elif call.data == "anime_manga_section":
        handle_anime_manga_section(call)
    
    # جلب الأخبار تلقائيًا
    elif call.data == "fetch_auto_news":
        handle_fetch_auto_news(call)
    
    # قسم السجلات
    elif call.data == "logs_section":
        handle_logs_section(call)
    
    # قسم المشرفين (للمالك فقط)
    elif call.data == "adminsplace" and user_id == OWNER_ID:
        handle_admins_section(call)
    
    # الإعدادات المتقدمة
    elif call.data == "advanced_settings":
        handle_advanced_settings(call)
    
    # إدخال كود التفعيل
    elif call.data == "enter_code":
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال كود التفعيل:")
        SOLO.register_next_step_handler(msg, process_activation_code)
    
    # إضافة كود تفعيل
    elif call.data == "add_code" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال الكود بالصيغة التالية: الكود:عدد المستخدمين:عدد الأيام")
        SOLO.register_next_step_handler(msg, add_code)
    
    # حذف كود تفعيل
    elif call.data == "delete_code" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال الكود الذي ترغب في حذفه:")
        SOLO.register_next_step_handler(msg, delete_code)
    
    # قفل البوت
    elif call.data == "lock_bot" and call.from_user.id in admins:
        bot_locked = True
        SOLO.send_message(call.message.chat.id, "تم قفل البوت. لا يمكن لأي شخص استخدامه الآن.")
    
    # فتح البوت
    elif call.data == "unlock_bot" and call.from_user.id in admins:
        bot_locked = False
        SOLO.send_message(call.message.chat.id, "تم فتح البوت. يمكن للمستخدمين استخدامه الآن.")
    
    # حظر مستخدم
    elif call.data == "ban_user" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال معرف الشخص الذي ترغب في حظره:")
        SOLO.register_next_step_handler(msg, process_ban_user)
    
    # إلغاء حظر مستخدم
    elif call.data == "unban_user" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال معرف الشخص الذي ترغب في إلغاء حظره:")
        SOLO.register_next_step_handler(msg, process_unban_user)
    
    # عرض المحظورين
    elif call.data == "list_banned" and call.from_user.id in admins:
        list_banned_users(call.message.chat.id)
    
    # إلغاء حظر الجميع
    elif call.data == "unban_all" and call.from_user.id in admins:
        unban_all_users(call.message.chat.id)
    
    # عرض القنوات
    elif call.data == "list_channels" and call.from_user.id in admins:
        list_channels(call.message.chat.id)
    
    # إضافة قناة
    elif call.data == "add_channel" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال يوزر القناة التي ترغب في إضافتها (بصيغة @channelusername):")
        SOLO.register_next_step_handler(msg, add_channel)
    
    # حذف قناة
    elif call.data == "remove_channel" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال يوزر القناة التي ترغب في حذفها (بصيغة @channelusername):")
        SOLO.register_next_step_handler(msg, remove_channel)
    
    # إذاعة للجميع
    elif call.data == "broadcast_all" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال الرسالة التي ترغب في إرسالها للجميع:")
        SOLO.register_next_step_handler(msg, broadcast_all_users)
    
    # إذاعة لمستخدم
    elif call.data == "broadcast_user" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "يرجى إدخال معرف الشخص ثم الرسالة، مفصولة بعلامة (:) مثلًا: user_id:message")
        SOLO.register_next_step_handler(msg, broadcast_to_user)
    
    # رفع مشرف
    elif call.data == "promote_admin" and call.from_user.id == OWNER_ID:
        SOLO.send_message(call.from_user.id, "أرسل إيدي الشخص لرفعه كمشرف:")
        SOLO.register_next_step_handler(call.message, process_promote_admin)
    
    # تنزيل مشرف
    elif call.data == "demote_admin" and call.from_user.id == OWNER_ID:
        SOLO.send_message(call.from_user.id, "أرسل إيدي الشخص لخفضه من المشرفين:")
        SOLO.register_next_step_handler(call.message, process_demote_admin)
    
    # تغيير رتبة مشرف
    elif call.data == "change_admin_role" and call.from_user.id == OWNER_ID:
        msg = SOLO.send_message(call.message.chat.id, "أرسل إيدي المشرف والرتبة الجديدة (بالصيغة: user_id:role):")
        SOLO.register_next_step_handler(msg, process_change_admin_role)
    
    # عرض المشرفين
    elif call.data == "list_admins":
        list_admins(call.message.chat.id)
    
    # القائمة الرئيسية
    elif call.data == "admin_menu":
        send_welcome(call.message)
    
    # إضافة خبر أنمي
    elif call.data == "add_anime_news" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "أرسل خبر الأنمي بالصيغة التالية:\nالعنوان:المحتوى:رابط الصورة (اختياري)")
        SOLO.register_next_step_handler(msg, lambda m: process_add_news(m, 'anime'))
    
    # إضافة خبر مانجا
    elif call.data == "add_manga_news" and call.from_user.id in admins:
        msg = SOLO.send_message(call.message.chat.id, "أرسل خبر المانجا بالصيغة التالية:\nالعنوان:المحتوى:رابط الصورة (اختياري)")
        SOLO.register_next_step_handler(msg, lambda m: process_add_news(m, 'manga'))
    
    # عرض قائمة الأخبار
    elif call.data == "list_news" and call.from_user.id in admins:
        show_news_list(call.message.chat.id)
    
    # ضبط وقت النشر
    elif call.data == "set_publish_time":
        handle_set_publish_time(call)
    
    # تشغيل/إيقاف النشر
    elif call.data == "toggle_publishing" and call.from_user.id in admins:
        current_status = get_setting('publishing_enabled')
        new_status = '0' if current_status == '1' else '1'
        set_setting('publishing_enabled', new_status)
        status_text = "مفعّل" if new_status == '1' else "معطّل"
        SOLO.send_message(call.message.chat.id, f"تم {status_text} النشر التلقائي.")
    
    # إدارة قنوات النشر
    elif call.data == "manage_publish_channels":
        handle_publish_channels_section(call)
    
    # إضافة قناة نشر
    elif call.data == "add_publish_channel":
        msg = SOLO.send_message(call.message.chat.id, "أرسل معرف القناة التي تريد النشر فيها (بصيغة @channelusername):")
        SOLO.register_next_step_handler(msg, process_add_publish_channel)
    
    # حذف قناة نشر
    elif call.data == "remove_publish_channel":
        msg = SOLO.send_message(call.message.chat.id, "أرسل معرف القناة التي تريد إزالتها (بصيغة @channelusername):")
        SOLO.register_next_step_handler(msg, process_remove_publish_channel)
    
    # عرض قنوات النشر
    elif call.data == "list_publish_channels":
        list_publish_channels(call.message.chat.id)
    
    # تعديل وقت نشر الأنمي
    elif call.data == "set_anime_time":
        msg = SOLO.send_message(call.message.chat.id, "أدخل وقت نشر الأنمي الجديد (HH:MM):")
        SOLO.register_next_step_handler(msg, lambda m: process_set_time(m, 'anime'))
    
    # تعديل وقت نشر المانجا
    elif call.data == "set_manga_time":
        msg = SOLO.send_message(call.message.chat.id, "أدخل وقت نشر المانجا الجديد (HH:MM):")
        SOLO.register_next_step_handler(msg, lambda m: process_set_time(m, 'manga'))
    
    # خيار غير معروف
    else:
        SOLO.send_message(call.from_user.id, "خيار غير صالح.")

# قسم معالجة الأقسام المختلفة
def handle_subscription_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕إنشاء كود تفعيل➕", callback_data="add_code"),
        types.InlineKeyboardButton("➖حذف كود تفعيل➖", callback_data="delete_code")
    )
    SOLO.edit_message_text(
        "✨اهلا بك في قسم الاشتراك عن طريق كود تفعيل✨\n ⌤ اضغط على زر إنشاء كود تفعيل لصناعة كود اشتراك في البوت\n ⌤ اضغط على زر حذف كود تفعيل لحذف كود تفعيل ما",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_lock_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔒قفل البوت🔒", callback_data="lock_bot"),
        types.InlineKeyboardButton("🔓فتح البوت🔓", callback_data="unlock_bot")
    )
    SOLO.edit_message_text(
        "✨اهلا بك في قسم التحكم بالبوت✨\n ⌤ اضغط على زر قفل البوت لتظهر رسالة لجميع من يشغل البوت انه تحت الصيانة👨‍🔧\n ⌤ اضغط على زر فتح البوت لكي تتيح للمستخدمين استعمال البوت.",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_ban_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚷حظر مستخدم🚷", callback_data="ban_user"),
        types.InlineKeyboardButton("🎫إلغاء حظر مستخدم🎫", callback_data="unban_user"),
        types.InlineKeyboardButton("📋عرض قائمةالمحظورين📋", callback_data="list_banned")
    )
    SOLO.edit_message_text(
        "✨ اهلا بك في قسم الحظر✨\n ⌤ اضغط على زر حظر مستخدم لحظر أحد المستخدمين من البوت.\n ⌤ اضغط على زر إلغاء خظر مستخدم لإلغاء خظر مستخدم تم حظره مسبقا.\n ⌤ اضغط على زر عرض قائمة المحظورين لرؤيه المستخدمين الذين تم حظرهم.",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_channels_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✨إضافة قناة اشتراك إجباري✨", callback_data="add_channel"),
        types.InlineKeyboardButton("✨حذف قناة اشتراك إجباري✨", callback_data="remove_channel"),
        types.InlineKeyboardButton("✨عرض قنوات الاشتراك الإجباري✨", callback_data="list_channels")
    )
    SOLO.edit_message_text(
        "✨اهلا بك في قسم الاشتراك الاجباري✨\n ⌤ اضغط على زر إضافة قناة اشتراك اجباري لاضافة قناة ما الى الاشتراك الاجباري\n ⌤ اضغط على زر حذف قناة من الاشتراك الاجباري لحذف قناة ما من قنوات الاشتراك الاجباري\n ⌤ اضغط على زر عرض قناة اشتراك اجباري لعرض كل القنوات التي تمت اضافتها الى قائمة قنوات الاشتراك الاجباري.",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_broadcast_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📣إذاعة عامة📣", callback_data="broadcast_all"),
        types.InlineKeyboardButton("🗣️إذاعة خاصة🗣️", callback_data="broadcast_user")
    )
    SOLO.edit_message_text(
        "✨اهلا بك في قسم الإداعة✨\n ⌤ اضغط على زر إذاعة عامه لإرسال رسالة محدده الى كل مستخدمين البوت \n ⌤ اضغط على زر إذاعة خاصة لإرسال رسالة ما إلى مستخدم محدد.",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_admins_section(call):
    admins_list = get_admins()
    admin_text = "👥 قائمة المشرفين:\n"
    for user_id, role in admins_list.items():
        try:
            user = SOLO.get_chat_member(user_id, user_id).user
            username = f"@{user.username}" if user.username else user.first_name
            admin_text += f"{username} - {role}\n"
        except:
            admin_text += f"{user_id} - {role}\n"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("👤 رفع ادمن", callback_data="promote_admin"),
        types.InlineKeyboardButton("🗣️ تنزيل ادمن", callback_data="demote_admin"),
        types.InlineKeyboardButton("🎚️ تغيير رتبة", callback_data="change_admin_role"),
        types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_menu")
    ]
    markup.add(*buttons)
    
    SOLO.edit_message_text(
        admin_text,
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_anime_manga_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("🎎 إضافة خبر أنمي 🎎", callback_data="add_anime_news"),
        types.InlineKeyboardButton("📚 إضافة خبر مانجا 📚", callback_data="add_manga_news"),
        types.InlineKeyboardButton("📋 عرض قائمة الأخبار 📋", callback_data="list_news"),
        types.InlineKeyboardButton("⏱️ ضبط وقت النشر ⏱️", callback_data="set_publish_time"),
        types.InlineKeyboardButton("🔘 تشغيل/إيقاف النشر 🔘", callback_data="toggle_publishing"),
        types.InlineKeyboardButton("📢 إدارة قنوات النشر", callback_data="manage_publish_channels"),
        types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_menu")
    ]
    markup.add(*buttons)
    
    publishing_status = "مفعّل" if get_setting('publishing_enabled') == '1' else "معطّل"
    anime_hour, anime_minute = get_schedule('anime')
    manga_hour, manga_minute = get_schedule('manga')
    anime_time = f"{anime_hour}:{anime_minute:02d}"
    manga_time = f"{manga_hour}:{manga_minute:02d}"
    publish_channels = get_publish_channels()
    channel_count = len(publish_channels)
    
    SOLO.edit_message_text(
        f"✨ اهلا بك في قسم الأنمي والمانجا ✨\n\n"
        f"حالة النشر: {publishing_status}\n"
        f"⏰ وقت نشر الأنمي: {anime_time}\n"
        f"⏳ وقت نشر المانجا: {manga_time}\n"
        f"📢 عدد قنوات النشر: {channel_count}\n"
        f"📺 أخبار الأنمي المخزنة: {get_news_count('anime')}\n"
        f"📚 أخبار المانجا المخزنة: {get_news_count('manga')}\n\n"
        "⌤ اختر أحد الخيارات التالية للتحكم في نشر الأخبار:",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_fetch_auto_news(call):
    msg = SOLO.send_message(call.message.chat.id, "جاري تحديث الأخبار من المصادر...")
    try:
        # جلب أخبار الأنمي
        anime_items = fetch_news('anime')
        for item in anime_items:
            save_news('anime', item['title'], item['content'], item.get('image_url', ''), item.get('source', ''))
        
        # جلب أخبار المانجا
        manga_items = fetch_news('manga')
        for item in manga_items:
            save_news('manga', item['title'], item['content'], item.get('image_url', ''), item.get('source', ''))
        
        SOLO.edit_message_text(
            f"تم تحديث الأخبار بنجاح!\n"
            f"📺 أخبار الأنمي المضافة: {len(anime_items)}\n"
            f"📚 أخبار المانجا المضافة: {len(manga_items)}",
            chat_id=call.message.chat.id,
            message_id=msg.message_id
        )
    except Exception as e:
        SOLO.edit_message_text(
            f"حدث خطأ أثناء تحديث الأخبار: {str(e)}",
            chat_id=call.message.chat.id,
            message_id=msg.message_id
        )

def handle_advanced_settings(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("⏰ تعديل وقت نشر الأنمي", callback_data="set_anime_time"),
        types.InlineKeyboardButton("⏳ تعديل وقت نشر المانجا", callback_data="set_manga_time"),
        types.InlineKeyboardButton("📝 إدارة السجلات", callback_data="logs_section"),
        types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_menu")
    ]
    markup.add(*buttons)
    
    SOLO.edit_message_text(
        "⚙️ الإعدادات المتقدمة:\n"
        "هنا يمكنك ضبط إعدادات البوت المتقدمة",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_set_publish_time(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("⏰ تعديل وقت نشر الأنمي", callback_data="set_anime_time"),
        types.InlineKeyboardButton("⏳ تعديل وقت نشر المانجا", callback_data="set_manga_time"),
        types.InlineKeyboardButton("⬅️ رجوع", callback_data="anime_manga_section")
    ]
    markup.add(*buttons)
    
    anime_hour, anime_minute = get_schedule('anime')
    manga_hour, manga_minute = get_schedule('manga')
    
    SOLO.edit_message_text(
        f"⏱️ إعدادات وقت النشر:\n\n"
        f"وقت نشر الأنمي الحالي: {anime_hour}:{anime_minute:02d}\n"
        f"وقت نشر المانجا الحالي: {manga_hour}:{manga_minute:02d}\n\n"
        "اختر ما تريد تعديله:",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

def handle_publish_channels_section(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة قناة نشر", callback_data="add_publish_channel"),
        types.InlineKeyboardButton("➖ حذف قناة نشر", callback_data="remove_publish_channel"),
        types.InlineKeyboardButton("📋 عرض قنوات النشر", callback_data="list_publish_channels"),
        types.InlineKeyboardButton("⬅️ رجوع", callback_data="anime_manga_section")
    )
    
    SOLO.edit_message_text(
        "📢 إدارة قنوات النشر:\n"
        "هنا يمكنك إضافة أو حذف قنوات النشر",
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

# قسم معالجة الأخبار
def process_add_news(message, news_type):
    try:
        parts = message.text.split(":", 2)
        if len(parts) < 2:
            SOLO.reply_to(message, "الصيغة غير صحيحة. يجب أن تكون: العنوان:المحتوى:رابط الصورة (اختياري)")
            return
        
        title = parts[0].strip()
        content = parts[1].strip()
        image_url = parts[2].strip() if len(parts) > 2 else ""
        
        save_news(news_type, title, content, image_url)
        
        news_type_arabic = "أنمي" if news_type == 'anime' else "مانجا"
        SOLO.reply_to(message, f"تم إضافة خبر {news_type_arabic} بنجاح:\nالعنوان: {title}")
    except Exception as e:
        SOLO.reply_to(message, f"حدث خطأ أثناء إضافة الخبر: {e}")

def show_news_list(chat_id):
    anime_count = get_news_count('anime')
    manga_count = get_news_count('manga')
    
    message = f"📋 إحصائيات الأخبار:\n\n"
    message += f"📺 أخبار الأنمي: {anime_count}\n"
    message += f"📚 أخبار المانجا: {manga_count}\n"
    message += f"📌 المجموع: {anime_count + manga_count}"
    
    SOLO.send_message(chat_id, message)

def process_add_publish_channel(message):
    try:
        channel = message.text.strip()
        if not channel.startswith("@"):
            SOLO.reply_to(message, "يجب أن يبدأ معرف القناة بعلامة @")
            return
        
        if add_publish_channel(channel):
            SOLO.reply_to(message, f"تم إضافة قناة النشر: {channel}")
        else:
            SOLO.reply_to(message, "القناة موجودة مسبقاً")
    except Exception as e:
        SOLO.reply_to(message, f"حدث خطأ أثناء تعيين القناة: {e}")

def process_remove_publish_channel(message):
    try:
        channel = message.text.strip()
        remove_publish_channel(channel)
        SOLO.reply_to(message, f"تم حذف قناة النشر: {channel}")
    except Exception as e:
        SOLO.reply_to(message, f"حدث خطأ أثناء حذف القناة: {e}")

def list_publish_channels(chat_id):
    channels = get_publish_channels()
    if channels:
        response = "قنوات النشر:\n" + "\n".join(channels)
    else:
        response = "لا توجد قنوات نشر"
    SOLO.send_message(chat_id, response)

def process_set_time(message, news_type):
    try:
        time_str = message.text.strip()
        hour, minute = map(int, time_str.split(':'))
        
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            set_schedule(news_type, hour, minute)
            news_type_arabic = "أنمي" if news_type == 'anime' else "مانجا"
            SOLO.reply_to(message, f"✅ تم تحديث وقت نشر {news_type_arabic} إلى {hour}:{minute:02d}")
        else:
            SOLO.reply_to(message, "⛔ وقت غير صحيح. الرجاء إدخال وقت بصيغة HH:MM")
    except:
        SOLO.reply_to(message, "⛔ صيغة الوقت غير صحيحة. الرجاء استخدام الصيغة HH:MM")

def process_change_admin_role(message):
    try:
        user_id, role = message.text.split(":")
        user_id = int(user_id.strip())
        role = role.strip()
        
        if user_id in get_admins():
            add_admin(user_id, role)
            SOLO.reply_to(message, f"تم تغيير رتبة المشرف {user_id} إلى {role}")
        else:
            SOLO.reply_to(message, "المستخدم ليس مشرفاً")
    except Exception as e:
        SOLO.reply_to(message, f"خطأ في المعالجة: {str(e)}")

# باقي الوظائف
def process_activation_code(message):
    user_id = message.from_user.id
    code = message.text.strip()

    if code in activation_codes and activation_codes[code]['usage_count'] < activation_codes[code]['max_usage']:
        expiry_date = datetime.now() + timedelta(days=activation_codes[code]['validity_days'])
        activated_users[user_id] = {'expiry_date': expiry_date}
        activation_codes[code]['usage_count'] += 1

        send_activation_notification(user_id, message.from_user.username, code)
        SOLO.send_message(user_id, "تم تفعيل الكود بنجاح.")

        if activation_codes[code]['usage_count'] >= activation_codes[code]['max_usage']:
            deleted_codes.append(code)
            del activation_codes[code]
    else:
        SOLO.send_message(user_id, "كود غير صالح أو تم استخدامه بالكامل.")

def add_code(message):
    try:
        code_info = message.text.strip().split(":")
        code = code_info[0]
        max_usage = int(code_info[1])
        validity_days = int(code_info[2])

        if code not in activation_codes:
            activation_codes[code] = {
                'max_usage': max_usage,
                'validity_days': validity_days,
                'usage_count': 0
            }
            SOLO.reply_to(message, f"تم إضافة الكود بنجاح. الكود: {code}")
        else:
            SOLO.reply_to(message, "الكود موجود بالفعل.")
    except Exception as e:
        SOLO.reply_to(message, "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة مرة أخرى.")

def delete_code(message):
    global deleted_codes
    code = message.text.strip()
    if code in activation_codes:
        del activation_codes[code]
        deleted_codes.append(code)
        SOLO.reply_to(message, f"تم حذف الكود بنجاح: {code}")
        for user_id, valid_until in list(activated_users.items()):
            if code in deleted_codes or valid_until < datetime.now():
                del activated_users[user_id]
    else:
        SOLO.reply_to(message, "الكود غير موجود. يرجى التحقق والمحاولة مرة أخرى.")

def process_ban_user(message):
    try:
        user_id_to_ban = int(message.text.strip())
        if user_id_to_ban not in banned_users:
            banned_users.append(user_id_to_ban)
            SOLO.reply_to(message, f"تم حظر المستخدم بنجاح. معرف الشخص المحظور: {user_id_to_ban}")
        else:
            SOLO.reply_to(message, "المستخدم محظور بالفعل.")
    except Exception as e:
        SOLO.reply_to(message, "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة مرة أخرى.")

def process_unban_user(message):
    try:
        user_id_to_unban = int(message.text.strip())
        if user_id_to_unban in banned_users:
            banned_users.remove(user_id_to_unban)
            SOLO.reply_to(message, f"تم إلغاء حظر المستخدم بنجاح. معرف الشخص المزال حظره: {user_id_to_unban}")
        else:
            SOLO.reply_to(message, "المستخدم غير محظور.")
    except Exception as e:
        SOLO.reply_to(message, "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة مرة أخرى.")

def list_banned_users(chat_id):
    if banned_users:
        banned_list = "قائمة المستخدمين المحظورين:\n" + "\n".join([str(user_id) for user_id in banned_users])
    else:
        banned_list = "لا يوجد مستخدمون محظورون."
    SOLO.send_message(chat_id, banned_list)

def unban_all_users(chat_id):
    banned_users.clear()
    SOLO.send_message(chat_id, "تم إلغاء حظر جميع المستخدمين.")

def list_channels(chat_id):
    if CHANNELS:
        channels_list = "قائمة قنوات الاشتراك الإجباري:\n" + "\n".join(CHANNELS)
    else:
        channels_list = "لا توجد قنوات اشتراك إجباري."
    SOLO.send_message(chat_id, channels_list)

def add_channel(message):
    try:
        channel_username = message.text.strip()
        if channel_username not in CHANNELS:
            CHANNELS.append(channel_username)
            SOLO.reply_to(message, f"تم إضافة القناة بنجاح. معرف القناة: {channel_username}")
        else:
            SOLO.reply_to(message, "القناة موجودة بالفعل في القائمة.")
    except Exception as e:
        SOLO.reply_to(message, "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة مرة أخرى.")

def remove_channel(message):
    try:
        channel_username = message.text.strip()
        if channel_username in CHANNELS:
            CHANNELS.remove(channel_username)
            SOLO.reply_to(message, f"تم حذف القناة بنجاح. معرف القناة المحذوفة: {channel_username}")
        else:
            SOLO.reply_to(message, "القناة غير موجودة في القائمة.")
    except Exception as e:
        SOLO.reply_to(message, "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة مرة أخرى.")

def broadcast_all_users(message):
    broadcast_message = messag
