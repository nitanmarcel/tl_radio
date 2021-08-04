import functools
import re

from telethon import events, TelegramClient
from telethon.errors import RPCError
from telethon.tl.custom import Message
from youtube_dl.utils import YoutubeDLError

DELETION_QUEUE = {}
HELP = {}


class CommandHandler:
    def __init__(self, client, callback, prefix, command, *args, **kwargs):
        self._client: TelegramClient = client
        self._callback = callback
        self._prefix = prefix
        self._command = command

        self._client.add_event_handler(self._command_handler, events.NewMessage(*args, **kwargs))

        if self._callback.__doc__:
            HELP[self._command] = {"prefix": self._prefix, "message": self._callback.__doc__}

    async def _command_handler(self, event):
        if not event.text:
            return
        if event.raw_text.split(None, 1)[0] != self._prefix + self._command:
            return

        args = event.raw_text.split()[1:]

        @self.cleanup
        async def _raise(exception):
            if isinstance(exception, RPCError):
                return await event.reply(self._format_tg_exception(exc))
            if isinstance(exception, YoutubeDLError):
                return await event.reply(self._format_youtubedl_error(exc))
            else:
                await event.reply(self._format_exception(exc))
                raise

        @self.cleanup
        async def _help(command=None):
            if command:
                return await event.reply(HELP[command]["message"])

        try:
            if "--help" in args:
                return await _help(self._command)
            await self._callback(event, args)
        except Exception as exc:
            await _raise(exc)
        await event.delete()

    @staticmethod
    def cleanup(func):
        global DELETION_QUEUE

        @functools.wraps(func)
        async def decorator(*args, **kwargs):
            name = func.__module__ + "." + func.__name__
            try:
                await DELETION_QUEUE[name].delete()
            except Exception:
                pass
            result = await func(*args, **kwargs)
            if isinstance(result, Message):
                DELETION_QUEUE[name] = result

        return decorator

    @staticmethod
    def _format_html(text):
        text = text.replace("\n", "<br>").replace("<b><b>", "<b>")
        text = str(Pre(text))
        return text

    @staticmethod
    def _format_tg_exception(exception):
        text = re.sub(rf"(\(.*\))", "", str(exception))
        return text

    @staticmethod
    def _format_exception(exception):
        name = exception.__class__.__name__
        text = str(exception)
        return name + ": " + text

    @staticmethod
    def _format_youtubedl_error(exception):
        text = re.sub('^(\w*:)', '', str(exception))
        return text
