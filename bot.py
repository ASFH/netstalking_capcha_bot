from config import TOKEN, TESTS, chat_for_capcha_bot, asdasda
import telebot
import time
import random
import threading

CHAT_ID = asdasda

# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()
CAPTCHA_TIMEOUT = 10 # seconds
LIMIT = 5

bot = telebot.TeleBot(TOKEN)

def kick_user(uid, msg_from_bot):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    time.sleep(CAPTCHA_TIMEOUT)
    if uid in UNSAFE_MESSAGES:
        bot.kick_chat_member(CHAT_ID, uid)
        kicked_user_id = bot.get_updates()[-1].message.message_id
        bot.delete_message(CHAT_ID, kicked_user_id)
        print('removing message {0} from bot'.format(kicked_user_id))
        bot.unban_chat_member(CHAT_ID, uid)
        for msg_id in UNSAFE_MESSAGES[uid]:
            print("removing message", msg_id, "from user", uid)
            bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
        bot.delete_message(CHAT_ID, msg_from_bot)
        print('removing message {0} from bot'.format(msg_from_bot))
        del(UNSAFE_MESSAGES[uid])

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
    if UNSAFE_MESSAGES:
        for uid, messages in UNSAFE_MESSAGES.items():
            for msg_id in messages:
                print("removing message", msg_id, "from user", uid)
                bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
    else:
        bot.send_message(chat_id=CHAT_ID, text="Нечего чистить")

@bot.message_handler(func=lambda m: True, content_types=['new_chat_members'])
def on_user_joins(m):
    """
        sends notification message to each joined user and triggers `kick_user`
    """
    def _gen_captcha_text(name):
        _captcha_text = ("@{0}, please, press the button below within the time amount"
                         " specified, otherwise you will be kicked. Thank you! ({1} sec)")
        return _captcha_text.format(name, CAPTCHA_TIMEOUT)
    if m.from_user.id not in UNSAFE_MESSAGES: 
        UNSAFE_MESSAGES[m.from_user.id] = [m.message_id]
        name = m.from_user.username if m.from_user.username != None else m.from_user.first_name
        msg_from_bot = bot.send_message(
            CHAT_ID,
            _gen_captcha_text(name),
            parse_mode='HTML',
            reply_markup=show_captcha_keyboard()
        )
        #print(msg_from_bot)
        thread = threading.Thread(target=kick_user, args=(m.from_user.id, msg_from_bot.message_id))
        thread.start()

@bot.callback_query_handler(func=lambda message:True)
def answer(message):
    """
        processes new messages; if correct answer was given, removes uid from UNSAFE_MESSAGES
    """
    if message.from_user.id in UNSAFE_MESSAGES and message.data == 'robot':
        bot.edit_message_text(chat_id=CHAT_ID, message_id=message.message.message_id, text='Done')
        del(UNSAFE_MESSAGES[message.from_user.id])
        print(UNSAFE_MESSAGES)

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'animation', 'voice', 'sticker'])
def get_user_messages(message):
    """
        processes new messages; removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
            bot.delete_message(chat_id=CHAT_ID, message_id=message.message_id)
        else:
            UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)

bot.polling()
