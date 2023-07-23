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
    """Проверка на наличие необходимых токенов."""
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    for key, value in tokens.items():
        if value is None:
            log = f"Отсутствует обязательная переменная окружения {key}"
            logger.critical(log)
            raise exceptions.InvalidTokenException(log)


def send_message(bot, message):
    """Отправка сообщения пользователю."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug("Сообщение было успешно отправлено!")
    except Exception as error:
        logger.error(f"Произошла ошибка при отправке сообщения {error}")


def get_api_answer(timestamp):
    """Запрос к апи и получения от него ответа."""
    payload = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise exceptions.WrongStatusCode("Получен статус отличный от 200")
    except Exception:
        raise exceptions.ApiError("Возникла ошибка при запросе к апи")

    return response.json()


def check_response(response):
    """Проверка ответа от апи."""
    if not isinstance(response, dict):
        raise TypeError("Ответ пришел в неверном формате")
    if (homeworks := response.get("homeworks")) is None:
        raise exceptions.InvalidApiAnswer(
            "В ответе апи отсутствуют домашние работы"
        )
    if not isinstance(homeworks, list):
        raise TypeError("Неверный тип данных домашних работ")


def parse_status(homework):
    """Получение статуса домашней работы."""
    if not (homework_status := homework.get("status")):
        raise exceptions.InvalidStatusError(
            "Отсутствует статус домашней работы"
        )

    if not (homework_name := homework.get("homework_name")):
        raise exceptions.HomeWorkKeyError(
            "Отсутствует название домашней работы"
        )

    if not (verdict := HOMEWORK_VERDICTS.get(homework_status)):
        raise exceptions.InvalidStatusError(
            "Неизвестный статус домашней работы"
        )

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    current_status = ""

    while True:
        try:
            response = get_api_answer(timestamp=current_timestamp)
            check_response(response)
            current_timestamp = response["current_date"]
            if not (homeworks := response["homeworks"]):
                logger.debug("В данный момент список домашек пуст")
            else:
                status = parse_status(homeworks[0])
                if status == current_status:
                    logger.debug("Статус остался прежним")
                else:
                    current_status = status
                    send_message(bot, current_status)

        except Exception as error:
            logger.error(error, exc_info=True)
            error_message = f"Произошла ошибка: {error}"
            send_message(bot, error_message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
