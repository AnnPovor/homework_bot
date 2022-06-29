import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from typing import Dict

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ConnectionException, NotResponseException
from exceptions import TelegramException, WrongAnswerException

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except TelegramException as error:
        raise TelegramException(f'Сообщение не отправлено, ошибка: {error}')


def get_api_answer(current_timestamp):
    """

    Делает запрос к API-сервису.
    В качестве параметра получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except ConnectionException as error:
        raise ConnectionException(f'Недоступность эндпоинта {error}')

    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        msg = f'Ошибка {status_code}'
        logger.error(msg)
        raise Exception(msg)
    try:
        return response.json()
    except ValueError:
        msg = 'Ответ не преобразовался в формат json'
        logger.error(msg)
        raise ValueError(msg)


def check_response(response):
    """

    Проверяет ответ API на корректность.
    В качестве параметра получает ответ API, приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям, то функция должна вернуть список
    домашних работ, доступный в ответе API по ключу 'homeworks'
    """
    if not isinstance(response, dict):
        raise TypeError('В ответе нет словаря')
    if 'homeworks' not in response or 'current_date' not in response:
        raise NotResponseException('Ключей нет в списке')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise WrongAnswerException('Тип homeworks - не список')
    return homeworks


def parse_status(homework):
    """Извлекает из информации статус работы.
    В качестве параметра функция получает один элемент из списка работ.
    В случае успеха, функция возвращает в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """
    Проверяет доступность переменных окруженияю.
    Если отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        msg = 'Отсутствуют переменные окружения!'
        logger.critical(msg)
        sys.exit(msg)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_report = {'name': '', 'output': ''}
    prev_report: Dict = current_report.copy()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
        except ConnectionException as error:
            logger.error(f'Недоступность эндпоинта {error}')
        try:
            for homework in homeworks:
                current_report['name'] = homework['homework_name']
                current_report['output'] = homework['"reviewer_comment']
                status = parse_status(homework)
                send_message(bot, status)
                current_timestamp = int(time.time())
            else:
                logger.debug('Новых статусов нет')
        except Exception as error:
            logger.error(f'Ошибка у бота {error}')
        try:
            if current_report != prev_report:
                send_message(current_report.copy(), bot)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        'my_logger.log', maxBytes=50000000, backupCount=5)
    logger.addHandler(handler)
    main()
