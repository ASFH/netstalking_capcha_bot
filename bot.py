import threading
import time
import logging

import telebot
from peewee import DoesNotExist
from telebot.apihelper import ApiException

from config import config
from models import Message, User, db

db.create_tables([User, Message])

logging.basicConfig(level=config["loglevel"].get())
LOG = logging.getLogger(__name__)

UNSAFE_MESSAGES = dict()
ADMINS = list()
MESSAGES = dict()

# define bot
bot = telebot.TeleBot(config["token"].get())
messages_to_delete = []
LOG_MESSAGES = False
LOG_MESSAGES_CHATID = None


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


def kick_user(message, msg_from_bot):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    LOG.info("Waiting for member %s to solve captcha", User.from_message(message)._repr())
    time.sleep(config["captcha"]["timeout"].get())
    if message.from_user.id in UNSAFE_MESSAGES:

        bot.kick_chat_member(message.chat.id, message.from_user.id)
        LOG.info("User %s kicked", User.from_message(message)._repr())
        bot.unban_chat_member(message.chat.id, message.from_user.id)

        for msg_id in UNSAFE_MESSAGES[message.from_user.id]:
            LOG.info("removing message %s from user %s", msg_id, User.from_message(message)._repr())
            bot.delete_message(chat_id=message.chat.id, message_id=msg_id)

        LOG.info("removing message %s from bot", msg_from_bot)
        bot.delete_message(message.chat.id, msg_from_bot)
        del UNSAFE_MESSAGES[message.from_user.id]


def check_access(bot_function):

    def a_wrapper_accepting_arguments(message):
        LOG.info("Checking if %s is allowed to call %s", User.from_message(message)._repr(), getattr(bot_function, '__name__', repr(callable)))
        if message.from_user.id in ADMINS:
            bot_function(message)
        else:
            LOG.warning("Restricted")

    return a_wrapper_accepting_arguments


@bot.message_handler(func=lambda m: True, content_types=["new_chat_members"])
def new_user(message):
    """
        sends notification message to each joined user and triggers `kick_user`
    """
    LOG.info("Handling new chat member")
    def _gen_captcha_text(user):
        _captcha_text = (
            "[{0}](tg://user?id={1}), хоп-хей! Докажи, что ты не бот "
            "и нажми, пожалуйста, кнопку в течение указанного времени."
            " Боты будут кикнуты. Спасибо! ({2} sec)"
        )
        return _captcha_text.format(
            user.first_name, user.id, config["captcha"]["timeout"].get()
        )

    try:
        user = User.select().where(User.uid == message.from_user.id).get()
        LOG.info("Known member %s", User.from_message(message)._repr())
    except DoesNotExist:
        LOG.info("Member with %s is unknown, sending captcha", User.from_message(message)._repr())
        if message.from_user.id not in UNSAFE_MESSAGES:
            UNSAFE_MESSAGES[message.from_user.id] = [message.message_id]
            msg_from_bot = bot.send_message(
                message.chat.id,
                _gen_captcha_text(message.from_user),
                parse_mode="Markdown",
                reply_markup=show_captcha_keyboard(),
            )
            thread = threading.Thread(
                target=kick_user, args=(message, msg_from_bot.message_id,)
            )
            thread.start()


@bot.callback_query_handler(func=lambda message: True)
def answer(message):
    """
        processes new messages; if correct answer was given, removes uid from UNSAFE_MESSAGES
    """
    if message.from_user.id in UNSAFE_MESSAGES and message.data == "robot":
        LOG.info("Member %s passed captcha", User.from_message(message)._repr())
        bot.delete_message(message.message.chat.id, message.message.message_id)
        del UNSAFE_MESSAGES[message.from_user.id]
        User.from_message(message)
    else:
        bot.answer_callback_query(message.id, "Активно только для нового пользователя")


@bot.message_handler(commands=['start'])
@check_access
def some_start_handler(message):
    global LOG_MESSAGES
    global LOG_MESSAGES_CHATID
    LOG.info("Handling /start command")
    if LOG_MESSAGES:
        LOG.warning("Already logging messages, declined")
        bot.send_message(message.chat.id, f"Already logging messages in chat {LOG_MESSAGES_CHATID}")
    else:
        LOG.info("Logging enabled by %s (in chat %s)", User.from_message(message)._repr(), message.chat.id)
        LOG_MESSAGES = True
        LOG_MESSAGES_CHATID = message.chat.id


@bot.message_handler(commands=['stop'])
@check_access
def some_stop_handler(message):
    global LOG_MESSAGES
    global LOG_MESSAGES_CHATID
    global messages_to_delete
    LOG.info("Handling /stop command")
    if not LOG_MESSAGES:
        LOG.warning("Not logging messages, declined")
        bot.send_message(message.chat.id, "Not logging messages")
    else:
        LOG.info("Logging disabled by %s (in chat %s)", User.from_message(message)._repr(), message.chat.id)
        LOG_MESSAGES = False
        messages = Message.select().where((Message.date << messages_to_delete) & (Message.chat_id == config["chats"]["ts"].get()))

        for message in messages:
            LOG.info("Forwarding and removing message %s", message.msg_id)
            bot.forward_message(config["chats"]["tv"].get(), config["chats"]["ts"].get(), message.msg_id)
            bot.delete_message(config["chats"]["ts"].get(), message.msg_id)
        LOG.info("Flushing messages_to_delete")
        messages_to_delete = []



@bot.message_handler(func=lambda m: LOG_MESSAGES == True and LOG_MESSAGES_CHATID == m.chat.id)
def messages_to_delete_handler(message):
    global messages_to_delete
    messages_to_delete.append(message.forward_date)
    LOG.info("message logged (total %s)", len(messages_to_delete))


@bot.message_handler(
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
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)
    else:
        Message.from_message(message)


if __name__ == "__main__":
    for c_name, c_id in config["chats"].get().items():
        if c_name == config["admins_from"].get():
            for admin in bot.get_chat_administrators(c_id):
                ADMINS.append(admin.user.id)
    try:
        while True:
            try:
                bot.polling(none_stop=True, timeout=60)
            except Exception as e:
                bot.stop_polling()
                time.sleep(10)
    except (KeyboardInterrupt, SystemExit):
        raise
