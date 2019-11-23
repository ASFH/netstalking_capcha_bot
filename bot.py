"""
    entrypoint and main module with msg handlers
"""

import re
import time
import logging
import threading
from datetime import timedelta, datetime

import sqlite3
import telebot
from tinydb import TinyDB, Query

from data import Graph
from config import config

logging.basicConfig(level=config['loglevel'].get())
LOG = logging.getLogger(__name__)

# setup databases
MSG_CONN = sqlite3.connect(config['db']['messages'].get(str), check_same_thread=False)

MSG_CONN.execute("""CREATE TABLE IF NOT EXISTS messages (
    chat_id integer,
    user_id integer,
    msg_id integer,
    msg_date date,
    content_type text,
    content_data text
)""")

MSG_CONN.commit()
MSG_DB = MSG_CONN.cursor()

USERS_DB = TinyDB(config['db']['users'].get())
User = Query()  #pylint: disable=invalid-name


UNSAFE_MESSAGES = {}
ADMINS = []

# define bot
BOT = telebot.TeleBot(config['token'].get())


def get_message_content(message):  #pylint: disable=too-many-return-statements
    """
        returns actual message content for each message type
    """
    if message.content_type == 'photo':
        return message.photo[0].file_id
    if message.content_type == 'text':
        return message.text
    if message.content_type == 'audio':
        return message.audio.file_id
    if message.content_type == 'document':
        return message.document.file_id
    if message.content_type == 'sticker':
        return message.sticker.thumb.file_id
    if message.content_type == 'video':
        return message.video.file_id
    if message.content_type == 'voice':
        return message.voice.file_id
    return message.text or 'None'


def kick_user(message, msg_from_bot):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    time.sleep(config['captcha']['timeout'].get())
    if message.from_user.id in UNSAFE_MESSAGES:

        BOT.kick_chat_member(message.chat.id, message.from_user.id)
        LOG.info('User %s kicked', message.from_user.first_name)
        BOT.unban_chat_member(message.chat.id, message.from_user.id)

        for msg_id in UNSAFE_MESSAGES[message.from_user.id]:
            LOG.info("removing message %s from user %s", msg_id, message.from_user.id)
            BOT.delete_message(chat_id=message.chat.id, message_id=msg_id)

        BOT.delete_message(message.chat.id, msg_from_bot)
        LOG.info('removing message %s from bot', msg_from_bot)
        del UNSAFE_MESSAGES[message.from_user.id]


def count_users(period, chat=None):
    """
        count users who have wrote in period
    """
    # distinct for unique values
    query = "SELECT DISTINCT user_id FROM messages WHERE"
    if chat:
        query = query + " chat_id = {} AND ".format(chat)
    query = query + " (msg_date BETWEEN ? AND ?)"
    MSG_DB.execute(query, (datetime.now() - timedelta(hours=int(period)), datetime.now()))
    return [i[0] for i in MSG_DB.fetchall()]


def count_messages(chat=None, uid=None, content=None, period=None):
    """
        composes query and returns message stats
    """
    users = []
    counts = []
    query = "SELECT user_id, COUNT(*) FROM messages WHERE "
    if not period:
        period = config['graphs']['period'].get()
    if uid:
        users = [uid]
        query = query + " user_id = {} AND ".format(uid)
    else:
        users = count_users(period, chat)
        query = query + " user_id IN ({}) AND ".format(','.join([str(i) for i in users]))
    if chat:
        query = query + "chat_id = {} AND ".format(chat)
    if content is not None:
        query = query + " content_type = '{}' AND ".format(content)
    query = query + " (msg_date BETWEEN ? AND ?) GROUP BY user_id"
    LOG.debug(query)
    MSG_DB.execute(query, (datetime.now() - timedelta(hours=int(period)), datetime.now()))
    result = MSG_DB.fetchall()
    counts = [i[1] for i in result]
    users = [i[0] for i in result]
    LOG.debug(counts)
    return users, counts


def show_captcha_keyboard():
    """
        generates captcha keyboard
    """
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text='I\'m not a robot', callback_data='robot'))
    return keyboard


@BOT.message_handler(commands=['count'])
def count(message):
    """
        sends counted messages and images from users as a graph
    """
    kwargs = {
        k: v for k, v in [  #pylint: disable=unnecessary-comprehension
            a.split('=') for a in re.findall(
                r'((?:uid|chat|content|period)=[^\s]+)', message.text
            )
        ]
    }
    users, counts = count_messages(**kwargs)
    usernames = []
    for uid in users:
        user = USERS_DB.search(User.user_id == uid)[0]
        name = None
        if user['first_name']:
            name = user['first_name']
            if user['last_name']:
                name += ' ' + user['last_name']
        elif user['username']:
            name = user['username']
        else:
            name = str(uid)
        usernames.append(name)
    counted = Graph(usernames, counts)
    BOT.send_photo(
        message.from_user.id,
        counted.get_stats(),
        'Counted messages from chat: ' + (kwargs.get('chat') if 'chat' in kwargs else '*')
    )


@BOT.message_handler(commands=['cleanup'])
def cleanup_messages(message):
    """
        triggered manually, it cleanups all UNSAFE_MESSAGES
    """
    LOG.debug(UNSAFE_MESSAGES)
    if message.from_user.id in ADMINS:
        if UNSAFE_MESSAGES:
            for uid, messages in UNSAFE_MESSAGES.items():
                for msg_id in messages:
                    LOG.info("removing message %s from user %s", msg_id, uid)
                    BOT.delete_message(chat_id=message.chat.id, message_id=msg_id)
        else:
            BOT.send_message(chat_id=message.chat.id, text="Нечего чистить")
    else:
        if message.from_user.id in UNSAFE_MESSAGES:
            if len(UNSAFE_MESSAGES[message.from_user.id]) >= config['captcha']['msg_limit'].get():
                BOT.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            else:
                UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)


@BOT.message_handler(func=lambda m: True, content_types=['new_chat_members'])
def new_user(message):
    """
        sends notification message to each joined user and triggers `kick_user`
    """
    def _gen_captcha_text(user):
        if user.language_code == "ru":
            _captcha_text = ("[{0}](tg://user?id={1}), хоп-хей! Докажи, что ты не бот "
                             "и нажми, пожалуйста, кнопку в течение указанного времени."
                             " Боты будут кикнуты. Спасибо! ({2} sec)")
        else:
            _captcha_text = ("[{0}](tg://user?id={1}), howdy-ho! Prove you're not a bot "
                             "and please press the button within the specified time."
                             " The bots will be kicked. Thank you! ({2} sec)")
        return _captcha_text.format(user.first_name, user.id, config['captcha']['timeout'].get())

    if not USERS_DB.search(User.user_id == message.from_user.id):
        if message.from_user.id not in UNSAFE_MESSAGES:
            UNSAFE_MESSAGES[message.from_user.id] = [message.message_id]
            msg_from_bot = BOT.send_message(
                message.chat.id,
                _gen_captcha_text(message.from_user),
                parse_mode='Markdown',
                reply_markup=show_captcha_keyboard()
            )
        thread = threading.Thread(target=kick_user, args=(message, msg_from_bot.message_id, ))
        thread.start()


@BOT.callback_query_handler(func=lambda message: True)
def answer(message):
    """
        processes new messages; if correct answer was given, removes uid from UNSAFE_MESSAGES
    """
    if message.from_user.id in UNSAFE_MESSAGES and message.data == 'robot':
        BOT.delete_message(message.message.chat.id, message.message.message_id)
        del UNSAFE_MESSAGES[message.from_user.id]
        LOG.debug(UNSAFE_MESSAGES)
        USERS_DB.insert({
            'user_id': message.from_user.id,
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name
        })
        LOG.info('User %s created', USERS_DB.search(
            User.first_name == message.from_user.first_name
        )[0]['first_name'])
    else:
        BOT.answer_callback_query(message.id, 'Активно только для нового пользователя')


@BOT.message_handler(content_types=[
    'text',
    'photo',
    'video',
    'document',
    'audio',
    'animation',
    'voice',
    'sticker',
    'bot_command'
])
def get_user_messages(message):
    """
        processes all new messages;
        removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= config['captcha']['msg_limit'].get():
            BOT.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)

    MSG_DB.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)", (
        message.chat.id,
        message.from_user.id,
        message.message_id,
        datetime.now(),
        message.content_type,
        get_message_content(message)
    ))
    MSG_CONN.commit()


if __name__ == "__main__":
    for _chat in config['chats'].get():
        if _chat['name'] == config['admins_from'].get():
            for admin in BOT.get_chat_administrators(_chat['id']):
                ADMINS.append(admin.user.id)
    BOT.polling()
