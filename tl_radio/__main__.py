import asyncio
import functools

from pytgcalls import GroupCallFactory
from telethon import TelegramClient, utils
from telethon import events
from telethon.errors import MessageNotModifiedError, MessageIdInvalidError
from youtube_dl.utils import formatSeconds, UnsupportedError

from tl_radio import CONFIG, LOOP, LOGGER
from tl_radio.sql import sql_telethon
from tl_radio.utils import build_queue, format_queue, build_playback_buttons, next_pairs, prev_pairs
from tl_radio.utils.commandhandler import CommandHandler, HELP
from tl_radio.ytdl import YtDl
from .player import Player, Stream, RadioStream

u_client = TelegramClient(sql_telethon.container.new_session("user"), api_id=CONFIG.telegram.api_id,
                          api_hash=CONFIG.telegram.api_hash)
u_client.start()
if CONFIG.telegram.bot_token:
    b_client = TelegramClient(sql_telethon.container.new_session("bot"), api_id=CONFIG.telegram.api_id,
                              api_hash=CONFIG.telegram.api_hash)
    b_client.start(bot_token=CONFIG.telegram.bot_token)
else:
    b_client = u_client

u_client.parse_mode = "html"
b_client.parse_mode = "html"

_ytdl_opts = {"format": "bestaudio/best",
              "extractaudio": True,
              "restrictfilenames": True,
              "logtostderr": False,
              "no_color": True,
              "outtmpl": "%(id)s.%(ext)s",
              "source_address": "0.0.0.0",
              "postprocessors": [{"key": "FFmpegMetadata"}]}
_ytdl_opts.update(CONFIG.youtubedl_opts)
ytdl = YtDl(_ytdl_opts)

audioplayer = Player(max_queue_lenght=50, loop=LOOP)
group_call_factory = GroupCallFactory(u_client, GroupCallFactory.MTPROTO_CLIENT_TYPE.TELETHON)
group_call = group_call_factory.get_raw_group_call(on_played_data=audioplayer.read_buffer)

async def main():
    user_entity = await u_client.get_me()
    if not CONFIG.telegram.bot_token:
        bot_entity = user_entity
    else:
        bot_entity = await b_client.get_me()

    @CommandHandler.cleanup
    async def _help(event, args):
        """<i>Returns a list with all the availbale commands.</i>"""
        res = "Here is a list of all the commands you can use:\n\n"
        for k in list(HELP.keys()):
            res += f"{HELP[k]['prefix']}{k}:\n {HELP[k]['message']}\n\n"
        return await event.reply(res)

    @CommandHandler.cleanup
    @not_busy
    @has_permissions
    async def _play(event, args):
        """<i>Ads songs to queue and plays if the initial queue was empty.</i>
            <pre>Args:
            source [url | int]: An url to an audio stream or a number on the queue.</pre>
        """
        if not args:
            return
        source = " ".join(args)
        if not await group_call.check_group_call():
            LOGGER.debug("Starting group call")
            await group_call.start(event.chat_id)
        if source.isdigit():
            await audioplayer.play_one(int(source))
            return
        msg = await event.reply("Processing..")
        info = await ytdl.extract_info(source)
        if len(info) == 1:
            result = info[0]
            if CONFIG.general.music_only:
                if not result["extractor"].lower().startswith("youtube"):
                    return await msg.edit("Only audios provided by YouTube are allowed!")
                if "Music" not in result["categories"]:
                    return await msg.edit("Only YouTube queries from \"Music\" category are allowed.")
            if CONFIG.general.extractors_denylist[0]:
                if result["extractor"] in CONFIG.general.extractors_denylist:
                    return await msg.edit(f"Queries from {result['extractor']} are not allowed.")

            elif CONFIG.general.extractors_allowlist[0]:
                if result["extractor"] not in CONFIG.general.extractors_allowlist:
                    return await msg.edit(f"Queries from {result['extractor']} are not allowed.")
            if CONFIG.general.max_lenght > 0:
                if result["duration"] == 0:
                    return await msg.edit("Medias with no duration data aren't allowed.")
                elif result["duration"] > CONFIG.general.max_lenght:
                    return await msg.edit(
                        f"Medias longer than {formatSeconds(CONFIG.general.max_lenght)} (h:m:s) aren't allowed. The provided media is {formatSeconds(result['duration'])} (h:m:s) long.")
            if result["is_live"] is True:
                return await msg.edit("Live streams should be played using the /radio command")
            stream = Stream(result["id"], result["url"], result["title"], result["extractor"], result["duration"])
            await audioplayer.add_to_queue(stream)
        else:
            queued_count = 0
            for result in info:
                if result["extractor"] not in ["live", "generic"]:
                    if CONFIG.general.music_only:
                        if not result["extractor"].lower().startswith("youtube"):
                            return
                        if "Music" not in result["categories"]:
                            return
                    if CONFIG.general.extractors_denylist[0]:
                        if result["extractor"] in CONFIG.general.extractors_denylist:
                            return
                    elif CONFIG.general.extractors_allowlist[0]:
                        if result["extractor"] not in CONFIG.general.extractors_allowlist:
                            return
                    if CONFIG.general.max_lenght > 0:
                        if result["duration"] == 0:
                            return
                        elif result["duration"] > CONFIG.general.max_lenght:
                            return
                queued_count += 1
                stream = Stream(result["id"], result["url"], result["title"], result["extractor"], result["duration"])
                await audioplayer.add_to_queue(stream, raise_event=queued_count == len(info))
        await msg.delete()

    @CommandHandler.cleanup
    @not_busy
    @has_permissions
    async def _radio(event, args):
        """<i>Plays an radio or live stream.</i>
            <pre>Args:
            source [url]: An url to a radio stream.</pre>
        """
        if not args:
            return
        is_connected = await group_call.check_group_call()
        if not is_connected:
            await group_call.start(event.chat_id)

        source = args[0]

        msg = await event.reply("Processing..")
        info = await ytdl.extract_info(source)
        if len(info) > 1:
            await msg.delete()
            raise UnsupportedError(source)
        if info[0]["is_live"] is False:
            await msg.delete()
            raise UnsupportedError(source)

        stream = RadioStream(info[0]["id"], info[0]["url"], info[0]["title"])
        await audioplayer.add_to_queue(stream)

    @CommandHandler.cleanup
    @connected
    @not_busy
    @has_permissions
    async def _stop(event, args):
        """<i>Stops the current playback and leaves the group.</i>"""
        await audioplayer.stop()
        await group_call.stop()

    @CommandHandler.cleanup
    @not_busy
    @has_permissions
    async def _clear_queue(event, args):
        """<i>Clears the current queue and stops any song if playing.</i>"""
        await audioplayer.stop()
        audioplayer.queue.clear()

    @CommandHandler.cleanup
    @not_busy
    @has_permissions
    async def _dequeue(event, args):
        """<i>Removes a song from the queue</i>
            <pre>Args:
                index [int]: The index in queue to remove."""
        if not args:
            return
        index = args[0]
        if not index.isdigit():
            return
        await audioplayer.remove_from_queue(int(index))

    @CommandHandler.cleanup
    @not_busy
    @has_permissions
    async def _queue(event, args):
        """<i>Returns the current queue.</i>"""
        queue, buttons, page = format_queue(audioplayer.queue)
        res = build_queue(queue, page)
        return await event.reply(res, buttons=buttons)

    @CommandHandler.cleanup
    @connected
    @not_busy
    @has_permissions
    async def _playing(event, args):
        """<i>Returns the current playing stream and the playback controls."""
        stream = audioplayer.now_playing
        if stream:
            buttons = build_playback_buttons(audioplayer.is_paused, audioplayer.repeat_mode)
            return await b_client.send_message(group_call.full_chat.id, f"Now playing: {stream.title}", buttons=buttons)
        else:
            return await b_client.send_message(group_call.full_chat.id, "There's nothing playing or queued at this moment.")


    @audioplayer.event.on("event_queue_update")
    @CommandHandler.cleanup
    async def _on_queue_update(queue):
        queue, buttons, page = format_queue(audioplayer.queue)
        res = build_queue(queue, page)
        if not audioplayer.is_playing and not audioplayer.is_paused:
            await audioplayer.play()
        return await b_client.send_message(group_call.full_chat.id, res, buttons=buttons)

    @audioplayer.event.on("event_playback_pause")
    async def _pause(stream):
        group_call.pause_playout()

    @audioplayer.event.on("event_playback_resume")
    async def _resume(stream):
        group_call.resume_playout()

    @audioplayer.event.on("event_stream_start")
    @CommandHandler.cleanup
    async def _on_stream_start(stream):
        buttons = build_playback_buttons(audioplayer.is_paused, audioplayer.repeat_mode)
        return await b_client.send_message(group_call.full_chat.id, f"Now playing: {stream.title or stream.url}.", buttons=buttons, link_preview=False)

    @audioplayer.event.on("event_stream_end")
    async def _on_stream_end(stream):
        await audioplayer.play_next()

    @b_client.on(events.CallbackQuery())
    @has_permissions
    @connected
    @not_busy
    async def _controls(event):
        data = event.data.decode()
        data_type = data.split("_", 1)[0]
        await event.answer()
        if data_type == "ctrl":
            ctrl = data.split("ctrl_", 1)[-1]
            if ctrl == "resume":
                await audioplayer.resume()
            if ctrl == "pause":
                await audioplayer.pause()
            if ctrl == "back":
                await audioplayer.play_prev()
            if ctrl == "forward":
                await audioplayer.play_next()
            if ctrl == "shuffle":
                audioplayer.shuffle_queue()
            if ctrl == "repeat_queue":
                audioplayer.repeat_mode = 0
            if ctrl == "no_repeat":
                audioplayer.repeat_mode = 1
            if ctrl == "repeat_playback":
                audioplayer.repeat_mode = 2
            buttons = build_playback_buttons(audioplayer.is_paused, audioplayer.repeat_mode)
            msg = await event.get_message()
            try:
                await event.edit(msg.text, buttons=buttons)
            except (MessageNotModifiedError, MessageIdInvalidError):
                pass
        if data_type == "queue":
            queue_ctrl = data.split("queue_", 1)[-1]
            if queue_ctrl == "next":
                next_pairs()
            if queue_ctrl == "shuffle":
                audioplayer.shuffle_queue()
            if queue_ctrl == "prev":
                prev_pairs()
            queue, buttons, page = format_queue(audioplayer.queue)
            res = build_queue(queue, page)
            try:
                await event.edit(res, buttons=buttons)
            except MessageNotModifiedError:
                pass
            except MessageIdInvalidError:
                return await event.reply(res, buttons=buttons)

    CommandHandler(b_client, _help, CONFIG.general.cmd_prefix, "help", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _play, CONFIG.general.cmd_prefix, "play", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _radio, CONFIG.general.cmd_prefix, "radio", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _stop, CONFIG.general.cmd_prefix, "stop", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _clear_queue, CONFIG.general.cmd_prefix, "clear", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _dequeue, CONFIG.general.cmd_prefix, "dequeue", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _queue, CONFIG.general.cmd_prefix, "queue", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _clear_queue, CONFIG.general.cmd_prefix, "clear", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)
    CommandHandler(b_client, _playing, CONFIG.general.cmd_prefix, "playing", incoming=bot_entity.bot,
                   outgoing=not bot_entity.bot, func=lambda e: not e.is_private)

    tasks = [u_client.run_until_disconnected()]
    if await b_client.is_bot():
        tasks.append(b_client.run_until_disconnected())
    await asyncio.gather(*tasks)


def has_permissions(func):
    @functools.wraps(func)
    async def decorator(event, *args, **kwargs):
        is_callback = isinstance(event, events.callbackquery.CallbackQuery.Event)
        if CONFIG.general.enforce_admin:
            permissions = await b_client.get_permissions(event.chat_id, event.sender_id)
            if CONFIG.general.anonymous:
                if not permissions.anonymous:
                    if not is_callback:
                        return await event.reply("Anonymous usage is not allowed.")
                    else:
                        await event.answer()
                        return
            elif not permissions.is_admin or not permissions.manage_call:
                if event.sender_id not in CONFIG.general.exceptions:
                    if not is_callback:
                        return await event.reply("You don't have enough rights to use this command.")
                    else:
                        await event.answer()
                        return
        else:
            if event.sender_id in CONFIG.general.exceptions:
                if not is_callback:
                    return await event.reply("You don't have enough rights to use this command.")
                else:
                    await event.answer()
                    return
        return await func(event, *args, **kwargs)
    return decorator

def connected(func):
    @functools.wraps(func)
    async def decorator(event, *args, **kwargs):
        is_callback = isinstance(event, events.callbackquery.CallbackQuery.Event)
        is_connected = await group_call.check_group_call()
        if not is_connected:
            if is_callback:
                await event.answer()
                return
        peer = await b_client.get_input_entity(event.chat_id)
        group_call_peer = group_call.chat_peer
        if group_call_peer is None:
            if is_callback:
                await event.answer()
            return
        if utils.get_peer_id(peer) != utils.get_peer_id(group_call_peer):
            if is_callback:
                await event.answer()
            return
        return await func(event, *args, **kwargs)
    return decorator

def not_busy(func):
    @functools.wraps(func)
    async def decorator(event, *args, **kwargs):
        is_callback = isinstance(event, events.callbackquery.CallbackQuery.Event)
        if group_call.is_connected:
            peer = await b_client.get_input_entity(event.chat_id)
            group_call_peer = group_call.chat_peer
            if utils.get_peer_id(peer) != utils.get_peer_id(group_call_peer):
                if not is_callback:
                    return await event.reply("Userbot is already busy playing in another chat!")
                else:
                    await event.answer()
                    return
        return await func(event, *args, **kwargs)
    return decorator

if __name__ == "__main__":
    LOOP.run_until_complete(main())
