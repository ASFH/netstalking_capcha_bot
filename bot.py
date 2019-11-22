"""
    entrypoint and main module with msg handlers
"""

import os
import time
import random
import threading
from threading import Lock
from datetime import date, timedelta, datetime

import yaml
import sqlite3
import telebot
from tinydb import TinyDB, Query

from data import Graph


config = yaml.safe_load('config.yaml')

# setup databases
msg_conn = sqlite3.connect(config.get('db', {}).get('messages', 'messages.db'), check_same_thread = False)
msg_db = msg_conn.cursor()

msg_db.execute("""CREATE TABLE IF NOT EXISTS messages (
    chat_id integer, 
    username text, 
    msg_id integer, 
    date text,
    content_type text,
    content_data text
)""")

users_db = TinyDB(config.get('db', {}).get('users', 'users.json'))
User = Query()

# define bot
bot = telebot.TeleBot(config.get('token'))
# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()

# obtain admins list from CHAT_ID
ADMINS = [i.user.id for i in bot.get_chat_administrators(config.get('adm_chat'))]
print(ADMINS)


def get_message_content(message):
    if message.content_type == 'photo':
        return message.photo[0].file_id
    elif message.content_type == 'text':
        return message.text
    elif message.content_type == 'audio':
        return message.audio.file_id
    elif message.content_type == 'document':
        return message.document.file_id
    elif message.content_type == 'sticker':
        return message.sticker.thumb.file_id
    elif message.content_type == 'video':
        return message.video.file_id
    elif message.content_type == 'voice':
        return message.voice.file_id

def add_message(message):
    """
        checks and add every users message into sqlite.db
    """
    name = message.from_user.first_name
    name += ' ' + (message.from_user.last_name if message.from_user.last_name is not None else '')
    print(name)
    msg_db.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)", 
        (
            message.chat.id,
            name,
            message.message_id, 
            str(datetime.now()),
            message.content_type,
            get_message_content(message)
        )
    )
    msg_conn.commit()

def kick_user(message, msg_from_bot):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    time.sleep(config.get('captcha', {}).get('timeout', 30))
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
        count users who have wrote in period
    """
    # distinct for unique values
    msg_db.execute("SELECT DISTINCT username FROM messages WHERE chat_id = ? AND (date BETWEEN ? AND ?)", (
        chat_id,
        str(datetime.now() - timedelta(hours=config.get('graphs', {}).get('period', 1))), 
        str(datetime.now())
        )
    )
    return msg_db.fetchall()

def count_by_type(chat_id, all_users, content_type=None):
    counted = list()
    query = "SELECT COUNT(*) FROM messages WHERE chat_id = ? AND username = ? AND (date BETWEEN ? AND ?)"
    if content_type is not None:
        query = query + " AND content_type = '{}'".format(content_type) 
    for i in all_users:
        msg_db.execute(
            query, (
                chat_id,
                i,
                datetime.now() - timedelta(hours=config.get('graphs', {}).get('period', 1)), 
                datetime.now()
            )
        )
        counted.append(msg_db.fetchone()[0])
    return counted

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
        bot.send_photo(
            message.from_user.id,
            counted.get_images_stat(),
            'Counted messages from chat: Точка Сбора'
        )
    elif 'chat2' in message.text:
        all_users = count_users(CHAT_ID2)
        messages_count = count_messages(CHAT_ID2, all_users)
        images_counted = count_images(CHAT_ID2, all_users)
        counted = Graph(all_users, messages_count, images_counted)
        print(images_counted)
        bot.send_photo(
            message.from_user.id,
            counted.get_images_stat(),
            'Counted messages from chat: Точка Выхода'
        )

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
        return _captcha_text.format(user.first_name, user.id, config.get('captcha', {}).get('timeout', 30))

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
        processes all new messages; 
        removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)

    add_message(message)

bot.polling()
