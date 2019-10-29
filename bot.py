from config import TOKEN
import telebot
import time
import random

CHAT_ID = -1001443189124
CHAT_ID2 = -1001446867417
NEW_USERS = list()
MESSAGES_LIST = dict()

bot = telebot.TeleBot(TOKEN)

def show_keyboard(chat_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    buttons = ['test1', 'test2', 'test3']
    random.shuffle(buttons)
    for i in(buttons):
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
    print(MESSAGES_LIST)
    if MESSAGES_LIST:
        for i in MESSAGES_LIST:
            for j in MESSAGES_LIST[i]:
                bot.delete_message(chat_id=CHAT_ID, message_id=j)
        MESSAGES_LIST.clear()
        print(MESSAGES_LIST)
    else:
        bot.send_message(chat_id=CHAT_ID, text="Нечего чистить")

@bot.message_handler(func=lambda m: True, content_types=['new_chat_members'])
def on_user_joins(m):
    if m.from_user.id not in (NEW_USERS): 
        NEW_USERS.append(m.from_user.id)
    print(NEW_USERS)
    bot.send_message(CHAT_ID, 'test_message', parse_mode='HTML', reply_markup=show_keyboard(CHAT_ID))

@bot.callback_query_handler(func=lambda message:True)
def answer(message):
    if message.from_user.id in NEW_USERS and message.data == 'test1':
        bot.edit_message_text(chat_id=CHAT_ID, message_id=message.message.message_id, text='Test done')

@bot.message_handler(content_types=['text'])
def get_user_messages(message):
    if message.from_user.id in NEW_USERS:
        if message.from_user.id in MESSAGES_LIST:
            temp1 = MESSAGES_LIST[message.from_user.id]
            temp1.append(message.message_id)
            MESSAGES_LIST[message.from_user.id] = temp1
        else:
            MESSAGES_LIST[message.from_user.id] = [message.message_id]
        print(MESSAGES_LIST)


bot.polling()