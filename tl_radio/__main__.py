import asyncio
from functools import wraps

from pytgcalls import GroupCallFactory
from telethon import TelegramClient
from telethon import utils
from youtube_dl.utils import formatSeconds, ExtractorError

from tl_radio import CONFIG, LOOP, LAST_MSGS
from tl_radio.musicplayer import events
from tl_radio.musicplayer.player import Player
from tl_radio.musicplayer.song import Song
from tl_radio.radio import events as revents
from tl_radio.radio.radio import Radio
from tl_radio.sql import sql_telethon
from tl_radio.sql import sql_youtubedl
from tl_radio.utils.commandhandler import CommandHandler, CMDS
from tl_radio.utils.run_in_executor import run_in_executor

u_client = TelegramClient(sql_telethon.container.new_session("test_user"), api_id=CONFIG.telegram.api_id,
                          api_hash=CONFIG.telegram.api_hash)
u_client.start()
if CONFIG.telegram.bot_token:
    b_client = TelegramClient(sql_telethon.container.new_session("test_bot"), api_id=CONFIG.telegram.api_id,
                              api_hash=CONFIG.telegram.api_hash)
    b_client.start(bot_token=CONFIG.telegram.bot_token)
else:
    b_client = u_client

u_client.parse_mode = "html"
b_client.parse_mode = "html"

group_call_factory = GroupCallFactory(u_client, GroupCallFactory.MTPROTO_CLIENT_TYPE.TELETHON)
group_call = group_call_factory.get_file_group_call()
active_chat_id = None
musicplayer = Player(group_call)
radio = Radio(group_call)


async def main():
    user_entity = await u_client.get_me()
    if not CONFIG.telegram.bot_token:
        bot_entity = user_entity
    else:
        bot_entity = await b_client.get_me()

    @cleanup
    async def _help(event):
        """Displays a list of all commands and their short description."""
        res = f"All commands are callable using {CONFIG.general.cmd_prefix} prefix\n"
        for k, v in CMDS.items():
            res += f"{CONFIG.general.cmd_prefix}{k}"
            if v["has_args"]:
                res += " *args"
            res += f" {v['description']}\n"
        res += "\n\n See <code>{command} --help</code> for a detailed description for a specific command."
        msg = await event.reply(res)
        LAST_MSGS.append(msg)

    @cleanup
    @has_permissions
    @not_busy
    async def _play(event, args):
        """Downloads audio from source and adds it to the queue. If nothing is playing, play it."""
        source = " ".join(args.source)
        msg = await event.reply("Extracting info...")
        info = await _extract_info(source)
        if info["duration"] == -1:
            msg = await msg.edit(
                f"Live streaming using {info['extractor']} provider is not supported at this moment!")
            LAST_MSGS.append(msg)
            return
        if CONFIG.general.music_only:
            if not info["extractor"].lower().startswith("youtube"):
                msg = await msg.edit("Only audios provided by YouTube are allowed!")
                LAST_MSGS.append(msg)
                return
            if "Music" not in info["categories"]:
                msg = await msg.edit("Only YouTube queries from \"Music\" category are allowed.")
                LAST_MSGS.append(msg)
                return
        if CONFIG.general.extractors_denylist[0]:
            if info["extractor"] in CONFIG.general.extractors_denylist:
                msg = await msg.edit(f"Queries from {info['extractor']} are not allowed.")
                LAST_MSGS.append(msg)
                return
        elif CONFIG.general.extractors_allowlist[0]:
            if info["extractor"] not in CONFIG.general.extractors_allowlist:
                msg = await msg.edit(f"Queries from {info['extractor']} are not allowed.")
                LAST_MSGS.append(msg)
                return
        if CONFIG.general.max_lenght > 0:
            if info["duration"] == 0:
                msg = await msg.edit("Medias with no duration data aren't allowed.")
                LAST_MSGS.append(msg)
                return
            elif info["duration"] > CONFIG.general.max_lenght:
                msg = await msg.edit(
                    f"Medias longer than {formatSeconds(CONFIG.general.max_lenght)} (h:m:s) aren't allowed. The provided media is {formatSeconds(info['duration'])} (h:m:s) long.")
                LAST_MSGS.append(msg)
                return
        if not group_call.is_connected:
            await group_call.start(event.chat_id)

        sender = await event.get_sender()
        msg = await msg.edit("Processing...")
        LAST_MSGS.append(msg)
        song = Song(info["id"], info["title"], info["duration"], info["ext"], f"{info['id']}.raw",
                    sender.username or sender.first_name)
        await musicplayer.queue(song, source)
        if radio.is_active:
            await radio.stop()
        if not musicplayer.playlist_instance.now_playing:
            await musicplayer.play(song=song)

    @cleanup
    @connected
    @has_permissions
    async def _stop(event):
        """Stops music/radio."""
        if musicplayer.is_on:
            await musicplayer.stop()
        elif radio.is_active:
            await group_call.stop()

    @cleanup
    @connected
    @has_permissions
    async def _skip(event):
        """Skips to the next item in queue"""
        await musicplayer.play_next()

    @cleanup
    @connected
    async def _queue(event):
        """Returns the current queue."""
        res = ""
        nr = 0
        for s in musicplayer.playlist_instance.get_queue():
            res += f"{nr}: {s.title} - requested by {s.requested_by}\n"
            nr += 1
        await b_client.send_message(group_call.full_chat.id, res)

    @cleanup
    @connected
    @has_permissions
    async def _shuffle(event):
        """Shuffles the current queue."""
        await musicplayer.shuffle()

    @cleanup
    @connected
    @has_permissions
    async def _pause(event):
        """Pause the current playout."""
        await musicplayer.pause()

    @cleanup
    @connected
    @has_permissions
    async def _resume(event):
        """Resumes the current playout."""
        await musicplayer.resume()

    @cleanup
    @connected
    @has_permissions
    async def _repeat(event):
        """Toggles repeat on or off."""
        musicplayer.playlist_instance.switch_repeat()

    @group_call.on_playout_ended
    async def _ended(*args):
        await musicplayer.play_next()

    @group_call.on_network_status_changed
    async def _reconnect(*args):
        if not await group_call.check_group_call():
            await group_call.reconnect()

    @musicplayer.on(events.EventItemQueued)
    async def _on_queued(song):
        res = ""
        nr = 0
        for s in musicplayer.playlist_instance.get_queue():
            res += f"{nr}: {s.title} - requested by {s.requested_by}\n"
            nr += 1
        if LAST_MSGS:
            for msg in LAST_MSGS:
                try:
                    await msg.delete()
                except Exception:
                    pass
        msg = await b_client.send_message(group_call.full_chat.id, res)
        LAST_MSGS.append(msg)

    @musicplayer.on(events.EventPlaybackStarted)
    async def _on_play(song):
        if LAST_MSGS:
            for msg in LAST_MSGS:
                try:
                    await msg.delete()
                except Exception:
                    pass
        msg = await b_client.send_message(group_call.full_chat.id,
                                          f"Now playing.. {song.title} requested by {song.requested_by}")
        LAST_MSGS.append(msg)

    @musicplayer.on(events.EventRepeatToggled)
    async def _on_repeat(status):
        if LAST_MSGS:
            for msg in LAST_MSGS:
                try:
                    await msg.delete()
                except Exception:
                    pass
        msg = await b_client.send_message(group_call.full_chat.id, f"Repeat mode is {'on' if status else 'off'}")
        LAST_MSGS.append(msg)

    @cleanup
    @has_permissions
    @not_busy
    async def _radio(event, args):
        """Turns on radio and plays audio from a given stream url."""
        if not group_call.is_connected:
            await group_call.start(event.chat_id)
        msg = await event.reply("Processing...")
        LAST_MSGS.append(msg)
        await asyncio.sleep(1)
        musicplayer.playlist_instance.clear()
        station = " ".join(args.source)
        play = await radio.play(station)
        if not play:
            msg = await msg.edit("The given URL is not a valid radio stream.")
            LAST_MSGS.append(msg)

    @radio.on(revents.EventRadioStarted)
    async def _on_radio_start(station):
        msg = await b_client.send_message(group_call.full_chat.id, f"Now playing {station.url} radio stream.")
        LAST_MSGS.append(msg)

    _help_handler = CommandHandler(b_client, _help, "help", incoming=bot_entity.bot, outgoing=not bot_entity.bot,
                                   func=lambda e: not e.is_private)
    _play_handler = CommandHandler(b_client, _play, "play", incoming=bot_entity.bot, outgoing=not bot_entity.bot,
                                   func=lambda e: not e.is_private)
    _stop_handler = CommandHandler(b_client, _stop, "stop", incoming=bot_entity.bot, outgoing=not bot_entity.bot,
                                   func=lambda e: not e.is_private)
    _skip_handler = CommandHandler(b_client, _skip, "skip", incoming=bot_entity.bot, outgoing=not bot_entity.bot,
                                   func=lambda e: not e.is_private)

    _shuffle_handler = CommandHandler(b_client, _shuffle, "shuffle", incoming=bot_entity.bot,
                                      outgoing=not bot_entity.bot,
                                      func=lambda e: not e.is_private)

    _shuffle_handler = CommandHandler(b_client, _pause, "pause", incoming=bot_entity.bot,
                                      outgoing=not bot_entity.bot,
                                      func=lambda e: not e.is_private)

    _shuffle_handler = CommandHandler(b_client, _resume, "resume", incoming=bot_entity.bot,
                                      outgoing=not bot_entity.bot,
                                      func=lambda e: not e.is_private)

    _radio_handler = CommandHandler(b_client, _radio, "radio", incoming=bot_entity.bot,
                                    outgoing=not bot_entity.bot,
                                    func=lambda e: not e.is_private)

    _play_handler.add_argument("source", help="An url or youtube search query.")
    _radio_handler.add_argument("source", help="An audio stream url..")

    tasks = [u_client.run_until_disconnected()]
    if await b_client.is_bot():
        tasks.append(b_client.run_until_disconnected())
    await asyncio.gather(*tasks)


def has_permissions(func):
    @wraps(func)
    async def decorator(event, *args, **kwargs):
        if CONFIG.general.enforce_admin:
            permissions = await b_client.get_permissions(event.chat_id, event.sender_id)
            if CONFIG.general.anonymous:
                if not permissions.anonymous:
                    msg = await event.reply("Anonymous usage is not allowed.")
                    LAST_MSGS.append(msg)
                    return
            elif not permissions.is_admin or not permissions.manage_call:
                if event.sender_id not in CONFIG.general.exceptions:
                    msg = await event.reply("You don't have enough rights to use this command.")
                    LAST_MSGS.append(msg)
                    return
        else:
            if event.sender_id in CONFIG.general.exceptions:
                msg = await event.reply("You don't have enough rights to use this command.")
                LAST_MSGS.append(msg)
                return
        return await func(event, *args, **kwargs)

    return decorator


def connected(func):
    @wraps(func)
    async def decorator(event, *args, **kwargs):
        if not group_call.is_connected:
            return
        peer = await b_client.get_input_entity(event.chat_id)
        group_call_peer = group_call.chat_peer
        if utils.get_peer_id(peer) != utils.get_peer_id(group_call_peer):
            return
        return await func(event, *args, **kwargs)

    return decorator


def not_busy(func):
    @wraps(func)
    async def decorator(event, *args, **kwargs):
        if group_call.is_connected:
            peer = await b_client.get_input_entity(event.chat_id)
            group_call_peer = group_call.chat_peer
            if utils.get_peer_id(peer) != utils.get_peer_id(group_call_peer):
                msg = await event.reply("Userbot is already busy playing in another chat!")
                LAST_MSGS.append(msg)
                return await event.delete()
        return await func(event, *args, **kwargs)

    return decorator


def cleanup(func):
    @wraps(func)
    async def decorator(event, *args, **kwargs):
        if LAST_MSGS:
            for msg in LAST_MSGS:
                try:
                    await msg.delete()
                except Exception:
                    pass
        await func(event, *args, **kwargs)
        return await event.delete()

    return decorator


async def _extract_info(url):
    if not sql_youtubedl.is_cached(url):
        info = await run_in_executor(musicplayer.ytdl_instance.extract_info, url, download=False)
        if info is None:
            raise ExtractorError(f"ERROR: Failed to extract data for: {url}", expected=True)
        if "entries" in info.keys():
            info = info["entries"][0]
        await sql_youtubedl.set_cache(url, info["title"], info["id"], info["ext"], info["extractor"],
                                      info.get("duration", 0) if not info["is_live"] else -1,
                                      info.get("categories", ["General"]))
    return sql_youtubedl.get_cache(url)


if __name__ == "__main__":
    LOOP.run_until_complete(main())
