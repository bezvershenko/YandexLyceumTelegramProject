from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

import requests

from maps_api.request import geocoder_request, map_request
from maps_api.geocoder import get_pos, get_bbox, get_country_code, get_city, check_response
from maps_api.static import get_static_map

from news_parser.parser import parse_news

from weather.weather import get_current_weather, get_forecast_weather

from schedule_api.airports import airs
from schedule_api.schedule import get_flights

from speech_api.speech_analyze import speech_analyze
from speech_api.xml_parser import speech_parser

from config import TELEGRAM_TOKEN, SPEECH_TOKEN, WEATHER_TOKEN

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

keyboard1 = [['Пропустить']]
keyboard2 = [['Показать на карте'], ['Последние новости'], ['Погода'], ['Расписания'], ['Вернуться назад']]
keyboard3 = [['Вернуться назад']]
keyboard4 = [['Текущая погода'], ['Прогноз на 6 дней'], ['Вернуться назад']]
keyboard5 = [['Найти авиарейс'], ['Вернуться назад']]

inline_markup1 = InlineKeyboardMarkup(
    [[InlineKeyboardButton('Следующая новость', callback_data=1)], [InlineKeyboardButton('Назад', callback_data=3)]])

inline_markup2 = InlineKeyboardMarkup([
    [InlineKeyboardButton('Предыдущая новость', callback_data=2),
     InlineKeyboardButton('Следующая новость', callback_data=1)],
    [InlineKeyboardButton('Назад', callback_data=3)]
])

inline_markup3 = InlineKeyboardMarkup([
    [InlineKeyboardButton('Предыдущая новость', callback_data=2)],
    [InlineKeyboardButton('Назад', callback_data=3)]
])

inline_markup4 = InlineKeyboardMarkup([
    [InlineKeyboardButton('Карта', callback_data='map')],
    [InlineKeyboardButton('Спутник', callback_data='sat')],
    [InlineKeyboardButton('Гибрид', callback_data='sat,skl')],
])


def start(bot, update):
    update.message.reply_text(
        'Введите свое имя', reply_markup=ReplyKeyboardMarkup(keyboard1), one_time_keyboard=False)

    return ENTER_NAME


def enter_name(bot, update, user_data):
    name = update.message.text
    if name != 'Пропустить':
        user_data['username'] = name
    else:
        user_data['username'] = None

    update.message.reply_text('Введите свое местоположение')
    return ENTER_LOCATION


def enter_location(bot, update, user_data):
    location = update.message.text
    if location != 'Пропустить':
        user_data['location'] = location

    else:
        user_data['location'] = None

    update.message.reply_text('Введите какое-либо местоположение', reply_markup=ReplyKeyboardRemove())

    return IDLE


def idle(bot, update, user_data):
    response = geocoder_request(geocode=update.message.text, format='json')
    if check_response(response):
        update.message.reply_text(
            'Найдено местоположение',
            reply_markup=ReplyKeyboardMarkup(keyboard2)
        )

        user_data['current_response'] = response
        return LOCATION_HANDLER
    update.message.reply_text('По данному адресу ничего не найдено.')

    return IDLE


def voice_to_text(bot, update, user_data):
    voice = update.message.voice.get_file()
    file = requests.get(voice.file_path).content
    response = speech_analyze(SPEECH_TOKEN, file)

    text = speech_parser(response)
    data = geocoder_request(geocode=text, format='json')

    if check_response(data):
        update.message.reply_text(
            'Найдено местоположение',
            reply_markup=ReplyKeyboardMarkup(keyboard2)
        )
        update.message.reply_text('Выберите одну из возможных функций для данного местоположения:',
                                  reply_markup=ReplyKeyboardMarkup(keyboard2))

        user_data['current_response'] = data
        return LOCATION_HANDLER
    update.message.reply_text('По данному адресу ничего не найдено.')

    return IDLE


def location_handler(bot, update, user_data):
    text = update.message.text
    if text == 'Показать на карте':
        res = "[​​​​​​​​​​​]({}){}".format(get_static_map(user_data),
                                           'Карта для города ' + get_city(user_data['current_response'], 'ru-RU'))
        update.message.reply_text(res, parse_mode='markdown', reply_markup=inline_markup4)

    elif text == 'Последние новости':
        news = parse_news(user_data['current_response'])
        if news is not None:
            user_data['news'] = news
            user_data['index'] = 0
            user_data['length'] = len(news)
            update.message.reply_text('Найдено новостей для данного местоположения: {}'.format(len(news)),
                                      reply_markup=ReplyKeyboardRemove())
            update.message.reply_text('*{0}*\n{1}\n[Подробнее:]({2})'.format(*news[0]), parse_mode='markdown',
                                      reply_markup=inline_markup1)
            return NEWS_HANDLER

        else:
            update.message.reply_text('Новостей для этой местности не найдено')

    elif text == 'Погода':
        update.message.reply_text(
            'Что вы хотите узнать о погоде в городе {}?'.format(get_city(user_data['current_response'], 'ru-RU')),
            reply_markup=ReplyKeyboardMarkup(keyboard4))
        return WEATHER_HANDLER

    elif text == 'Расписания':
        update.message.reply_text(
            'Выберите один из вариантов поиска:',
            reply_markup=ReplyKeyboardMarkup(keyboard5))
        return RASP_HANDLER

    elif text == 'Вернуться назад':
        update.message.reply_text('Введите какое-либо местоположение', reply_markup=ReplyKeyboardRemove())
        return IDLE

    return LOCATION_HANDLER


def scrolling_news(bot, update, user_data):
    query = update.callback_query
    d = {0: inline_markup1, user_data['length'] - 1: inline_markup3}
    if query.data == '1':
        user_data['index'] = min(user_data['length'], user_data['index'] + 1)

    elif query.data == '2':
        user_data['index'] = max(0, user_data['index'] - 1)

    elif query.data == '3':
        bot.deleteMessage(chat_id=query.message.chat_id,
                          message_id=query.message.message_id)
        bot.send_message(query.message.chat_id, 'Выберите одну из возможных функций для данного местоположения:',
                         reply_markup=ReplyKeyboardMarkup(keyboard2))

        return LOCATION_HANDLER
    try:
        bot.edit_message_text(text='*{0}*\n{1}\n[Подробнее:]({2})'.format(*user_data['news'][user_data['index']]),
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id, parse_mode='markdown',
                              reply_markup=d[user_data['index']] if user_data['index'] in d else inline_markup2)
    except IndexError:
        if user_data['index'] < 0:
            user_data['index'] = 0

        else:
            user_data['index'] = user_data['length'] - 1


def choosing_map_type(bot, update, user_data):
    query = update.callback_query
    bot.edit_message_text(chat_id=query.message.chat_id, message_id=query.message.message_id,
                          text="[​​​​​​​​​​​]({}){}".format(get_static_map(user_data, query.data),
                                                            'Карта для города ' + get_city(
                                                                user_data['current_response'], 'ru-RU')),
                          parse_mode='markdown', reply_markup=inline_markup4)


def enter_the_map(bot, update):
    text = update.message.text
    if text == 'Вернуться назад':
        return LOCATION_HANDLER


def weather(bot, update, user_data):
    text = update.message.text

    if text == 'Текущая погода':
        city, code = get_city(user_data['current_response']), get_country_code(user_data['current_response'])
        update.message.reply_text(
            get_current_weather(city, code, WEATHER_TOKEN, get_city(user_data['current_response'], 'ru-RU')))

    elif text == 'Прогноз на 6 дней':
        city, code = get_city(user_data['current_response']), get_country_code(user_data['current_response'])
        update.message.reply_text(
            get_forecast_weather(city, code, WEATHER_TOKEN, get_city(user_data['current_response'], 'ru-RU')))

    elif text == 'Вернуться назад':
        update.message.reply_text('Выберите одну из возможных функций для данного местоположения:',
                                  reply_markup=ReplyKeyboardMarkup(keyboard2))

        return LOCATION_HANDLER


def schedule(bot, update, user_data):
    text = update.message.text

    if text == 'Найти авиарейс':
        city = get_city(user_data['current_response'], 'ru_RU')
        airports = airs.get(city, 0)
        if airports:
            airport_question(update, city)
            return SET_SECOND_CITY_HANDLER
        else:
            update.message.reply_text(
                'В заданном городе аэропорта не найдено')

    elif text == 'Вернуться назад':
        update.message.reply_text('Выберите одну из возможных функций для данного местоположения:',
                                  reply_markup=ReplyKeyboardMarkup(keyboard2))

        return LOCATION_HANDLER


def set_second_city(bot, update, user_data):
    text = update.message.text
    if text == 'Вернуться назад':
        update.message.reply_text(
            'Выберите один из вариантов поиска:',
            reply_markup=ReplyKeyboardMarkup(keyboard5))
        return RASP_HANDLER
    else:
        user_data['airport1'] = text.split(', ')[-1]
        update.message.reply_text('Введите город пункта назначения:', reply_markup=ReplyKeyboardMarkup(keyboard3))
        return SET_SECOND_AIRPORT_HANDLER


def set_second_airport(bot, update, user_data):
    text = update.message.text
    if text == 'Вернуться назад':
        city = get_city(user_data['current_response'], 'ru_RU')
        airport_question(update, city)
        return SET_SECOND_CITY_HANDLER
    else:
        response = geocoder_request(geocode=text, format='json')
        if check_response(response):
            user_data['city2'] = get_city(response, 'ru_RU')
            airports = airs.get(user_data['city2'], 0)
            update.message.reply_text('Выберите аэропорт прибытия:',
                                      reply_markup=ReplyKeyboardMarkup(
                                          [[elem[1] + ', ' + elem[0]] for elem in airports] + [['Вернуться назад']]))
            return FIND_FLIGHTS_HANDLER
        update.message.reply_text('Введеный город не найден. Проверьте написание.')


def find_flights(bot, update, user_data):
    text = update.message.text
    if text == 'Вернуться назад':
        city = get_city(user_data['current_response'], 'ru_RU')
        airport_question(update, city)
        return SET_SECOND_CITY_HANDLER
    else:
        airport2 = text.split(', ')[-1]
        flights = get_flights(user_data['airport1'], airport2)
        if not flights:
            update.message.reply_text('Рейсов между указанными ранее аэропортами не найдено!')
            city = get_city(user_data['current_response'], 'ru_RU')
            airport_question(update, city)
            return SET_SECOND_CITY_HANDLER
        update.message.reply_text(flights[0], reply_markup=ReplyKeyboardMarkup(keyboard3))


def airport_question(update, city):
    airports = airs.get(city, 0)
    update.message.reply_text('Из какого аэропорта города {} вы хотите найти рейс?'.format(city),
                              reply_markup=ReplyKeyboardMarkup(
                                  [[elem[1] + ', ' + elem[0]] for elem in airports] + [['Вернуться назад']]))


def stop(bot, update):
    update.message.reply_text('Бля конец')
    return ConversationHandler.END


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_error_handler(error)
    dp.add_handler(conversation_handler)

    updater.start_polling()
    updater.idle()


ENTER_NAME, ENTER_LOCATION, IDLE, LOCATION_HANDLER, NEWS_HANDLER, WEATHER_HANDLER, RASP_HANDLER, SET_SECOND_CITY_HANDLER, \
SET_SECOND_AIRPORT_HANDLER, FIND_FLIGHTS_HANDLER = range(10)

conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],

    states={
        ENTER_NAME: [MessageHandler(Filters.text, enter_name, pass_user_data=True)],
        ENTER_LOCATION: [MessageHandler(Filters.text, enter_location, pass_user_data=True)],

        IDLE: [
            MessageHandler(Filters.text, idle, pass_user_data=True),
            MessageHandler(Filters.voice, voice_to_text, pass_user_data=True)
        ],

        LOCATION_HANDLER: [
            MessageHandler(Filters.text, location_handler, pass_user_data=True),
            CallbackQueryHandler(choosing_map_type, pass_user_data=True),

        ],

        NEWS_HANDLER: [
            CallbackQueryHandler(scrolling_news, pass_user_data=True)
        ],
        WEATHER_HANDLER: [
            MessageHandler(Filters.text, weather, pass_user_data=True)
        ],
        RASP_HANDLER: [
            MessageHandler(Filters.text, schedule, pass_user_data=True)
        ],
        SET_SECOND_CITY_HANDLER: [
            MessageHandler(Filters.text, set_second_city, pass_user_data=True)
        ],
        SET_SECOND_AIRPORT_HANDLER: [
            MessageHandler(Filters.text, set_second_airport, pass_user_data=True)
        ],
        FIND_FLIGHTS_HANDLER: [
            MessageHandler(Filters.text, find_flights, pass_user_data=True)
        ]

    },

    fallbacks=[CommandHandler('stop', stop)]
)

if __name__ == '__main__':
    main()
