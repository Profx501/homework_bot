import time
import logging
import os
import json
from http import HTTPStatus

import requests
import telegram.ext
from dotenv import load_dotenv

from exceptions import StatusError, ResponseError, AnswerError


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(message)s,',
    level=logging.DEBUG,
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN))


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(
            'Бот отправил сообщение')
    except telegram.TelegramError as telegram_error:
        logging.error(
            f'Бот не отправил сообщение: {telegram_error}')


def get_api_answer(timestamp):
    """Делает запрос к API-сервису."""
    try:
        logging.debug('Бот делает запрос!')
        response = requests.get(
            ENDPOINT,
            headers={'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
            params={'from_date': timestamp},
        )
        if response.status_code != HTTPStatus.OK:
            logging.error(
                f'Эндпоинт {ENDPOINT} недоступен.'
                f' Код ответа API: {response.status_code}'
            )
            raise AnswerError(
                f'Эндпоинт {ENDPOINT} недоступен.'
                f' Код ответа API: {response.status_code}'
            )
        return response.json()
    except requests.RequestException as error:
        logging.error(f'Код ответа API: {error}')
        raise AnswerError(f'Код ответа API: {error}')
    except json.JSONDecodeError as json_error:
        logging.error(f'Код ответа API: {json_error}')
        raise json.JSONDecodeError(f'Код ответа API: {json_error}')


def check_response(response):
    """Проверяет ответ API."""
    if type(response) == list:
        raise TypeError('response не соответсвует типу!')
    if response.get('homeworks') is None:
        raise ResponseError('Нет значения в homework!')
    if type(response['homeworks']) != list:
        raise TypeError('homeworks не соответсвует типу!')
    return response.get('homeworks')[0]


def parse_status(homework):
    """Извлекает информаци о  статусе конкретной домашней работы."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')
    if status is None:
        logging.error('Нет значения в status!')
        raise StatusError('Нет значения в status!')
    if homework_name is None:
        logging.error('Нет значения в homework_name!')
        raise StatusError('Нет значения в homework_name!')
    if status not in HOMEWORK_VERDICTS:
        logging.error('Недокументированный статус')
        raise StatusError('Недокументированный статус')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            'Отсутствует обязательная переменная окружения!'
            ' Программа принудительно остановлена.'
        )
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message = 'Добро пожаловать!'
    send_message(bot, message)
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
        except Exception as error:
            message_error = f'Ошибка: {error}'
            send_message(bot, message_error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
