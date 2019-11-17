"""
    main entrypoint
"""

# standard:
import threading
import time
# 3rd-party:
import telebot
from tinydb import TinyDB, Query
# local:
from config import TOKEN, CHAT_ID

DB = TinyDB('users.json')
User = Query()  #pylint: disable=invalid-name
BOT = telebot.TeleBot(TOKEN)
# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()
CAPTCHA_TIMEOUT = 60 # seconds
LIMIT = 5
ADMINS = [i.user.id for i in BOT.get_chat_administrators(CHAT_ID)]
print(ADMINS)

def kick_user(message, msg_from_bot):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    time.sleep(CAPTCHA_TIMEOUT)
    if message.from_user.id in UNSAFE_MESSAGES:

        BOT.kick_chat_member(message.chat.id, message.from_user.id)
        print('User {0} kicked'.format(message.from_user.first_name))
        BOT.unban_chat_member(message.chat.id, message.from_user.id)

        for msg_id in UNSAFE_MESSAGES[message.from_user.id]:
            print("removing message", msg_id, "from user", message.from_user.id)
            BOT.delete_message(chat_id=message.chat.id, message_id=msg_id)

        BOT.delete_message(message.chat.id, msg_from_bot)
        print('removing message {0} from bot'.format(msg_from_bot))
        del UNSAFE_MESSAGES[message.from_user.id]

def show_captcha_keyboard():
    """
        generates captcha keyboard
    """
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text='I\'m not a robot', callback_data='robot'))
    return keyboard

@BOT.message_handler(commands=['cleanup'])
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
                    BOT.delete_message(chat_id=message.chat.id, message_id=msg_id)
        else:
            BOT.send_message(chat_id=message.chat.id, text="Нечего чистить")
    else:
        if message.from_user.id in UNSAFE_MESSAGES:
            if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
                BOT.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            else:
                UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)


@BOT.message_handler(func=lambda message: True, content_types=['new_chat_members'])
def on_user_joins(message):
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
        return _captcha_text.format(user.first_name, user.id, CAPTCHA_TIMEOUT)

    if not DB.search(User.user_id == message.from_user.id):
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
        print(UNSAFE_MESSAGES)
        DB.insert({
            'user_id': message.from_user.id,
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name
        })
        print('User {0} created'.format(
            DB.search(User.first_name == message.from_user.first_name)[0]['first_name']
        ))
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
        processes new messages; removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
            BOT.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)

BOT.polling()
