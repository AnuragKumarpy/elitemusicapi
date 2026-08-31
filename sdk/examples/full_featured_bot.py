"""
Example 2: Full-Featured Interactive Telegram Music Bot (aiogram 3.x)
Demonstrates complete integration with Elite Music API including:
- /play (Audio streaming & queueing)
- /vplay (720p Video streaming)
- /pause, /resume, /skip, /stop
- /bass (Real-time Bass Boost DSP)
- /8d (Real-time 8D Spatial Audio DSP)
- Interactive Inline Keyboard + Telegram Mini App (TMA) Collaborative DJ Console button.
"""
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from elitemusic import EliteMusicClient, DSP

# Telegram Bot Token & Elite Music API Credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
ELITE_API_KEY = os.getenv("ELITE_API_KEY", "master_live_sec_999a8b7c6d5e4f3a2b1c0d9e8f7a6b5c")
ELITE_API_URL = os.getenv("ELITE_API_URL", "http://localhost:8000/v1")
TMA_APP_URL = os.getenv("TMA_APP_URL", "https://tma.yourdomain.com")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
music_client = EliteMusicClient(api_key=ELITE_API_KEY, base_url=ELITE_API_URL)


def get_playback_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Generate interactive player controls with TMA DJ console button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸️ Pause", callback_data=f"pause:{chat_id}"),
            InlineKeyboardButton(text="▶️ Resume", callback_data=f"resume:{chat_id}"),
            InlineKeyboardButton(text="⏭️ Skip", callback_data=f"skip:{chat_id}"),
            InlineKeyboardButton(text="⏹️ Stop", callback_data=f"stop:{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="🔊 Bass Boost", callback_data=f"bass:{chat_id}"),
            InlineKeyboardButton(text="🎧 8D Audio", callback_data=f"8d:{chat_id}"),
        ],
        [
            InlineKeyboardButton(
                text="🎛️ Open TMA Live DJ Console",
                web_app=WebAppInfo(url=f"{TMA_APP_URL}?room_id={chat_id}")
            )
        ]
    ])


@dp.message(Command("play"))
async def handle_play(message: types.Message):
    if not message.chat or message.chat.type not in ("group", "supergroup"):
        return await message.reply("⚠️ Please use this command inside a Telegram Group Voice Chat.")

    query = message.text.replace("/play", "", 1).strip()
    if not query:
        return await message.reply("ℹ️ <b>Usage:</b> <code>/play &lt;song name or URL&gt;</code>", parse_mode="HTML")

    status_msg = await message.reply("🔍 Resolving track & connecting userbot to Voice Chat...")

    try:
        result = await music_client.play(
            chat_id=message.chat.id,
            query=query,
            requested_by_id=message.from_user.id if message.from_user else 0,
            requested_by_name=message.from_user.full_name if message.from_user else "User"
        )

        badge = "▶️ <b>Now Streaming:</b>" if result.status == "STREAMING" else "⏳ <b>Added to Queue:</b>"
        text = (
            f"{badge}\n"
            f"🎵 <b>{result.track.title}</b>\n"
            f"👤 <b>Artist:</b> {result.track.artist or 'Unknown'}\n"
            f"⏱️ <b>Duration:</b> {result.track.duration_seconds}s\n"
            f"⚙️ <b>Worker Node:</b> <code>{result.worker_node}</code>"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=get_playback_keyboard(message.chat.id))
    except Exception as err:
        await status_msg.edit_text(f"❌ <b>Error:</b> {str(err)}", parse_mode="HTML")


@dp.message(Command("vplay"))
async def handle_vplay(message: types.Message):
    """Stream 720p Video into Voice Chat."""
    query = message.text.replace("/vplay", "", 1).strip()
    if not query:
        return await message.reply("ℹ️ <b>Usage:</b> <code>/vplay &lt;video name or URL&gt;</code>", parse_mode="HTML")

    status_msg = await message.reply("🎬 Transcoding 720p video stream in RAM...")
    try:
        result = await music_client.play_video(chat_id=message.chat.id, query=query, resolution="720p")
        await status_msg.edit_text(
            f"🎬 <b>Streaming Video (720p @ 30fps):</b>\n🎵 <b>{result.track.title}</b>",
            parse_mode="HTML",
            reply_markup=get_playback_keyboard(message.chat.id)
        )
    except Exception as err:
        await status_msg.edit_text(f"❌ <b>Error:</b> {str(err)}", parse_mode="HTML")


@dp.callback_query()
async def handle_callback_buttons(query: types.CallbackQuery):
    data = query.data or ""
    action, chat_id_str = data.split(":")
    chat_id = int(chat_id_str)

    try:
        if action == "pause":
            await music_client.pause(chat_id)
            await query.answer("⏸️ Paused")
        elif action == "resume":
            await music_client.resume(chat_id)
            await query.answer("▶️ Resumed")
        elif action == "skip":
            res = await music_client.skip(chat_id)
            await query.answer("⏭️ Skipped track")
        elif action == "stop":
            await music_client.stop(chat_id)
            await query.answer("⏹️ Stream stopped and userbot released")
            await query.message.edit_text("⏹️ Playback stopped. Voice Chat session ended.")
        elif action == "bass":
            await music_client.set_dsp(chat_id, bass_boost_db=6.0)
            await query.answer("🔊 Bass Boost (+6dB) applied!")
        elif action == "8d":
            await music_client.set_dsp(chat_id, spatial_8d=True)
            await query.answer("🎧 8D Spatial Audio activated!")
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


async def main():
    print("🤖 Elite Music Reference Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
