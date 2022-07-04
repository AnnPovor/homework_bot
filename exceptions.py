class NotForSendingError(Exception):
    pass


class WrongAPIResponseCodeError(Exception):
    """Вылетает когда код ответа сервера != 200. Шлём в телегу."""
    pass


class EmptyAPIResponseError(NotForSendingError):
    """Вылетает когда нет домашек или timestamp. НЕ ШЛЁМ в телегу."""
    pass


class TelegramError(NotForSendingError):
    """Вылетает когда не получилось выслать в телегу. НЕ ШЛЁМ в телегу."""
    pass


class ConnectionError(Exception):
    """Вылетает, когда произошла ошибка при подключению к серверу."""
    pass
