import os
import sys
import logging
import time
from logging import StreamHandler
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions


load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s %(name)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv("TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def check_tokens():
    """Проверка на наличие необходимых токенов"""
    for var in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if var is None:
            logger.critical(
                f"Отсутствует обязательная переменная окружения {var}"
            )
            sys.exit(1)


def send_message(bot, message):
    """Отправка сообщения пользователю"""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug("Сообщение было успешно отправлено!")
    except Exception as error:
        log = f"Произошла ошибка при отправке сообщения {error}"
        logger.error(log)
        raise exceptions.SendMessageError(log)


def get_api_answer(timestamp):
    """Запрос к апи и получения от него ответа"""
    payload = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            log = "Получен код отличный от 200"
            logger.error(log)
            raise exceptions.WrongStatusCode
    except requests.exceptions.RequestException as error:
        log = f"Произошла ошибка на стороне сервера: {error}"
        logger.error(log)
        raise exceptions.ApiError(log)

    return response.json()


def check_response(response):
    """Проверка ответа от апи"""
    if not isinstance(response, dict):
        log = "Ответ от апи пришел в неверном формате"
        logger.error(log)
        raise TypeError(log)
    if "homeworks" not in response:
        log = "Получен некорректный ответ от апи"
        logger.error(log)
        raise exceptions.InvalidApiAnswer(log)
    if not isinstance(response.get("homeworks"), list):
        log = "Ответ от апи пришел в неверном формате"
        logger.error(log)
        raise TypeError(log)


def parse_status(homework):
    """Получение статуса домашней работы"""
    homework_status = homework.get("status")
    if not homework_status:
        raise exceptions.InvalidStatusError("Отсутствует статуса")

    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
    except KeyError:
        log = "Неизвестный статус домашней работы"
        logger.error(log)
        raise exceptions.InvalidStatusError(log)

    try:
        homework_name = homework["homework_name"]
    except KeyError:
        log = "Отсутствует название домашней работы"
        logger.error(log)
        raise exceptions.HomeWorkKeyError(log)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    current_status = ""

    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            check_response(response)
            status = parse_status(response["homeworks"][0])
            if status == current_status:
                logger.debug("Статус остался прежним")
            else:
                current_status = status
                send_message(bot, current_status)
        except telegram.TelegramError as error:
            logger.error(f"Ошибка при взаимодействии с телеграм: {error}")
        except KeyError:
            logger.error("Возникла ошибка при доступе к статусу домашки")
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
