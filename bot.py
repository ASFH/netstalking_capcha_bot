from config import TOKEN, CHAT_ID1, CHAT_ID2
import telebot
import os
import time
import random
import threading
from threading import Lock
from tinydb import TinyDB, Query
import sqlite3
from datetime import date, timedelta, datetime
from data import Graph

if not os.path.exists("images"):
    os.mkdir("images")

conn = sqlite3.connect("messages.db", check_same_thread = False)
c = conn.cursor()

db = TinyDB('users.json')
User = Query()
bot = telebot.TeleBot(TOKEN)
# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()
CAPTCHA_TIMEOUT = 60 # seconds
HOURS = 1
LIMIT = 5
ADMINS = [i.user.id for i in bot.get_chat_administrators(CHAT_ID1)]
print(ADMINS)
lock= Lock()

'''
"CREATE TABLE messages (chat_id integer, username text, msg_id integer, date text, photo text, 
                        msg_text text, audio text, document text, 
                        sticker text, video text, 
                        voice text, location text, poll text)"
'''
def check_message(message):
    message_data = []
    if message.photo is not None:
        message_data.append(message.photo[0].file_id)
    else:
        message_data.append('False')
    if message.text is not None:      
        message_data.append(message.text)
    else:
        message_data.append('False')
    if message.audio is not None: 
        message_data.append(message.audio.file_id)
    else:
        message_data.append('False')
    if message.document is not None: 
        message_data.append(message.document.file_id)
    else:
        message_data.append('False')
    if message.sticker is not None: 
        message_data.append(message.sticker.thumb.file_id)
    else:
        message_data.append('False')
    if message.video is not None:  
        message_data.append(message.video.file_id)
    else:
        message_data.append('False')
    if message.voice is not None:  
        message_data.append(message.voice.file_id)
    else:
        message_data.append('False')
    return message_data

def add_message(message):
    """
        checks and add every users message into sqlite.db
    """
    message_data = check_message(message)
    print(message_data)
    name = message.from_user.first_name
    name += message.from_user.last_name if message.from_user.last_name is not None else ''
    print(name)
    c.execute("INSERT INTO messages VALUES ({0}, '{1}', {2}, '{3}','{4}', '{5}', '{6}', '{7}', '{8}', '{9}', '{10}', '{11}', '{12}')".format(
        message.chat.id, name, message.message_id, str(datetime.now()), message_data[0], message_data[1], message_data[2], message_data[3], message_data[4], message_data[5], message_data[6], 'False', 'False'
    ))
    conn.commit()

def kick_user(message, msg_from_bot):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    time.sleep(CAPTCHA_TIMEOUT)
    if message.from_user.id in UNSAFE_MESSAGES:

        bot.kick_chat_member(message.chat.id, message.from_user.id)
        print('User {0} kicked'.format(message.from_user.first_name))
        bot.unban_chat_member(message.chat.id, message.from_user.id)

        for msg_id in UNSAFE_MESSAGES[message.from_user.id]:
            print("removing message", msg_id, "from user", message.from_user.id)
            bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            
        bot.delete_message(message.chat.id, msg_from_bot)
        print('removing message {0} from bot'.format(msg_from_bot))
        del(UNSAFE_MESSAGES[message.from_user.id])

def count_users(chat_id):
    """
        count users who have wrote in 5 minutes
    """
    c.execute("SELECT * FROM messages WHERE chat_id = {0} AND (date BETWEEN '{1}' AND '{2}')".format(
        chat_id,
        str(datetime.now() - timedelta(hours=HOURS)), 
        str(datetime.now())
        ))
    all = c.fetchall()
    all_users = list()
    for i in all: 
        if i[1] not in all_users:
            all_users.append(i[1])
        else:
            continue
    return all_users

def count_messages(chat_id, all_users):
    """
        count messages from counted users
    """
    messages_count = list()
    for i in all_users:
        c.execute("SELECT COUNT(*) FROM messages WHERE chat_id = {0} AND (username = '{1}') AND (date BETWEEN '{2}' AND '{3}')".format(
            chat_id,
            i, 
            str(datetime.now() - timedelta(hours=HOURS)), 
            str(datetime.now())
        ))
        messages_count.append(c.fetchone()[0])
    return messages_count

def count_images(chat_id, all_users):
    images_counted = list()
    for i in all_users:
        c.execute("SELECT COUNT(photo) FROM messages WHERE chat_id = {0} AND (username = '{1}') AND (date BETWEEN '{2}' AND '{3}') AND (NOT photo = 'False')".format(
            chat_id,
            i, 
            str(datetime.now() - timedelta(hours=HOURS)), 
            str(datetime.now())
        ))
        images_counted.append(c.fetchone()[0])
    return images_counted

def show_captcha_keyboard():
    """
        generates captcha keyboard 
    """
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text='I\'m not a robot', callback_data='robot'))
    return keyboard

@bot.message_handler(commands=['count_images'])
def cleanup_messages(message):
    """
        sends counted messages and images from users as a graph
    """
    if 'chat1' in message.text:
        all_users = count_users(CHAT_ID1)
        messages_count = count_messages(CHAT_ID1, all_users)
        images_counted = count_images(CHAT_ID1, all_users)
        counted = Graph(all_users, messages_count, images_counted)
        print(images_counted)
        counted.get_images_stat()
        photo = open('images/fig2.png', 'rb')
        bot.send_photo(message.from_user.id, photo, 'Counted messages from chat: Точка Сбора')
    elif 'chat2' in message.text:
        all_users = count_users(CHAT_ID2)
        messages_count = count_messages(CHAT_ID2, all_users)
        images_counted = count_images(CHAT_ID2, all_users)
        counted = Graph(all_users, messages_count, images_counted)
        print(images_counted)
        counted.get_images_stat()
        photo = open('images/fig2.png', 'rb')
        bot.send_photo(message.from_user.id, photo, 'Counted messages from chat: Точка Выхода')

@bot.message_handler(commands=['count'])
def cleanup_messages(message):
    """
        sends counted messages from users as a graph
    """
    if 'chat1' in message.text:
        all_users = count_users(CHAT_ID1)
        messages_count = count_messages(CHAT_ID1, all_users)
        print(all_users)
        print(messages_count)
        users = Graph(all_users, messages_count)
        users.get_users_stat()
        photo = open('images/fig1.png', 'rb')
        bot.send_photo(message.from_user.id, photo, 'Counted messages from chat: Точка Сбора')
    elif 'chat2' in message.text:
        all_users = count_users(CHAT_ID2)
        messages_count = count_messages(CHAT_ID2, all_users)
        print(all_users)
        print(messages_count)
        users = Graph(all_users, messages_count)
        users.get_users_stat()
        photo = open('images/fig1.png', 'rb')
        bot.send_photo(message.from_user.id, photo, 'Counted messages from chat: Точка Выхода')

@bot.message_handler(commands=['cleanup'])
def cleanup_messages(message):
    """
        triggered manually, it cleanups all UNSAFE_MESSAGES
    """
    print(UNSAFE_MESSAGES)
    if message.from_user.id in ADMINS:
        if UNSAFE_MESSAGES:
            for uid, messages in UNSAFE_MESSAGES.items():
                for msg_id in messages:
                    print("removing message", msg_id, "from user", uid)
                    bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
        else:
            bot.send_message(chat_id=message.chat.id, text="Нечего чистить")
    else:
        if message.from_user.id in UNSAFE_MESSAGES:
            if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
                bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            else:
                UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)
        

@bot.message_handler(func=lambda m: True, content_types=['new_chat_members'])
def on_user_joins(m):
    """
        sends notification message to each joined user and triggers `kick_user`
    """
    def _gen_captcha_text(user):
        if user.language_code == "ru":
            _captcha_text = ("[{0}](tg://user?id={1}), хоп-хей! Докажи, что ты не бот и нажми, пожалуйста, кнопку в течение указанного времени."
                            " Боты будут кикнуты. Спасибо! ({2} sec)")
        else:
            _captcha_text = ("[{0}](tg://user?id={1}), howdy-ho! Prove you're not a bot and please press the button within the specified time."
                            " The bots will be kicked. Thank you! ({2} sec)")
        return _captcha_text.format(user.first_name, user.id, CAPTCHA_TIMEOUT)

    if not db.search(User.user_id == m.from_user.id):
        if m.from_user.id not in UNSAFE_MESSAGES: 
            UNSAFE_MESSAGES[m.from_user.id] = [m.message_id]
            name = m.from_user.first_name if m.from_user.first_name != None else m.from_user.username
            uid = m.from_user.id
            msg_from_bot = bot.send_message(
                m.chat.id,
                _gen_captcha_text(m.from_user),
                parse_mode='Markdown',
                reply_markup=show_captcha_keyboard()
            )
        thread = threading.Thread(target=kick_user, args=(m, msg_from_bot.message_id, ))
        thread.start()

@bot.callback_query_handler(func=lambda message:True)
def answer(message):
    """
        processes new messages; if correct answer was given, removes uid from UNSAFE_MESSAGES
    """
    if message.from_user.id in UNSAFE_MESSAGES and message.data == 'robot':
        bot.delete_message(message.message.chat.id, message.message.message_id)
        del(UNSAFE_MESSAGES[message.from_user.id])
        print(UNSAFE_MESSAGES)
        db.insert(
            {'user_id': message.from_user.id, 
            'username': message.from_user.username, 
            'first_name': message.from_user.first_name, 
            'last_name': message.from_user.last_name}
        )
        print('User {0} created'.format(db.search(User.first_name == message.from_user.first_name)[0]['first_name']))
    else:
        bot.answer_callback_query(message.id, 'Активно только для нового пользователя')

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'animation', 'voice', 'sticker', 'bot_command'])
def get_user_messages(message):
    """
        processes new messages; removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)

    add_message(message)

bot.polling()
