from config import TOKEN, TESTS
import telebot
import time
import random
import threading

CHAT_ID = -1001443189124
CHAT_ID2 = -1001446867417

# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()
CAPTCHA_TIMEOUT = 5 # seconds
LIMIT = 5

bot = telebot.TeleBot(TOKEN)

def kick_user(uid):
    """
        executes in separate thread;
        kicks user and removes its messages after timeout if it didn't pass the exam
    """
    time.sleep(CAPTCHA_TIMEOUT)
    if uid in UNSAFE_MESSAGES:
        bot.kick_chat_member(CHAT_ID, uid)
        bot.unban_chat_member(CHAT_ID, uid)
        for msg_id in UNSAFE_MESSAGES[uid]:
            print("removing message", msg_id, "from user", uid)
            bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
        del(UNSAFE_MESSAGES[uid])
        print(UNSAFE_MESSAGES)

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
        _captcha_text = ("@%s, please, press the button below within the time amount"
                         "specified, otherwise you will be kicked. Thank you! (%s sec)")
        return _captcha_text.format(name, CAPTCHA_TIMEOUT)
    if m.from_user.id not in UNSAFE_MESSAGES: 
        UNSAFE_MESSAGES[m.from_user.id] = []
        #TODO: change `x` to some valuable name
        x = threading.Thread(target=kick_user, args=(m.from_user.id, ))
        x.start()
        name = m.from_user.username if m.from_user.username != None else m.from_user.first_name
        bot.send_message(
            CHAT_ID,
            _gen_captcha_text(name),
            parse_mode='HTML',
            reply_markup=show_captcha_keyboard()
        )

@bot.callback_query_handler(func=lambda message:True)
def answer(message):
    """
        processes new messages; if correct answer was given, removes uid from UNSAFE_MESSAGES
    """
    if message.from_user.id in UNSAFE_MESSAGES and message.data == 'robot':
        bot.edit_message_text(chat_id=CHAT_ID, message_id=message.message.message_id, text='Done')
        del(UNSAFE_MESSAGES[message.from_user.id])
        print(UNSAFE_MESSAGES)

#FIXME: consider switching to any content type since spam messages may have not only text data?
@bot.message_handler(content_types=['text'])
def get_user_messages(message):
    """
        processes new messages; removes those which exceed predefined LIMIT
    """
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
            bot.delete_message(chat_id=CHAT_ID, message_id=message.message_id)
        else:
            #FIXME: why not `UNSAFE_MESSAGES[message.from_user.id].append(message.message_id)` ?
            temp1 = UNSAFE_MESSAGES[message.from_user.id]
            temp1.append(message.message_id)
            UNSAFE_MESSAGES[message.from_user.id] = temp1

bot.polling()
