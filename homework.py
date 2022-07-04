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

from exceptions import (
    ConnectionError, EmptyAPIResponseError, NotForSendingError,
    TelegramError, WrongAPIResponseCodeError
)
load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format=(
        '%(asctime)s %(levelname)s - '
        '(%(filename)s).%(funcName)s:%(lineno)d - %(message)s'
    ))
logger = logging.getLogger(__name__)

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
        logger.info(f'Отправляем сообщение в телеграм: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        raise TelegramError(f'Сообщение не отправлено, ошибка: {error}')
    else:
        logger.info('Телеграм сообщение отправлено.')


def get_api_answer(current_timestamp):
    """

    Делает запрос к API-сервису.
    В качестве параметра получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params
    }
    try:
        logger.info(
            (
                'Начинаем подключение к эндпоинту {url}, с параметрами'
                ' headers = {headers}; params= {params}.'
            ).format(**request_params)
        )
        response = requests.get(**request_params)
        if response.status_code != HTTPStatus.OK:
            status_code = response.status_code
            raise WrongAPIResponseCodeError(f'Ошибка {status_code}')
        return response.json()
    except Exception as error:
        raise ConnectionError(f'Недоступность эндпоинта {error}')


def check_response(response):
    """

    Проверяет ответ API на корректность.
    В качестве параметра получает ответ API, приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям, то функция должна вернуть список
    домашних работ, доступный в ответе API по ключу 'homeworks'
    """
    logger.info(
        'Приступаю к проверке ответа от API.'
    )
    if not isinstance(response, dict):
        raise TypeError('В ответе нет словаря')
    if 'homeworks' not in response or 'current_date' not in response:
        raise EmptyAPIResponseError('Ключей нет в списке')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise KeyError('Тип homeworks - не список')
    return homeworks


def parse_status(homework):
    """
    Извлекает из информации статус работы.
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
            if homeworks:
                homework = homeworks[0]
                current_report['name'] = homework['homework_name']
                current_report['output'] = parse_status(homework)
            else:
                current_report['output'] = 'домашних работ нет.'
            if current_report != prev_report:
                send_message(bot, message=current_report['output'])
                prev_report = current_report.copy()
            else:
                logger.debug('В ответе нет новых статусов.')
        except NotForSendingError as error:
            logger.exception(error)
        except Exception as error:
            msg = f'Ошибка у бота {error}'
            current_report['output'] = msg
            if current_report != prev_report:
                send_message(bot, current_report['output'])
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(
        'my_logger.log', encoding='utf-8', maxBytes=50000000, backupCount=5)
    logger.addHandler(handler)
    h1 = logging.StreamHandler(sys.stdout)
    logger.addHandler(h1)
    main()
