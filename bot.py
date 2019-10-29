from config import TOKEN
import telebot
import time
import random

CHAT_ID = -1001443189124
CHAT_ID2 = -1001446867417

# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()

bot = telebot.TeleBot(TOKEN)

def show_keyboard(chat_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    buttons = ['test1', 'test2', 'test3']
    random.shuffle(buttons)
    for i in buttons:
        keyboard.add(telebot.types.InlineKeyboardButton(text=i, callback_data=i))
    
    return keyboard

@bot.message_handler(commands=['start', 'help'])
def test_func(message):
    print(MESSAGES_LIST)
    for i in MESSAGES_LIST:
        print(MESSAGES_LIST)
        print(i)
        bot.send_message(chat_id=CHAT_ID, text=str(i))

@bot.message_handler(commands=['cleanup'])
def cleanup_messages(message):
    print(UNSAFE_MESSAGES)
    if UNSAFE_MESSAGES:
        for uid, messages in UNSAFE_MESSAGES.items():
            for msg_id in messages:
                print("removing message", msg_id, "from user", uid)
                bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
        MESSAGES_LIST.clear()
    else:
        bot.send_message(chat_id=CHAT_ID, text="Нечего чистить")

@bot.message_handler(func=lambda m: True, content_types=['new_chat_members'])
def on_user_joins(m):
    if m.from_user.id not in UNSAFE_MESSAGES: 
        UNSAFE_MESSAGES[m.from_user.id] = []
    print(UNSAFE_MESSAGES)
    bot.send_message(CHAT_ID, 'test_message', parse_mode='HTML', reply_markup=show_keyboard(CHAT_ID))

@bot.callback_query_handler(func=lambda message:True)
def answer(message):
    if message.from_user.id in UNSAFE_MESSAGES and message.data == 'test1':
        bot.edit_message_text(chat_id=CHAT_ID, message_id=message.message.message_id, text='Test done')

@bot.message_handler(content_types=['text'])
def get_user_messages(message):
    if message.from_user.id in UNSAFE_MESSAGES:
        temp1 = UNSAFE_MESSAGES[message.from_user.id]
        temp1.append(message.message_id)
        UNSAFE_MESSAGES[message.from_user.id] = temp1
    else:
        UNSAFE_MESSAGES[message.from_user.id] = [message.message_id]
    print(UNSAFE_MESSAGES)

bot.polling()
