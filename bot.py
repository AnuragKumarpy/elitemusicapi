# =====================================================================
# Elite Music API — Production Telegram Supergroup Bot (@EliteMusicApiBot)
# =====================================================================
import os
import re
import asyncio
import time
import html
from typing import Optional, Dict, Any, List, Set

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    BufferedInputFile,
    BotCommand,
    ChatJoinRequest,
)
from app.config import settings
from app.services.logger.telegram_logger import admin_logger
from app.services.clone_manager import clone_manager
from app.services.extractor.resolver import MediaResolver
from app.services.media.card_generator import card_generator
from app.services.db_service import db_service
from app.services.help_manual import help_manual
from app.services.broadcaster import broadcaster
from app.services.channel_dashboard import ChannelDashboardService
from elitemusic import EliteMusicClient

# Custom Animated Emoji Tags (<tg-emoji>) from verified clean packs
E_CROWN = '<tg-emoji emoji-id="5217822164362739968">👑</tg-emoji>'
E_DIAMOND = '<tg-emoji emoji-id="5427168083074628963">💎</tg-emoji>'
E_LIGHTNING = '<tg-emoji emoji-id="5456140674028019486">⚡️</tg-emoji>'
E_FIRE = '<tg-emoji emoji-id="5033184522489825051">🔥</tg-emoji>'
E_SHIELD = '<tg-emoji emoji-id="5251203410396458957">🛡️</tg-emoji>'
E_CHECK = '<tg-emoji emoji-id="5237699328843200968">✅</tg-emoji>'
E_CROSS = '<tg-emoji emoji-id="5210952531676504517">❌</tg-emoji>'
E_HEADPHONES = '<tg-emoji emoji-id="5420216386448270341">🎧</tg-emoji>'
E_MUSIC = '<tg-emoji emoji-id="5350452584119279096">🎵</tg-emoji>'
E_ROBOT = '<tg-emoji emoji-id="5361741454685256344">🤖</tg-emoji>'
E_SEARCH = '<tg-emoji emoji-id="5231012545799666522">🔍</tg-emoji>'

# Sleek aesthetic mention link footer
POWERED_BY_FOOTER = '⚡ <i>Powered by</i> <a href="https://t.me/EliteBotsTelegram"><b>Elite Bots</b></a>'
MASTER_ADMINS = {8713594643, 6535726443, 7936713532, 5114938225}

# Verified Fleet Assistant User IDs (Only these are auto-approved on join requests)
ASSISTANT_USER_IDS: Set[int] = {
    7936713532,  # Ahilybiswas
    8182560464,  # memohini
    7636837556,  # grtfulraashi
    8883206998,  # ohsojaavni
    8558279811,  # manvisinghhh
    7902124879,  # shipsuhani
}

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
music_client = EliteMusicClient(
    api_key=settings.MASTER_ADMIN_KEY,
    base_url=f"http://localhost:{settings.PORT}/v1"
)
channel_dashboard = ChannelDashboardService(bot)

BOT_TOKEN_REGEX = re.compile(r"(\d{8,11}:[A-Za-z0-9_-]{35})")

# In-memory DSP profile state & active card messages per chat
room_dsp_state: Dict[int, Dict[str, Any]] = {}
active_player_cards: Dict[int, int] = {}


class CloneStates(StatesGroup):
    waiting_for_token = State()


def get_room_dsp(chat_id: int) -> Dict[str, Any]:
    if chat_id not in room_dsp_state:
        room_dsp_state[chat_id] = {
            "bass_on": False,
            "d8_on": False,
            "speed": 1.0,
            "is_paused": False
        }
    return room_dsp_state[chat_id]


async def auto_delete(message: Optional[Message], delay: int = 8):
    if not message:
        return
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception:
        pass


async def safe_edit_menu(event: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    try:
        if event.message and event.message.photo:
            await event.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="HTML")
        elif event.message:
            await event.message.edit_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            if event.message:
                await event.message.delete()
        except Exception:
            pass
        if event.message:
            await event.message.answer(text=text, reply_markup=reply_markup, parse_mode="HTML")
    try:
        await event.answer()
    except Exception:
        pass


async def get_chat_invite_link(chat_id: int) -> Optional[str]:
    try:
        return await bot.export_chat_invite_link(chat_id)
    except Exception:
        pass
    try:
        link = await bot.create_chat_invite_link(chat_id, name="Elite Music Assistant")
        return link.invite_link
    except Exception:
        pass
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
    except Exception:
        pass
    return None


def get_compact_emoji_keyboard(chat_id: int, is_paused: bool = False) -> InlineKeyboardMarkup:
    play_pause = (
        InlineKeyboardButton(
            text="▶️",
            callback_data=f"player:resume:{chat_id}",
        )
        if is_paused
        else InlineKeyboardButton(
            text="⏸️",
            callback_data=f"player:pause:{chat_id}",
        )
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                play_pause,
                InlineKeyboardButton(
                    text="⏭️",
                    callback_data=f"player:skip:{chat_id}",
                ),
                InlineKeyboardButton(
                    text="⏹️",
                    callback_data=f"player:stop:{chat_id}",
                ),
                InlineKeyboardButton(
                    text="🎛️",
                    callback_data=f"player:options:{chat_id}",
                ),
            ]
        ]
    )


def get_compact_options_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    dsp = get_room_dsp(chat_id)
    bass_on = dsp.get("bass_on", False)
    d8_on = dsp.get("d8_on", False)
    speed = dsp.get("speed", 1.0)

    bass_text = "🔊 ON (+6dB)" if bass_on else "🔊 OFF"
    bass_style = "success" if bass_on else "primary"

    d8_text = "🎧 8D: ON" if d8_on else "🎧 8D: OFF"
    d8_style = "success" if d8_on else "primary"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=bass_text,
                    callback_data=f"player:toggle_bass:{chat_id}",
                ),
                InlineKeyboardButton(
                    text=d8_text,
                    callback_data=f"player:toggle_8d:{chat_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⚡ {speed:.1f}x",
                    callback_data=f"player:cycle_speed:{chat_id}",
                ),
                InlineKeyboardButton(
                    text="📜 Queue",
                    callback_data=f"player:queue:{chat_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data=f"player:back:{chat_id}",
                )
            ]
        ]
    )


def get_start_menu_content(user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    caption = (
        f"{E_CROWN} <b>Welcome to Elite Music API, {user_name}!</b>\n\n"
        f"I am <b>@EliteMusicApiBot</b> — the premier ultra-low-latency <b>Telegram Voice Chat Audio Streaming Engine</b> {E_DIAMOND}\n\n"
        f"{E_HEADPHONES} <b>Key Features:</b>\n"
        f"• 🎵 <b>Lossless 320kbps Audio:</b> Zero buffering, crystal clear 48 kHz stereo sound.\n"
        f"• 🔊 <b>Dynamic Live DSP:</b> Real-time Bass Boost, 8D Spatial Audio, and Speed modifiers.\n"
        f"• 🤖 <b>7 Multi-Assistant Fleet:</b> High-density multi-VC streaming pool.\n"
        f"• 🚀 <b>Bot Clone Engine:</b> Turn any Bot Token into your personal music bot in 3 seconds.\n\n"
        f"👉 Add me to your group with Admin rights, start a Voice Chat, and send <code>/play &lt;song&gt;</code>!\n\n"
        f"{POWERED_BY_FOOTER}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Add to Supergroup",
                    url="https://t.me/EliteMusicApiBot?startgroup=true&admin=change_info+delete_messages+restrict_members+invite_users+pin_messages+manage_call",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Make Your Own Bot",
                    callback_data="menu:clone_prompt",
                ),
                InlineKeyboardButton(
                    text="Command Guide & FAQs",
                    callback_data="menu:help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="System Telemetry",
                    callback_data="menu:stats",
                )
            ]
        ]
    )
    return caption, kb


@dp.chat_join_request()
async def handle_chat_join_request(event: ChatJoinRequest):
    """Strictly auto-approve ONLY verified fleet assistant userbots."""
    if event.from_user and event.from_user.id in ASSISTANT_USER_IDS:
        try:
            await event.approve()
            print(f"[JoinRequests] Auto-approved verified assistant {event.from_user.id} in chat {event.chat.id}")
        except Exception as e:
            print(f"[JoinRequests] Failed to approve assistant join: {e}")


@dp.message(CommandStart())
@dp.message(F.text.regexp(r"^/start(?:@\w+)?(?:\s+(.*))?"))
async def handle_start(message: Message, state: FSMContext):
    if message.from_user:
        await db_service.track_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            is_bot=message.from_user.is_bot,
            source_bot="EliteMusicApiBot"
        )

    args = message.text.split()[1] if len(message.text.split()) > 1 else ""
    if args == "clone":
        await state.set_state(CloneStates.waiting_for_token)
        return await message.answer(
            f"{E_ROBOT} <b>Make Your Own Music Bot (Clone Engine)</b>\n\n"
            f"1. Open @BotFather on Telegram and send <code>/newbot</code>.\n"
            f"2. Choose a name and username for your music bot.\n"
            f"3. <b>Copy your Bot Token</b> or forward the message from BotFather here.\n\n"
            f"⚡ <i>Your bot will instantly start streaming 48kHz audio into your Voice Chats!</i>\n\n"
            f"{POWERED_BY_FOOTER}",
            parse_mode="HTML"
        )

    user_name = html.escape(message.from_user.first_name if message.from_user else "Friend")
    caption, kb = get_start_menu_content(user_name)

    try:
        banner_bytes = card_generator.generate_start_banner().getvalue()
        photo = BufferedInputFile(banner_bytes, filename="start_banner.jpg")
        await message.answer_photo(photo=photo, caption=caption, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await message.answer(text=caption, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data == "menu:start")
async def handle_start_menu_cb(query: CallbackQuery):
    user_name = html.escape(query.from_user.first_name if query.from_user else "Friend")
    caption, kb = get_start_menu_content(user_name)
    await safe_edit_menu(query, caption, kb)


@dp.message(Command("help"))
@dp.message(Command("manual"))
@dp.message(Command("faq"))
@dp.callback_query(F.data == "menu:help")
async def handle_help_command(event: Message | CallbackQuery):
    text, kb = help_manual.get_main_menu(bot_name="Elite Music Bot")
    if isinstance(event, CallbackQuery):
        await safe_edit_menu(event, text, kb)
    else:
        await event.answer(text=text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("menu:guide:"))
async def handle_help_guides(query: CallbackQuery):
    guide_type = query.data.split(":")[-1]
    if guide_type == "start":
        txt, kb = help_manual.get_getting_started()
    elif guide_type == "dsp":
        txt, kb = help_manual.get_dsp_guide()
    elif guide_type == "clone":
        txt, kb = help_manual.get_clone_guide()
    elif guide_type == "commands":
        txt, kb = help_manual.get_commands_guide()
    elif guide_type == "faq":
        txt, kb = help_manual.get_faq_guide()
    else:
        txt, kb = help_manual.get_main_menu(bot_name="Elite Music Bot")
    
    await safe_edit_menu(query, txt, kb)


@dp.message(Command("stats"))
@dp.callback_query(F.data == "menu:stats")
async def handle_stats_menu(event: Message | CallbackQuery):
    net_stats = await db_service.get_network_stats()
    text = (
        f"{E_DIAMOND} <b>ELITE MUSIC ENGINE — SYSTEM TELEMETRY</b>\n\n"
        f"• 👥 <b>Total Tracked Users:</b> <code>{net_stats['total_users']}</code>\n"
        f"• 💬 <b>Total Active Groups:</b> <code>{net_stats['active_chats']}</code>\n"
        f"• 🤖 <b>Assistant Standby Fleet:</b> <code>7 Priority Userbots (Multi-VC Density)</code>\n"
        f"• ⚡ <b>Audio Resolution:</b> <code>Lossless 320kbps / 48kHz PCM</code>\n"
        f"• 🛡️ <b>Engine Status:</b> <code>100% HEALTHY (AWS eu-north-1)</code>\n\n"
        f"{POWERED_BY_FOOTER}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Back to Menu", callback_data="menu:start")]
        ]
    )
    if isinstance(event, CallbackQuery):
        await safe_edit_menu(event, text, kb)
    else:
        await event.answer(text=text, reply_markup=kb, parse_mode="HTML")


@dp.message(Command("clone"))
@dp.callback_query(F.data == "menu:clone_prompt")
async def handle_clone_command(event: Message | CallbackQuery, state: FSMContext):
    await state.set_state(CloneStates.waiting_for_token)
    text = (
        f"{E_ROBOT} <b>Make Your Own Music Bot (Clone Engine)</b>\n\n"
        f"1. Open @BotFather and create a new bot (<code>/newbot</code>).\n"
        f"2. Copy the <b>HTTP API Token</b> or <b>forward the BotFather message</b> directly here.\n\n"
        f"⚡ <i>Your bot will instantly go live and start streaming in your groups!</i>\n\n"
        f"{POWERED_BY_FOOTER}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Back to Menu", callback_data="menu:start")]
        ]
    )
    if isinstance(event, CallbackQuery):
        await safe_edit_menu(event, text, kb)
    else:
        await event.answer(text=text, reply_markup=kb, parse_mode="HTML")


@dp.message(CloneStates.waiting_for_token)
@dp.message(F.forward_from.username == "BotFather")
async def process_clone_token(message: Message, state: FSMContext):
    raw_text = message.text or (message.caption if message.caption else "")
    match = BOT_TOKEN_REGEX.search(raw_text)
    if not match:
        msg = await message.reply(
            f"{E_CROSS} <b>Invalid Token Format!</b>\n\n"
            f"Please send a valid Telegram Bot Token from @BotFather (e.g. <code>123456789:ABCdefGHIjklMNOpqrSTUvwxYZ</code>).\n\n"
            f"{POWERED_BY_FOOTER}",
            parse_mode="HTML"
        )
        asyncio.create_task(auto_delete(msg, delay=10))
        return

    token = match.group(1)
    status_msg = await message.reply("⚙️ Verifying token with Telegram & provisioning clone runner...", parse_mode="HTML")

    try:
        user_id = message.from_user.id if message.from_user else 0
        user_name = message.from_user.full_name if message.from_user else "User"

        clone_res = await clone_manager.add_clone(
            token=token,
            owner_id=user_id,
            owner_name=user_name
        )

        bot_uname = clone_res["username"]
        bot_title = clone_res["first_name"]

        await state.clear()
        card = (
            f"{E_CHECK} <b>YOUR MUSIC BOT IS NOW LIVE!</b>\n\n"
            f"• 🤖 <b>Bot Name:</b> <b>{html.escape(bot_title)}</b>\n"
            f"• 🔗 <b>Username:</b> @{bot_uname}\n"
            f"• ⚡ <b>Status:</b> <code>RUNNING (High-Speed PCM 48kHz)</code>\n"
            f"• 🛡️ <b>Plan Quota:</b> <code>500 Free Songs/Day (10 Concurrent VCs)</code>\n\n"
            f"👉 <b>How to Use:</b>\n"
            f"1. Add @{bot_uname} to your group as Admin.\n"
            f"2. Start a Voice Chat and send <code>/play &lt;song&gt;</code>!\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"Add @{bot_uname} to Group",
                        url=f"https://t.me/{bot_uname}?startgroup=true&admin=change_info+delete_messages+restrict_members+invite_users+pin_messages+manage_call",
                    )
                ]
            ]
        )
        await status_msg.edit_text(card, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"{E_CROSS} <b>Clone Setup Failed:</b> <code>{html.escape(str(e))}</code>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(status_msg, delay=12))


@dp.message(F.text.regexp(r"^/broadcast(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
@dp.message(F.text.regexp(r"^/gcast(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
@dp.message(F.text.regexp(r"^/broadcast_all(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_master_broadcast(message: Message):
    if not message.from_user or message.from_user.id not in MASTER_ADMINS:
        return

    cmd_word = (message.text or "").split()[0]
    if "@" in cmd_word and not cmd_word.lower().endswith("@elitemusicapibot"):
        return

    tokens = message.text.split() if message.text else []
    mode = "all"
    pin_flag = False

    for t in tokens[1:]:
        low = t.lower()
        if low in ["-all", "all", "-a"]:
            mode = "all"
        elif low in ["-users", "users", "-u", "-user", "user"]:
            mode = "users"
        elif low in ["-groups", "groups", "-g", "-group", "group", "-chats", "chats", "-c"]:
            mode = "groups"
        elif low in ["-pin", "pin", "-p"]:
            pin_flag = True

    if message.text and message.text.startswith("/gcast"):
        mode = "groups"

    payload_msg = message.reply_to_message or message
    if payload_msg == message and len(tokens) <= 1:
        help_msg = (
            "ℹ️ <b>How to Broadcast:</b>\n\n"
            "1. Send any photo, video, sticker, animation/GIF, audio, or text.\n"
            "2. Reply to it with:\n"
            "• <code>/broadcast -all</code> — Send to all users & groups\n"
            "• <code>/broadcast -users</code> — Send to all users (DMs)\n"
            "• <code>/broadcast -groups</code> — Send to all groups\n"
            "• Add <code>-pin</code> to pin in supergroups (e.g. <code>/broadcast -all -pin</code>)\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        await message.reply(help_msg, parse_mode="HTML")
        return

    user_ids = await db_service.get_all_user_ids(source_bot="global") if mode in ["all", "users"] else []
    chat_ids = await db_service.get_all_chat_ids(source_bot="global") if mode in ["all", "groups"] else []

    targets = [(uid, False) for uid in user_ids] + [(cid, True) for cid in chat_ids]
    if not targets:
        return await message.reply(f"ℹ️ No active destinations found in database for mode: <code>{mode}</code>.", parse_mode="HTML")

    status_msg = await message.reply(f"🚀 Initializing broadcast to <b>{len(targets)} total destinations</b> ({mode.upper()})...", parse_mode="HTML")

    total = len(targets)
    success, failed = 0, 0
    t0 = time.time()

    for idx, (target_id, is_grp) in enumerate(targets, start=1):
        try:
            sent = await payload_msg.copy_to(chat_id=target_id)
            success += 1
            if is_grp and pin_flag and sent:
                try:
                    await bot.pin_chat_message(chat_id=target_id, message_id=sent.message_id, disable_notification=True)
                except Exception:
                    pass
        except Exception:
            failed += 1

        if idx % 20 == 0:
            await asyncio.sleep(0.5)

    elapsed = round(time.time() - t0, 1)
    report = (
        f"📢 <b>BROADCAST OPERATION COMPLETE!</b>\n\n"
        f"• 🎯 <b>Target Scope:</b> <code>{mode.upper()}</code>\n"
        f"• 👥 <b>Total Targets:</b> <code>{total:,}</code>\n"
        f"• 🟢 <b>Successfully Delivered:</b> <code>{success:,}</code>\n"
        f"• 🔴 <b>Blocked / Failed:</b> <code>{failed:,}</code>\n"
        f"• ⏱️ <b>Time Elapsed:</b> <code>{elapsed}s</code>\n\n"
        f"{POWERED_BY_FOOTER}"
    )
    await status_msg.edit_text(report, parse_mode="HTML")




@dp.message(F.text.regexp(r"^[!/.?]?(?:ytdlp|yt_dlp|testdl)(?:@\w+)?(?:\s+([\s\S]*))?$", flags=re.IGNORECASE))
async def handle_ytdlp_diag(message: Message):
    if not message.from_user or message.from_user.id not in MASTER_ADMINS:
        return

    match = re.search(r"^[!/.?]?(?:ytdlp|yt_dlp|testdl)(?:@\w+)?(?:\s+([\s\S]*))?$", message.text or "", flags=re.IGNORECASE)
    query = match.group(1).strip() if match and match.group(1) else ""
    if not query:
        await message.reply(
            f"ℹ️ <b>Usage:</b> <code>/ytdlp &lt;song name or YouTube URL&gt;</code>\n\n"
            f"<i>Tests multi-tier extractor, yt-dlp binary, download throughput, and direct stream health.</i>\n\n"
            f"{POWERED_BY_FOOTER}",
            parse_mode="HTML"
        )
        return

    status_msg = await message.reply(
        f"🔍 <b>Testing Downloader Engine...</b>\n\n"
        f"• <b>Query:</b> <code>{html.escape(query)}</code>\n"
        f"• <b>Mode:</b> <code>Audio & Video Stream Diagnostics</code>\n\n"
        f"⏳ <i>Probing YouTube v3, Lossless 320kbps CDN & yt-dlp...</i>",
        parse_mode="HTML"
    )

    t_start = time.time()
    try:
        # 1. Resolve metadata & streams
        track = await MediaResolver.resolve(
            query=query,
            tier="master",
            is_video=True,
            requested_by=None
        )
        resolve_time_ms = int((time.time() - t_start) * 1000)

        # 2. Test downloading a sample stream chunk to verify real bandwidth
        dl_status = "Skipped"
        dl_speed_kbps = 0
        if track.stream_url and track.stream_url.startswith("http"):
            try:
                import aiohttp
                t_dl_start = time.time()
                bytes_downloaded = 0
                async with aiohttp.ClientSession() as session:
                    async with session.get(track.stream_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        chunk = await resp.content.read(1024 * 512)
                        bytes_downloaded = len(chunk)
                t_dl_sec = time.time() - t_dl_start
                if t_dl_sec > 0 and bytes_downloaded > 0:
                    dl_speed_kbps = int((bytes_downloaded * 8) / (t_dl_sec * 1024))
                    dl_status = f"✅ Success ({bytes_downloaded/1024:.1f} KB in {t_dl_sec*1000:.0f}ms | ~{dl_speed_kbps} kbps)"
                else:
                    dl_status = "⚠️ Stream responded but 0 bytes read"
            except Exception as dl_err:
                dl_status = f"❌ Download error: {html.escape(str(dl_err))[:60]}"

        # 3. Format complete diagnostic card
        masked_url = track.stream_url[:50] + "..." if track.stream_url else "None"
        report = (
            f"⚡ <b>YTDLP & STREAM ENGINE DIAGNOSTICS</b>\n\n"
            f"• 🎯 <b>Query:</b> <code>{html.escape(query)}</code>\n"
            f"• 🎵 <b>Title:</b> <b>{html.escape(track.title)}</b>\n"
            f"• 👤 <b>Artist:</b> {html.escape(track.artist)}\n"
            f"• ⏱️ <b>Duration:</b> <code>{track.duration_seconds}s ({track.duration_seconds//60}:{track.duration_seconds%60:02d})</code>\n"
            f"• 🌐 <b>Source Engine:</b> <code>{track.source}</code>\n"
            f"• ⚡ <b>Resolve Latency:</b> <code>{resolve_time_ms} ms</code>\n"
            f"• 📥 <b>Stream Download Test:</b> {dl_status}\n"
            f"• 🔗 <b>Stream URL:</b> <code>{html.escape(masked_url)}</code>\n"
            f"• 🖼️ <b>Artwork / Thumbnail:</b> <a href='{track.thumbnail_url}'>Preview HD</a>\n\n"
            f"{POWERED_BY_FOOTER}"
        )

        await status_msg.edit_text(report, parse_mode="HTML", disable_web_page_preview=False)

    except Exception as e:
        await status_msg.edit_text(
            f"{E_CROSS} <b>Extractor Failed:</b> <code>{html.escape(str(e))}</code>\n\n"
            f"⏱️ <i>Time elapsed: {int((time.time() - t_start)*1000)}ms</i>\n\n"
            f"{POWERED_BY_FOOTER}",
            parse_mode="HTML"
        )


@dp.message(F.text.regexp(r"^[!/.?]?(?:play|vplay|p)(?:@\w+)?(?:\s+([\s\S]*))?$", flags=re.IGNORECASE) | F.caption.regexp(r"^[!/.?]?(?:play|vplay|p)(?:@\w+)?(?:\s+([\s\S]*))?$", flags=re.IGNORECASE))
async def handle_play(message: Message):
    if not message.chat or message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        msg = await message.reply(f"{E_SHIELD} Please use <code>/play</code> inside a Telegram Group Voice Chat.\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        return

    await db_service.track_chat(
        chat_id=message.chat.id,
        title=message.chat.title,
        chat_type=str(message.chat.type),
        username=message.chat.username,
        added_by_user_id=message.from_user.id if message.from_user else None,
        source_bot="EliteMusicApiBot"
    )

    raw_text = message.text or ""
    is_video = bool(re.match(r"^[!/.?]?(?:vplay|video)", raw_text, flags=re.IGNORECASE))
    query = re.sub(r"^[!/.?]?(?:play|vplay|video|p)(?:@\w+)?\s*", "", raw_text, flags=re.IGNORECASE).strip()

    if not query and message.reply_to_message:
        reply = message.reply_to_message
        file_obj = reply.audio or reply.voice or reply.document
        if file_obj:
            status_msg = await message.reply("📥 Downloading replied audio file...", parse_mode="HTML")
            try:
                tg_file = await bot.get_file(file_obj.file_id)
                dest_path = f"/tmp/tg_audio_{file_obj.file_unique_id}.mp3"
                await bot.download_file(tg_file.file_path, destination=dest_path)
                query = dest_path
            except Exception as e:
                await status_msg.edit_text(f"⚠️ Failed to process replied audio: {html.escape(str(e))}", parse_mode="HTML")
                asyncio.create_task(auto_delete(status_msg, delay=8))
                return

    if not query:
        msg = await message.reply(f"ℹ️ <b>Usage:</b> <code>/play &lt;song name, URL, or reply to an audio file&gt;</code>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        return

    load_text = f"{E_SEARCH} <b>Loading video stream...</b>" if is_video else f"{E_SEARCH} <b>Loading audio stream...</b>"
    status_msg = await message.reply(load_text, parse_mode="HTML")

    try:
        user_id = message.from_user.id if message.from_user else 0
        user_name = message.from_user.full_name if message.from_user else "User"

        invite_link = await get_chat_invite_link(message.chat.id)

        if is_video:
            result = await music_client.play_video(
                chat_id=message.chat.id,
                query=query,
                resolution="720p",
                requested_by_id=user_id,
                requested_by_name=user_name,
                invite_link=invite_link
            )
        else:
            user_dsp_dict = await db_service.get_user_dsp(user_id)
            track_dsp = DSPConfig(**user_dsp_dict) if user_dsp_dict else None
            result = await music_client.play(
                chat_id=message.chat.id,
                query=query,
                requested_by_id=user_id,
                requested_by_name=user_name,
                invite_link=invite_link,
                dsp=track_dsp
            )

        badge = f"{E_MUSIC} <b>NOW STREAMING:</b>" if result.status == "STREAMING" else "⏳ <b>ADDED TO QUEUE:</b>"
        mins, secs = divmod(result.track.duration_seconds, 60)

        caption = (
            f"{E_HEADPHONES} <b>ELITE PLAYER</b>\n\n"
            f"{badge}\n"
            f"• 🎵 <b>Title:</b> <b>{html.escape(result.track.title)}</b>\n"
            f"• 👤 <b>Artist:</b> <i>{html.escape(result.track.artist or 'Various Artists')}</i>\n"
            f"• ⏱️ <b>Duration:</b> <code>{mins:02d}:{secs:02d}</code>\n"
            f"• 👤 <b>Requested By:</b> <b>{html.escape(user_name)}</b>\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        dsp = get_room_dsp(message.chat.id)
        dsp["is_paused"] = False

        prev_card_id = active_player_cards.get(message.chat.id)
        if prev_card_id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=prev_card_id)
            except Exception:
                pass

        photo_sent = False
        try:
            card_bytes = card_generator.generate_player_card(
                title=result.track.title,
                artist=result.track.artist or "Various Artists",
                duration_sec=result.track.duration_seconds,
                thumbnail_url=result.track.thumbnail_url,
                requested_by=user_name
            ).getvalue()
            photo = BufferedInputFile(card_bytes, filename="now_playing.jpg")
            card_msg = await message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=get_compact_emoji_keyboard(message.chat.id, is_paused=False)
            )
            active_player_cards[message.chat.id] = card_msg.message_id
            await status_msg.delete()
            photo_sent = True
        except Exception as card_err:
            print(f"[Bot] Failed to send photo card: {card_err}")

        if not photo_sent:
            if result.track.thumbnail_url:
                try:
                    from aiogram.types import URLInputFile
                    card_msg = await message.answer_photo(
                        photo=URLInputFile(result.track.thumbnail_url),
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=get_compact_emoji_keyboard(message.chat.id, is_paused=False)
                    )
                    active_player_cards[message.chat.id] = card_msg.message_id
                    await status_msg.delete()
                    photo_sent = True
                except Exception:
                    pass

        if not photo_sent:
            card_msg = await status_msg.edit_text(caption, parse_mode="HTML", reply_markup=get_compact_emoji_keyboard(message.chat.id, is_paused=False))
            active_player_cards[message.chat.id] = card_msg.message_id

        await admin_logger.log_stream_event(
            event="PLAY_AUDIO",
            room_id=message.chat.id,
            track_title=result.track.title,
            duration_sec=result.track.duration_seconds,
            worker_node=result.worker_node,
            tier="Master"
        )
    except Exception as err:
        err_str = str(err)
        if "GROUPCALL_INVALID" in err_str or "No active group call" in err_str:
            msg = f"⚠️ <b>Voice Chat is not active!</b>\n\nPlease start or open the Voice Chat in this group, then send <code>/play</code> again.\n\n{POWERED_BY_FOOTER}"
        else:
            msg = f"⚠️ <b>Playback Notice:</b> <code>{html.escape(err_str)}</code>\n\n{POWERED_BY_FOOTER}"
        await status_msg.edit_text(msg, parse_mode="HTML")
        asyncio.create_task(auto_delete(status_msg, delay=10))


@dp.message(F.text.regexp(r"^[!/.?]?(?:pause|cpause)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_pause_cmd(message: Message):
    try:
        await music_client.pause(message.chat.id)
        dsp = get_room_dsp(message.chat.id)
        dsp["is_paused"] = True
        msg = await message.reply(f"⏸️ Playback paused.\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=6))
        asyncio.create_task(auto_delete(message, delay=6))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:resume|cresume)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_resume_cmd(message: Message):
    try:
        await music_client.resume(message.chat.id)
        dsp = get_room_dsp(message.chat.id)
        dsp["is_paused"] = False
        msg = await message.reply(f"▶️ Playback resumed.\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=6))
        asyncio.create_task(auto_delete(message, delay=6))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:skip|cskip|next)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_skip_cmd(message: Message):
    try:
        res = await music_client.skip(message.chat.id)
        if res and res.track:
            dur_m = res.track.duration_seconds // 60
            dur_s = res.track.duration_seconds % 60
            duration_fmt = f"{dur_m:02d}:{dur_s:02d}"
            text = (
                f"⏭️ <b>NOW STREAMING NEXT TRACK:</b>\n\n"
                f"• 🎵 <b>Title:</b> <b>{html.escape(res.track.title)}</b>\n"
                f"• 👤 <b>Artist:</b> <i>{html.escape(res.track.artist)}</i>\n"
                f"• ⏱ <b>Duration:</b> <code>{duration_fmt}</code>\n\n"
                f"{POWERED_BY_FOOTER}"
            )
            msg = await message.reply(text, parse_mode="HTML", reply_markup=get_compact_emoji_keyboard(message.chat.id))
        else:
            msg = await message.reply(f"⏹️ <b>Queue is empty. Playback stopped.</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=10))
        asyncio.create_task(auto_delete(message, delay=6))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:stop|cstop|end)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_stop_cmd(message: Message):
    try:
        await music_client.stop(message.chat.id)
        room_dsp_state.pop(message.chat.id, None)
        prev_card_id = active_player_cards.pop(message.chat.id, None)
        if prev_card_id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=prev_card_id)
            except Exception:
                pass
        msg = await message.reply(f"⏹️ Playback stopped & Voice Chat session ended.\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        asyncio.create_task(auto_delete(message, delay=8))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^/bass(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_bass_cmd(message: Message):
    dsp = get_room_dsp(message.chat.id)
    parts = message.text.split()
    if len(parts) > 1 and parts[1].lower() in ("off", "0", "disable", "reset"):
        db = 0.0
        dsp["bass_on"] = False
    elif len(parts) > 1 and parts[1].replace(".", "", 1).isdigit():
        db = float(parts[1])
        dsp["bass_on"] = (db > 0)
    else:
        dsp["bass_on"] = not dsp["bass_on"]
        db = 6.0 if dsp["bass_on"] else 0.0

    try:
        await music_client.set_dsp(message.chat.id, bass_boost_db=db)
        if dsp["bass_on"]:
            msg = await message.reply(f"{E_FIRE} <b>Bass Boost (+{db:.1f} dB) enabled!</b>\n⚡ <i>Effect armed for upcoming & queued songs.</i>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        else:
            msg = await message.reply(f"{E_CHECK} <b>Bass Boost disabled.</b> Upcoming songs will play flat.\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        asyncio.create_task(auto_delete(message, delay=8))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^/8d(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_8d_cmd(message: Message):
    dsp = get_room_dsp(message.chat.id)
    parts = message.text.split()
    if len(parts) > 1 and parts[1].lower() in ("off", "0", "disable", "reset"):
        dsp["d8_on"] = False
    elif len(parts) > 1 and parts[1].lower() in ("on", "1", "enable"):
        dsp["d8_on"] = True
    else:
        dsp["d8_on"] = not dsp["d8_on"]

    try:
        await music_client.set_dsp(message.chat.id, spatial_8d=dsp["d8_on"])
        if dsp["d8_on"]:
            msg = await message.reply(f"{E_HEADPHONES} <b>8D Spatial Audio enabled!</b>\n⚡ <i>Effect armed for upcoming & queued songs.</i>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        else:
            msg = await message.reply(f"{E_CHECK} <b>8D Spatial Audio disabled.</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        asyncio.create_task(auto_delete(message, delay=8))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))



@dp.message(F.text.regexp(r"^[!/.?]?(?:queue|q|cqueue)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_queue_cmd(message: Message):
    try:
        state = await music_client.get_room_state(message.chat.id)
        if not state or not state.current_track:
            msg = await message.reply(f"ℹ️ <b>No active playback session in this group.</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
            asyncio.create_task(auto_delete(msg, delay=8))
            return

        cur = state.current_track
        dur_m = cur.duration_seconds // 60
        dur_s = cur.duration_seconds % 60
        queue_text = f"🎧 <b>ACTIVE PLAYBACK & QUEUE</b>\n\n"
        queue_text += f"🎵 <b>Now Playing:</b> <b>{html.escape(cur.title)}</b> — <i>{html.escape(cur.artist)}</i> (<code>{dur_m:02d}:{dur_s:02d}</code>)\n"
        queue_text += f"📊 <b>Status:</b> <code>{state.status}</code> | 🔊 <b>Listeners:</b> <code>{state.connected_listeners}</code>\n\n"

        if state.queue:
            queue_text += f"📜 <b>Upcoming Tracks ({len(state.queue)}):</b>\n"
            for i, trk in enumerate(state.queue[:10], start=1):
                tm = trk.duration_seconds // 60
                ts = trk.duration_seconds % 60
                queue_text += f"<b>{i}.</b> {html.escape(trk.title[:30])} — <i>{html.escape(trk.artist[:20])}</i> [<code>{tm:02d}:{ts:02d}</code>]\n"
            if len(state.queue) > 10:
                queue_text += f"<i>...and {len(state.queue) - 10} more in queue.</i>\n"
        else:
            queue_text += "ℹ️ <i>Queue is currently empty. Use <code>/play <song></code> to add more.</i>\n"

        queue_text += f"\n{POWERED_BY_FOOTER}"
        msg = await message.reply(queue_text, parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=20))
        asyncio.create_task(auto_delete(message, delay=8))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:np|nowplaying|cnowplaying)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_np_cmd(message: Message):
    try:
        state = await music_client.get_room_state(message.chat.id)
        if not state or not state.current_track:
            msg = await message.reply(f"ℹ️ <b>Nothing is currently streaming.</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
            asyncio.create_task(auto_delete(msg, delay=8))
            return

        cur = state.current_track
        dur_m = cur.duration_seconds // 60
        dur_s = cur.duration_seconds % 60
        elapsed_sec = int(state.progress_ms / 1000)
        el_m = elapsed_sec // 60
        el_s = elapsed_sec % 60

        text = (
            f"🎧 <b>NOW STREAMING IN VC</b>\n\n"
            f"• 🎵 <b>Title:</b> <b>{html.escape(cur.title)}</b>\n"
            f"• 👤 <b>Artist:</b> <i>{html.escape(cur.artist)}</i>\n"
            f"• ⏱ <b>Progress:</b> <code>{el_m:02d}:{el_s:02d} / {dur_m:02d}:{dur_s:02d}</code>\n"
            f"• 📊 <b>Status:</b> <code>{state.status}</code>\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        msg = await message.reply(text, parse_mode="HTML", reply_markup=get_compact_emoji_keyboard(message.chat.id))
        asyncio.create_task(auto_delete(msg, delay=15))
        asyncio.create_task(auto_delete(message, delay=8))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:speed)(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_speed_cmd(message: Message):
    dsp = get_room_dsp(message.chat.id)
    parts = message.text.split() if message.text else []
    if len(parts) > 1 and parts[1].replace(".", "", 1).isdigit():
        spd = max(0.5, min(2.0, float(parts[1])))
    else:
        current_spd = dsp.get("speed", 1.0)
        spd = 1.2 if current_spd == 1.0 else (1.5 if current_spd == 1.2 else 1.0)

    dsp["speed"] = spd
    try:
        await music_client.set_dsp(message.chat.id, speed=spd)
        msg = await message.reply(f"⚡ <b>Playback Speed set to {spd:.1f}x</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        asyncio.create_task(auto_delete(message, delay=8))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:seek)(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_seek_cmd(message: Message):
    parts = message.text.split() if message.text else []
    if len(parts) <= 1 or not parts[1].isdigit():
        msg = await message.reply("ℹ️ <b>Usage:</b> <code>/seek &lt;seconds&gt;</code> (e.g. <code>/seek 60</code>)", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        return

    seek_target_ms = int(parts[1]) * 1000
    try:
        await music_client.seek(message.chat.id, target_ms=seek_target_ms)
        msg = await message.reply(f"⏩ <b>Seeked to {parts[1]}s</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))
        asyncio.create_task(auto_delete(message, delay=8))
    except Exception as e:
        msg = await message.reply(f"{E_CROSS} Error: {html.escape(str(e))}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=8))


@dp.callback_query(F.data.startswith("player:"))
async def handle_player_callback(query: CallbackQuery):
    parts = query.data.split(":")
    action = parts[1]
    chat_id = int(parts[2])
    dsp = get_room_dsp(chat_id)

    try:
        if action == "pause":
            await music_client.pause(chat_id)
            dsp["is_paused"] = True
            await query.answer("Paused")
            if query.message:
                await query.message.edit_reply_markup(reply_markup=get_compact_emoji_keyboard(chat_id, is_paused=True))
        elif action == "resume":
            await music_client.resume(chat_id)
            dsp["is_paused"] = False
            await query.answer("Resumed")
            if query.message:
                await query.message.edit_reply_markup(reply_markup=get_compact_emoji_keyboard(chat_id, is_paused=False))
        elif action == "skip":
            res = await music_client.skip(chat_id)
            if res and res.track:
                dur_m = res.track.duration_seconds // 60
                dur_s = res.track.duration_seconds % 60
                duration_fmt = f"{dur_m:02d}:{dur_s:02d}"
                await query.answer(f"Skipped to: {res.track.title[:25]}")
                if query.message:
                    text = (
                        f"🎧 <b>ELITE MUSIC PLAYER</b>\n\n"
                        f"🎵 <b>NOW STREAMING:</b>\n"
                        f"• 🎵 <b>Title:</b> <b>{html.escape(res.track.title)}</b>\n"
                        f"• 👤 <b>Artist:</b> <i>{html.escape(res.track.artist)}</i>\n"
                        f"• ⏱ <b>Duration:</b> <code>{duration_fmt}</code>\n\n"
                        f"{POWERED_BY_FOOTER}"
                    )
                    await query.message.edit_text(text=text, reply_markup=get_compact_emoji_keyboard(chat_id), parse_mode="HTML")
            else:
                await query.answer("Queue empty. Playback stopped.")
                if query.message:
                    await query.message.delete()
        elif action == "stop":
            await music_client.stop(chat_id)
            room_dsp_state.pop(chat_id, None)
            active_player_cards.pop(chat_id, None)
            await query.answer("Stopped")
            if query.message:
                await query.message.delete()
        elif action == "options":
            await query.answer()
            if query.message:
                await query.message.edit_reply_markup(reply_markup=get_compact_options_keyboard(chat_id))
        elif action == "back":
            await query.answer()
            if query.message:
                await query.message.edit_reply_markup(reply_markup=get_compact_emoji_keyboard(chat_id, is_paused=dsp.get("is_paused", False)))
        elif action == "toggle_bass":
            dsp["bass_on"] = not dsp.get("bass_on", False)
            db = 6.0 if dsp["bass_on"] else 0.0
            await music_client.set_dsp(chat_id, bass_boost_db=db)
            alert_text = "🔊 Bass Boost (+6dB) Armed!" if dsp["bass_on"] else "🔊 Bass Boost Disabled."
            await query.answer(alert_text, show_alert=True)
            if query.message:
                await query.message.edit_reply_markup(reply_markup=get_compact_options_keyboard(chat_id))
        elif action == "toggle_8d":
            dsp["d8_on"] = not dsp.get("d8_on", False)
            await music_client.set_dsp(chat_id, spatial_8d=dsp["d8_on"])
            alert_text = "🎧 8D Spatial Audio Armed!" if dsp["d8_on"] else "🎧 8D Spatial Audio Disabled."
            await query.answer(alert_text, show_alert=True)
            if query.message:
                await query.message.edit_reply_markup(reply_markup=get_compact_options_keyboard(chat_id))
        elif action == "cycle_speed":
            current_spd = dsp.get("speed", 1.0)
            new_spd = 1.2 if current_spd == 1.0 else (1.5 if current_spd == 1.2 else 1.0)
            dsp["speed"] = new_spd
            await music_client.set_dsp(chat_id, speed=new_spd)
            await query.answer(f"⚡ Speed set to {new_spd:.1f}x!", show_alert=True)
            if query.message:
                await query.message.edit_reply_markup(reply_markup=get_compact_options_keyboard(chat_id))
        elif action == "queue":
            try:
                state = await music_client.get_room_state(chat_id)
                current = state.current_track.title if state.current_track else 'None'
                await query.answer(f"Queue: {state.queue_length} tracks\nNow: {current}", show_alert=True)
            except Exception:
                await query.answer("No active queue for this room.", show_alert=True)
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


async def main():
    print("🤖 @EliteMusicApiBot Production Daemon Starting...")
    await db_service.initialize()
    await admin_logger.start()

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Start bot & open control menu"),
            BotCommand(command="play", description="Play audio / replied media in VC"),
            BotCommand(command="pause", description="Pause current playback"),
            BotCommand(command="resume", description="Resume playback"),
            BotCommand(command="skip", description="Skip to next track"),
            BotCommand(command="stop", description="Stop playback & end VC session"),
            BotCommand(command="bass", description="Toggle Bass Boost (+6dB)"),
            BotCommand(command="8d", description="Toggle 8D Spatial Audio"),
            BotCommand(command="speed", description="Change playback speed"),
            BotCommand(command="clone", description="Make your own music bot"),
            BotCommand(command="help", description="Knowledge base & FAQ manual"),
            BotCommand(command="stats", description="System & network telemetry"),
            BotCommand(command="broadcast", description="Mass announcement to users (Admin)"),
            BotCommand(command="gcast", description="Mass announcement to groups (Admin)"),
        ])
    except Exception as e:
        print(f"[Bot] Failed to set bot commands: {e}")

    try:
        await bot.set_my_description(
            description="🎵 The premier ultra-low-latency Telegram Voice Chat Music Streaming Engine.\n\n"
                        "💎 Lossless 320kbps / 48kHz Stereo Audio\n"
                        "🔊 Real-Time Live DSP: Bass Boost, 8D Spatial Audio, Tempo Scaling\n"
                        "🤖 Bot Clone Engine: Create your personal music bot in 3 seconds\n\n"
                        "⚡ Powered by Elite Bots (@EliteBotsTelegram)"
        )
        await bot.set_my_short_description(
            short_description="Ultra-fast Telegram Voice Chat Music Bot with Lossless 320kbps Audio & Live DSP."
        )
    except Exception as e:
        print(f"[Bot] Failed to set description: {e}")

    await clone_manager.load_and_start_clones()
    
    # Start live channel telemetry dashboard in @EliteBotsTelegram
    # channel_dashboard.start() delegated to master Telethon syncer

    await admin_logger.log_system_health(
        active_streams=0,
        worker_ram_mb=48.0,
        ipv6_status="7 Active Priority Assistants Online (Multi-VC Density)"
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



@dp.message(F.text.regexp(r"^[!/.?]?(?:setdsp)(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_setdsp_cmd(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    text = (message.text or "").strip()
    parts = text.split()

    if len(parts) < 3:
        usage = (
            f"🎛️ <b>Personal DSP Configuration Guide</b>\n\n"
            f"Configure your personal sound profile. All songs you queue will automatically be rendered with your custom DSP ahead of time!\n\n"
            f"• <code>/setdsp bass &lt;0-15&gt;</code> — Set Bass Boost dB (e.g. <code>/setdsp bass 10</code>)\n"
            f"• <code>/setdsp 8d &lt;on|off&gt;</code> — Enable 360° Circular Spatial Audio\n"
            f"• <code>/setdsp nightcore &lt;on|off&gt;</code> — Enable 1.25x High-Tempo Nightcore\n"
            f"• <code>/setdsp speed &lt;0.5-2.0&gt;</code> — Set playback speed (e.g. <code>/setdsp speed 1.2</code>)\n"
            f"• <code>/mydsp</code> — View your current active DSP profile\n"
            f"• <code>/cleardsp</code> — Reset to clean studio sound\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        msg = await message.reply(usage, parse_mode="HTML")
        asyncio.create_task(auto_delete(msg, delay=15))
        return

    mode = parts[1].lower()
    val = parts[2].lower()

    if mode == "bass":
        try:
            db_val = max(0.0, min(15.0, float(val)))
            await db_service.set_user_dsp(user_id, bass_boost_db=db_val)
            res = f"🔊 <b>Bass Boost set to +{db_val:.1f} dB</b> for your queued songs!"
        except Exception:
            res = "⚠️ Invalid bass value. Choose between 0 and 15 dB."
    elif mode in ("8d", "d8", "spatial"):
        is_on = val in ("on", "1", "true", "enable")
        await db_service.set_user_dsp(user_id, spatial_8d=is_on)
        res = f"🎧 <b>8D Spatial Audio {'ENABLED' if is_on else 'DISABLED'}</b> for your queued songs!"
    elif mode in ("nightcore", "nc"):
        is_on = val in ("on", "1", "true", "enable")
        await db_service.set_user_dsp(user_id, nightcore=is_on)
        res = f"⚡ <b>Nightcore Mode {'ENABLED' if is_on else 'DISABLED'}</b> for your queued songs!"
    elif mode == "speed":
        try:
            spd_val = max(0.5, min(2.0, float(val)))
            await db_service.set_user_dsp(user_id, speed=spd_val)
            res = f"⏱️ <b>Playback Speed set to {spd_val:.2f}x</b> for your queued songs!"
        except Exception:
            res = "⚠️ Invalid speed value. Choose between 0.5 and 2.0x."
    else:
        res = f"⚠️ Unknown DSP parameter: <code>{html.escape(mode)}</code>. Use <code>bass</code>, <code>8d</code>, <code>nightcore</code>, or <code>speed</code>."

    msg = await message.reply(f"{res}\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay=10))


@dp.message(F.text.regexp(r"^[!/.?]?(?:mydsp|dsp)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_mydsp_cmd(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    dsp = await db_service.get_user_dsp(user_id)

    if not dsp or (dsp.get('bass_boost_db', 0) == 0 and not dsp.get('spatial_8d') and not dsp.get('nightcore') and dsp.get('speed', 1.0) == 1.0):
        text = (
            f"🎛️ <b>Your Personal DSP Profile:</b> <code>CLEAN STUDIO (DEFAULT)</code>\n\n"
            f"No sound modifiers active. Your queued songs play with pure uncompressed studio audio.\n"
            f"Use <code>/setdsp bass 10</code> or <code>/8d on</code> to activate modifiers.\n\n"
            f"{POWERED_BY_FOOTER}"
        )
    else:
        text = (
            f"🎛️ <b>Your Active DSP Sound Profile:</b>\n\n"
            f"• 🔊 <b>Bass Boost:</b> <code>+{dsp.get('bass_boost_db', 0):.1f} dB</code>\n"
            f"• 🎧 <b>8D Spatial Audio:</b> <code>{'ON (360°)' if dsp.get('spatial_8d') else 'OFF'}</code>\n"
            f"• ⚡ <b>Nightcore:</b> <code>{'ON (1.25x)' if dsp.get('nightcore') else 'OFF'}</code>\n"
            f"• ⏱️ <b>Playback Speed:</b> <code>{dsp.get('speed', 1.0):.2f}x</code>\n\n"
            f"⚡ <i>These modifiers are automatically pre-rendered on every song you queue!</i>\n"
            f"Use <code>/cleardsp</code> to reset.\n\n"
            f"{POWERED_BY_FOOTER}"
        )

    msg = await message.reply(text, parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay=15))


@dp.message(F.text.regexp(r"^[!/.?]?(?:cleardsp|resetdsp)(?:@\w+)?", flags=re.IGNORECASE))
async def handle_cleardsp_cmd(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    await db_service.clear_user_dsp(user_id)
    msg = await message.reply(f"{E_CHECK} <b>Personal DSP reset to Clean Studio Audio!</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:bass)(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_bass_cmd(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].lower() in ("off", "0", "disable", "reset"):
        db = 0.0
    elif len(parts) > 1 and parts[1].replace(".", "", 1).isdigit():
        db = max(0.0, min(15.0, float(parts[1])))
    else:
        cur_dsp = await db_service.get_user_dsp(user_id) or {}
        cur_db = cur_dsp.get("bass_boost_db", 0.0)
        db = 0.0 if cur_db > 0 else 10.0

    await db_service.set_user_dsp(user_id, bass_boost_db=db)
    if db > 0:
        msg = await message.reply(f"{E_FIRE} <b>Bass Boost (+{db:.1f} dB) armed for your queued songs!</b>\n⚡ <i>Pre-rendered in background for gapless playback.</i>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    else:
        msg = await message.reply(f"{E_CHECK} <b>Bass Boost disabled.</b> Your queued songs will play flat studio audio.\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:8d|d8)(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_8d_cmd(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].lower() in ("off", "0", "disable", "reset"):
        is_on = False
    elif len(parts) > 1 and parts[1].lower() in ("on", "1", "enable"):
        is_on = True
    else:
        cur_dsp = await db_service.get_user_dsp(user_id) or {}
        is_on = not cur_dsp.get("spatial_8d", False)

    await db_service.set_user_dsp(user_id, spatial_8d=is_on)
    if is_on:
        msg = await message.reply(f"{E_HEADPHONES} <b>8D Spatial Audio armed for your queued songs!</b>\n⚡ <i>360° binaural circular panning pre-rendered.</i>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    else:
        msg = await message.reply(f"{E_CHECK} <b>8D Spatial Audio disabled.</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay=8))


@dp.message(F.text.regexp(r"^[!/.?]?(?:nightcore|nc)(?:@\w+)?(?:\s+(.*))?", flags=re.IGNORECASE))
async def handle_nightcore_cmd(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].lower() in ("off", "0", "disable", "reset"):
        is_on = False
    elif len(parts) > 1 and parts[1].lower() in ("on", "1", "enable"):
        is_on = True
    else:
        cur_dsp = await db_service.get_user_dsp(user_id) or {}
        is_on = not cur_dsp.get("nightcore", False)

    await db_service.set_user_dsp(user_id, nightcore=is_on)
    if is_on:
        msg = await message.reply(f"⚡ <b>Nightcore Mode (1.25x Tempo & Pitch) armed for your queued songs!</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    else:
        msg = await message.reply(f"{E_CHECK} <b>Nightcore Mode disabled.</b>\n\n{POWERED_BY_FOOTER}", parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay=8))
