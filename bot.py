"""
    entrypoint and main module with msg handlers
"""

import os
import re
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

msg_conn.execute("""CREATE TABLE IF NOT EXISTS messages (
    chat_id integer,
    user_id integer,
    msg_id integer,
    msg_date date,
    content_type text,
    content_data text
)""")

msg_conn.commit()
msg_db = msg_conn.cursor()

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


def count_users(period, chat=None):
    """
        count users who have wrote in period
    """
    # distinct for unique values
    query = "SELECT DISTINCT user_id FROM messages WHERE"
    if chat:
        query = query + " chat_id = {} AND ".format(chat)
    query = query + " (date BETWEEN ? AND ?)"
    msg_db.execute(query, (datetime.now() - timedelta(hours=period), datetime.now()))
    return msg_db.fetchall()


def count_messages(chat=None, uid=None, content=None, period=None):
    users = []
    counts = []
    query = "SELECT COUNT(*) FROM messages WHERE "
    if not period:
        period = config.get('graphs', {}).get('period', 1)
    if uid:
        users = [uid]
        query = query + " user_id = {} AND ".format(uid)
    else:
        users = count_users(period, chat)
        query = query + " user_id IN ({}) AND ".format(','.join())
    if chat:
        query = query + "chat_id = {} AND ".format(chat)
    if content is not None:
        query = query + " content_type = '{}' AND ".format(content)
    query = query + " (date BETWEEN ? AND ?)"
    msg_db.execute(query, (datetime.now() - timedelta(hours=period), datetime.now()))
    counts = msg_db.fetchall()
    return users, counts


def show_captcha_keyboard():
    """
        generates captcha keyboard 
    """
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text='I\'m not a robot', callback_data='robot'))
    return keyboard


@bot.message_handler(commands=['count'])
def count(message):
    """
        sends counted messages and images from users as a graph
    """
    kwargs = {
        k: v for k, v in [
            a.split('=') for a in re.findall(
                r'((?:uid|chat|content|period)=[^\s]+)', message.text
            )
        ]
    }
    users, counts = count_messages(**kwargs)
    counted = Graph(users, counts)
    bot.send_photo(
        message.from_user.id,
        counted.get_stats(),
        'Counted messages from chat: Точка Сбора'
    )


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
            if len(UNSAFE_MESSAGES[message.from_user.id]) >= config.get('captcha', {}).get('msg_limit', 5):
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

    if not users_db.search(User.user_id == m.from_user.id):
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
        users_db.insert(
            {'user_id': message.from_user.id, 
            'username': message.from_user.username, 
            'first_name': message.from_user.first_name, 
            'last_name': message.from_user.last_name}
        )
        print('User {0} created'.format(users_db.search(User.first_name == message.from_user.first_name)[0]['first_name']))
    else:
        bot.answer_callback_query(message.id, 'Активно только для нового пользователя')


@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'animation', 'voice', 'sticker', 'bot_command'])
def get_user_messages(message):
    """
        processes all new messages; 
        removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= config.get('captcha', {}).get('msg_limit', 5):
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)

    msg_db.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)", 
        (
            message.chat.id,
            message.from_user.id,
            message.message_id, 
            datetime.now(),
            message.content_type,
            get_message_content(message)
        )
    )
    msg_conn.commit()

bot.polling()
