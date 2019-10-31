from config import TOKEN, TESTS
import telebot
import time
import random

CHAT_ID = -1001443189124
CHAT_ID2 = -1001446867417

# dict {uid: [msg_id, ..]}
UNSAFE_MESSAGES = dict()
# dict {uid: {question: answer}}
QUESTION_FOR_USER = dict()
QUESTION = list()
GENERATED = list()

bot = telebot.TeleBot(TOKEN)

def generate_buttons(uid):
    random_buttons = ['3', '2', '8', '1', '4', '5']
    random.shuffle(random_buttons)
    GENERATED.append(random_buttons[1])
    GENERATED.append(random_buttons[3])
    print(QUESTION_FOR_USER)
    GENERATED.append(str(list(QUESTION_FOR_USER[uid].values())[0]))
    random.shuffle(GENERATED)

def show_keyboard(chat_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    print(GENERATED)
    for i in GENERATED:
        keyboard.add(telebot.types.InlineKeyboardButton(text=i, callback_data=i))
    GENERATED.clear()
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
    q, a = random.choice(list(TESTS.items()))
    QUESTION.append(q)
    QUESTION.append(str(a))
    if m.from_user.id in UNSAFE_MESSAGES:
        QUESTION_FOR_USER[m.from_user.id] = {QUESTION[0] : QUESTION[1]}
        generate_buttons(m.from_user.id)
        print(QUESTION_FOR_USER)
    QUESTION.clear()
    bot.send_message(CHAT_ID, str(list(QUESTION_FOR_USER[m.from_user.id].keys())[0]), parse_mode='HTML', reply_markup=show_keyboard(CHAT_ID))

@bot.callback_query_handler(func=lambda message:True)
def answer(message):
    if message.from_user.id in UNSAFE_MESSAGES and message.data == str(list(QUESTION_FOR_USER[message.from_user.id].values())[0]):
        bot.edit_message_text(chat_id=CHAT_ID, message_id=message.message.message_id, text='Test done')
        del(QUESTION_FOR_USER[message.from_user.id])
        del(UNSAFE_MESSAGES[message.from_user.id])
        print(QUESTION_FOR_USER)
        print(UNSAFE_MESSAGES)

@bot.message_handler(content_types=['text'])
def get_user_messages(message):
    if message.from_user.id in UNSAFE_MESSAGES:
        temp1 = UNSAFE_MESSAGES[message.from_user.id]
        temp1.append(message.message_id)
        UNSAFE_MESSAGES[message.from_user.id] = temp1

bot.polling()
