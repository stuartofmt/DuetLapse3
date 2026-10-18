"""
Messages duetLapse3 sends to its page

A Message is the English text (used in the log, the plain-text API, and by the page as a fallback) with a code
and values, so the page can show it in its own language - see ui/src/locales ("server").
A Message is a str, so it can be used anywhere the text is.  Keep the English the same as in en.json.
"""


class Message(str):
    def __new__(cls, code, text, **params):
        message = super().__new__(cls, text)
        message.code = code
        message.params = params
        return message


def coded(text):
    # {code, params} for the page - None for plain text
    if isinstance(text, Message):
        return {'code': text.code, 'params': text.params}
    return None
