"""
    entrypoint and main module with msg handlers
"""

import logging
import re
import threading
import time
from datetime import datetime, timedelta

import telebot
from peewee import DoesNotExist, fn

from config import config
from data import Graph
from models import Message, User, db

db.create_tables([User, Message])

logging.basicConfig(level=config["loglevel"].get())
LOG = logging.getLogger(__name__)

LOG.debug(config["chats"].get())


UNSAFE_MESSAGES = {}
ADMINS = []


# define bot
BOT = telebot.TeleBot(config["token"].get())


def kick_user(message, msg_from_bot):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    time.sleep(config["captcha"]["timeout"].get())
    if message.from_user.id in UNSAFE_MESSAGES:

        BOT.kick_chat_member(message.chat.id, message.from_user.id)
        LOG.info("User %s kicked", message.from_user.first_name)
        BOT.unban_chat_member(message.chat.id, message.from_user.id)

        for msg_id in UNSAFE_MESSAGES[message.from_user.id]:
            LOG.info("removing message %s from user %s", msg_id, message.from_user.id)
            BOT.delete_message(chat_id=message.chat.id, message_id=msg_id)

        BOT.delete_message(message.chat.id, msg_from_bot)
        LOG.info("removing message %s from bot", msg_from_bot)
        del UNSAFE_MESSAGES[message.from_user.id]


def count_users(period, chat=None):
    """
        count users who have wrote in period
    """
    # distinct for unique values
    query = (
        Message.select(User.uid)
        .join(User)
        .where(
            Message.date.between(
                datetime.now() - timedelta(hours=int(period)), datetime.now()
            )
        )
    )
    if chat:
        query = query.where(Message.chat_id == chat)
    query = query.distinct()
    return [message.user.uid for message in query]


def count_messages(chat=None, uid=None, content=None, period=None):
    """
        composes query and returns message stats
    """
    query = Message.select(User, fn.COUNT(Message.msg_id).alias("msg_count")).join(User)
    if not period:
        period = config["graphs"]["period"].get()
    if chat:
        chat_id = config["chats"].get().get(chat)
        if chat_id:
            query = query.where(Message.chat_id == chat_id)
            chat = chat_id
    if uid:
        users = [uid]
        query = query.where(User.uid == uid)
    else:
        users = count_users(period, chat)
        query = query.where(User.uid << users)
    if content is not None:
        query = query.where(Message.content_type == content)
    query = query.where(
        Message.date.between(
            datetime.now() - timedelta(hours=int(period)), datetime.now()
        )
    )
    query = query.group_by(User.uid)
    query = query.order_by(fn.COUNT(Message.msg_id).desc())
    LOG.debug(query)
    return query


def show_captcha_keyboard():
    """
        generates captcha keyboard
    """
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            text="I'm not a robot", callback_data="robot"
        )
    )
    return keyboard


@BOT.message_handler(commands=["count"])
def count(message):
    """
        sends counted messages and images from users as a graph
    """
    kwargs = {
        k: v
        for k, v in [  # pylint: disable=unnecessary-comprehension
            a.split("=")
            for a in re.findall(r"((?:uid|chat|content|period)=[^\s]+)", message.text)
        ]
    }
    usernames = []
    counts = []
    for row in count_messages(**kwargs):
        name = "None"
        if row.user.first_name:
            name = row.user.first_name
            if row.user.last_name:
                name += " " + row.user.last_name
        elif row.user.username:
            name = row.user.username
        else:
            name = "id_" + str(row.user.uid)
        usernames.append(name)
        counts.append(row.msg_count)
    counted = Graph(usernames, counts)
    BOT.send_photo(
        message.from_user.id,
        counted.get_stats(),
        "Counted messages from chat: "
        + (kwargs.get("chat") if "chat" in kwargs else "*"),
    )


@BOT.message_handler(commands=["cleanup"])
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
            if (
                len(UNSAFE_MESSAGES[message.from_user.id])
                >= config["captcha"]["msg_limit"].get()
            ):
                BOT.delete_message(
                    chat_id=message.chat.id, message_id=message.message_id
                )
            else:
                UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)


@BOT.message_handler(func=lambda m: True, content_types=["new_chat_members"])
def new_user(message):
    """
        sends notification message to each joined user and triggers `kick_user`
    """

    def _gen_captcha_text(user):
        if user.language_code == "ru":
            _captcha_text = (
                "[{0}](tg://user?id={1}), хоп-хей! Докажи, что ты не бот "
                "и нажми, пожалуйста, кнопку в течение указанного времени."
                " Боты будут кикнуты. Спасибо! ({2} sec)"
            )
        else:
            _captcha_text = (
                "[{0}](tg://user?id={1}), howdy-ho! Prove you're not a bot "
                "and please press the button within the specified time."
                " The bots will be kicked. Thank you! ({2} sec)"
            )
        return _captcha_text.format(
            user.first_name, user.id, config["captcha"]["timeout"].get()
        )

    try:
        user = User.select().where(User.uid == message.from_user.id).get()
    except DoesNotExist:
        if message.from_user.id not in UNSAFE_MESSAGES:
            UNSAFE_MESSAGES[message.from_user.id] = [message.message_id]
            msg_from_bot = BOT.send_message(
                message.chat.id,
                _gen_captcha_text(message.from_user),
                parse_mode="Markdown",
                reply_markup=show_captcha_keyboard(),
            )
            thread = threading.Thread(
                target=kick_user, args=(message, msg_from_bot.message_id,)
            )
            thread.start()


@BOT.callback_query_handler(func=lambda message: True)
def answer(message):
    """
        processes new messages; if correct answer was given, removes uid from UNSAFE_MESSAGES
    """
    if message.from_user.id in UNSAFE_MESSAGES and message.data == "robot":
        BOT.delete_message(message.message.chat.id, message.message.message_id)
        del UNSAFE_MESSAGES[message.from_user.id]
        LOG.debug(UNSAFE_MESSAGES)
        User.from_message(message)
        BOT.restrict_chat_member(
            message.message.chat.id, 
            message.from_user.id, 
            datetime.now() + timedelta(days=10),
            can_send_messages=True,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
    else:
        BOT.answer_callback_query(message.id, "Активно только для нового пользователя")


@BOT.message_handler(
    content_types=[
        "text",
        "photo",
        "video",
        "document",
        "audio",
        "animation",
        "voice",
        "sticker",
        "bot_command",
    ]
)
def get_user_messages(message):
    """
        processes all new messages;
        removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if (
            len(UNSAFE_MESSAGES[message.from_user.id])
            >= config["captcha"]["msg_limit"].get()
        ):
            BOT.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)
    else:
        Message.from_message(message)
    # Vahter 1.0
    


if __name__ == "__main__":
    for c_name, c_id in config["chats"].get().items():
        if c_name == config["admins_from"].get():
            for admin in BOT.get_chat_administrators(c_id):
                ADMINS.append(admin.user.id)
    try:
        while True:
            try:
                BOT.polling(none_stop=True, timeout=60)
            except Exception as e:
                logging.exception(e)
                BOT.stop_polling()
                time.sleep(10)
    except (KeyboardInterrupt, SystemExit):
        raise
