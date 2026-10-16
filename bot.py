from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import DatabaseManager, create_collage, get_score_image_paths, hide_img, BASE_DIR
from io import BytesIO
import cv2
import schedule
import threading
import time
from config import API_TOKEN, DATABASE

bot = TeleBot(API_TOKEN)
manager = DatabaseManager(DATABASE)

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    prize_id = int(call.data)
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if manager.get_winners_count(prize_id) < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            img = manager.get_prize_img(prize_id)
            with open(BASE_DIR / 'img' / img, 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Поздравляем! Ты получил картинку!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!)")


def send_message():
    prize = manager.get_random_prize()
    if prize is None:
        print('Неиспользованные картинки закончились. Добавь новые в img/ и запусти logic.py')
        return
    prize_id = prize[0]
    img = manager.get_prize_img(prize_id)
    manager.mark_prize_used(prize_id)
    hide_img(img)
    for user in manager.get_users():
        with open(BASE_DIR / 'hidden_img' / img, 'rb') as photo:
            bot.send_photo(user, photo, reply_markup=gen_markup(id = prize_id))
        

def shedule_thread():
    schedule.every().minute.do(send_message) # Здесь ты можешь задать периодичность отправки картинок
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['get_my_score'])
def get_my_score(message):
    try:
        paths = get_score_image_paths(manager, message.chat.id)
        if not paths:
            bot.send_message(message.chat.id, 'Пока нет картинок для коллажа.')
            return
        collage = create_collage(paths)
        ok, encoded = cv2.imencode('.jpg', collage)
        if not ok:
            raise ValueError('Не удалось закодировать коллаж')
    except (OSError, ValueError, cv2.error):
        bot.send_message(message.chat.id, 'Не удалось создать коллаж. Проверьте папки img и hidden_img.')
        return
    with BytesIO(encoded.tobytes()) as photo:
        photo.name = 'my_score.jpg'
        bot.send_photo(message.chat.id, photo,
                       caption='Твоя коллекция! Полученные призы открыты, остальные скрыты.')


@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating()
    res = [f'| @{str(x[0]):<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегестрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")
        


def polling_thread():
    bot.infinity_polling()

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    thread_polling = threading.Thread(target=polling_thread)
    thread_schedule = threading.Thread(target=shedule_thread)

    thread_polling.start()
    thread_schedule.start()
  
