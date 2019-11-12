from config import TOKEN, TESTS
import telebot
import time
import random
import threading

CHAT_ID = -1001443189124
CHAT_ID2 = -1001446867417

# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()
LIMIT = 5

bot = telebot.TeleBot(TOKEN)

def kick_user(uid):
    time.sleep(30)   
    if uid in UNSAFE_MESSAGES:
        bot.kick_chat_member(CHAT_ID, uid)
        bot.unban_chat_member(CHAT_ID, uid)
        for msg_id in UNSAFE_MESSAGES[uid]:
            print("removing message", msg_id, "from user", uid)
            bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
        del(UNSAFE_MESSAGES[uid])
        print(UNSAFE_MESSAGES)

def show_keyboard(chat_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text='I\'m not a robot', callback_data='robot'))
    return keyboard

@bot.message_handler(commands=['cleanup'])
def cleanup_messages(message):
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
    if m.from_user.id not in UNSAFE_MESSAGES: 
        UNSAFE_MESSAGES[m.from_user.id] = []
        x = threading.Thread(target=kick_user, args=(m.from_user.id,))
        x.start()
        name = m.from_user.username if m.from_user.username != None else m.from_user.first_name
        bot.send_message(CHAT_ID, '@' + str(name) + ' please, press the button below within the time amount specified, otherwise you will be kicked. Thank you! (60 sec)', parse_mode='HTML', reply_markup=show_keyboard(CHAT_ID))

@bot.callback_query_handler(func=lambda message:True)
def answer(message):
    if message.from_user.id in UNSAFE_MESSAGES and message.data == 'robot':
        bot.edit_message_text(chat_id=CHAT_ID, message_id=message.message.message_id, text='Done')
        del(UNSAFE_MESSAGES[message.from_user.id])
        print(UNSAFE_MESSAGES)

@bot.message_handler(content_types=['text'])
def get_user_messages(message):
    if message.from_user.id in UNSAFE_MESSAGES:
        if len(UNSAFE_MESSAGES[message.from_user.id]) >= LIMIT:
            bot.delete_message(chat_id=CHAT_ID, message_id=message.message_id)
        else:
            temp1 = UNSAFE_MESSAGES[message.from_user.id]
            temp1.append(message.message_id)
            UNSAFE_MESSAGES[message.from_user.id] = temp1

bot.polling()
