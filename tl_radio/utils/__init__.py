from telethon.tl.custom import Button

index = 0


def build_queue(queue, page):
    res = "Current Queue:\n"
    nr = page * 10
    for x in queue:
        res += f"{nr}: {x}\n"
        nr += 1
    return res


def build_playback_buttons(is_paused, repeat_mode):
    play = "▶"
    pause = "⏸"
    back = "⏪"
    forward = "⏩"
    no_repeat = "🔄"
    repeat_playback = "🔂"
    repeat_queue = "🔁"
    buttons = []
    buttons.append(Button.inline(back, "ctrl_back"))
    if is_paused:
        buttons.append(Button.inline(play, "ctrl_resume"))
    else:
        buttons.append(Button.inline(pause, "ctrl_pause"))
    buttons.append(Button.inline(forward, "ctrl_forward"))
    if repeat_mode == 1:
        buttons.append(Button.inline(repeat_playback, "ctrl_repeat_playback"))
    elif repeat_mode == 2:
        buttons.append(Button.inline(repeat_queue, "ctrl_repeat_queue"))
    else:
        buttons.append(Button.inline(no_repeat, "ctrl_no_repeat"))
    return buttons


def format_queue(queue):
    global index
    pairs = [queue[x:x + 10] for x in range(0, len(queue), 10)]
    print(pairs)
    buttons = []
    if len(pairs) > 1:
        buttons.append(Button.inline("<", "queue_prev"))
        buttons.append(Button.inline("🔀", "queue_shuffle"))
        buttons.append(Button.inline(">", "queue_next"))
        if index >= len(pairs):
            index = 0
        if index < 0:
            index = len(pairs) - 1
    else:
        if len(pairs[0]) > 2:
            buttons.append(Button.inline("🔀", "queue_shuffle"))
    return [s.title for s in pairs[index]], buttons or None, index


def next_pairs():
    global index
    index += 1


def prev_pairs():
    global index
    if index > 0:
        index -= 1
