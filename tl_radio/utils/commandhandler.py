import argparse
import datetime
import io
import re
import shlex
import sys
from typing import IO, List, NoReturn, Optional, Sequence, Text, Tuple

from kantex.html import *
from telethon import events
from telethon.errors import RPCError
from youtube_dl.utils import YoutubeDLError

from .. import CONFIG, LAST_MSGS


class CommandArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(CommandArgumentParser, self).__init__(*args, **kwargs)
        self._stderr = io.StringIO()
        self._stdout = io.StringIO()

    def error(self, message: Text) -> NoReturn:
        self._write_stderr(message)

    def exit(self) -> None:
        return

    def _print_message(self, message: str,
                       file: Optional[IO[str]] = ...) -> None:
        if message:
            if file is None:
                file = self._stderr
            if file is sys.stderr:
                file = self._stderr
            if file is sys.stdout:
                file = self._stdout
            file.seek(0)
            file.write(message)
            file.seek(0)

    def parse_known_args(self, args: Optional[Sequence[Text]] = ...,
                         namespace: Optional[argparse.Namespace] = ...) -> Tuple[argparse.Namespace, List[str]]:
        if args is None:
            args = list()
        else:
            args = list(args)

        if namespace is None:
            namespace = argparse.Namespace()

        # add any action defaults that aren't present
        for action in self._actions:
            if action.dest is not argparse.SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not argparse.SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        # parse the arguments and exit if there are any errors
        try:
            namespace, args = self._parse_known_args(args, namespace)
            if hasattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR):
                args.extend(
                    getattr(
                        namespace,
                        argparse._UNRECOGNIZED_ARGS_ATTR))
                delattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR)
            return namespace, args
        except argparse.ArgumentError:
            raise

    def _write_stderr(self, message: Text) -> NoReturn:
        self._stderr.seek(0)
        self._stderr.write(message)
        self._stderr.seek(0)

    def _write_stdout(self, message: Text) -> NoReturn:
        self._stdout.seek(0)
        self._stdout.write(message)
        self._stderr.seek(0)

    def read_stderr(self):
        return self._stderr.read()

    def read_stdout(self):
        return self._stdout.read()


CMDS = {}


class CommandHandler:
    def __init__(self, client, callback, command, *args, **kwargs):
        self._callback = callback
        self._command = command
        self._pattern = re.compile(f"^{re.escape(CONFIG.general.cmd_prefix)}{command}")
        self._parser = CommandArgumentParser(
            description=callback.__doc__,
            prog=f"{CONFIG.general.cmd_prefix}{self._command}")

        self._hasargs = False

        client.add_event_handler(
            self._handler,
            events.NewMessage(
                pattern=self._pattern,
                **kwargs))
        CMDS[command] = {"description": callback.__doc__, "has_args": False}

    async def _handler(self, event):

        msg = event.message

        if event.is_reply:
            msg = await event.get_reply_message()

        try:
            event.raw_text = event.raw_text.replace("\"", "\\\"").replace("\'", "\\'")
            args = self._parser.parse_args(shlex.split(
                " ".join(event.raw_text.split()[1:])))
        except argparse.ArgumentError as exc:
            return await msg.reply(Code(str(exc)))

        stdout = self._parser.read_stdout()
        stderr = self._parser.read_stderr()

        if stdout or stderr:
            msg = await msg.reply(str(Pre(stdout or stderr)))
            LAST_MSGS.append(msg)
            return

        try:
            if self._hasargs:
                await self._callback(event, args)
            else:
                await self._callback(event)

        except RPCError as exc:
            msg = await event.reply(self._format_tg_exception(exc))
            LAST_MSGS.append(msg)
            raise

        except YoutubeDLError as exc:
            msg = await event.reply(self._format_youtubedl_error(exc), link_preview=False)
            LAST_MSGS.append(msg)

        except Exception as exc:
            msg = await event.reply(self._format_exception(exc))
            LAST_MSGS.append(msg)
            raise

    def add_argument(self, *args, **kwargs):
        self._parser.add_argument(*args, nargs='+', **kwargs)
        if not self._hasargs:
            self._hasargs = True
        CMDS[self._command]["has_args"] = True

    @staticmethod
    def _format_html(text):
        text = text.replace("\n", "<br>").replace("<b><b>", "<b>")
        text = str(Pre(text))
        return text

    @staticmethod
    def _format_tg_exception(exception):
        name = exception.message.replace("_", " ").title()
        text = re.sub(rf"(\(.*\))", "", str(exception))
        sec = Section(name)

        if hasattr(exception, "seconds"):
            sec.append(
                KeyValueItem(
                    "Duration", Code(
                        datetime.timedelta(
                            seconds=exception.seconds))))

        sec.append(text)
        sec.append("")
        sec.append(
            KeyValueItem(
                "Cause", Code(
                    exception.request.__class__.__name__)))
        return str(KanTeXDocument(sec))

    @staticmethod
    def _format_exception(exception):
        text = str(exception)
        name = re.sub(r'([A-Z])', r' \1', exception.__class__.__name__)
        sec = Section(name)
        sec.append(text)
        sec.append("")
        return str(KanTeXDocument(sec))

    @staticmethod
    def _format_youtubedl_error(exception):
        text = re.sub('^(\w*:)', '', str(exception))
        return text
