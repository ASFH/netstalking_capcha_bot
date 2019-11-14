from config import TOKEN, CHAT_ID
import telebot
import time
import random
import threading
from tinydb import TinyDB, Query

db = TinyDB('users.json')
User = Query()
bot = telebot.TeleBot(TOKEN)
# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()
CAPTCHA_TIMEOUT = 60 # seconds
LIMIT = 5
ADMINS = [i.user.id for i in bot.get_chat_administrators(CHAT_ID)]
print(ADMINS)

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

def show_captcha_keyboard():
    """
        generates captcha keyboard 
    """
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text='I\'m not a robot', callback_data='robot'))
    return keyboard

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
        _captcha_text = ("[{0}](tg://user?id={1}), пожалуйста, нажмите кнопку ниже в течение указанного времени,"
                         " в противном случае вы будете кикнуты. Спасибо! ({2} sec)")
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

bot.polling()
