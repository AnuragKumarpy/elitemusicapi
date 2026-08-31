"""
Final Enterprise Knowledge Hub, Manual, Command Reference, and FAQ System for Elite Music API.
"""
import html
from typing import Tuple
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

POWERED_BY_FOOTER = '⚡ <i>Powered by</i> <a href="https://t.me/EliteBotsTelegram"><b>Elite Bots</b></a>'


class HelpManualService:
    @staticmethod
    def get_main_menu(bot_name: str = "Elite Music Bot") -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            f"👑 <b>{html.escape(bot_name)} — Knowledge Hub & User Guide</b> 💎\n\n"
            f"Welcome to the official documentation deck! Explore high-speed Voice Chat streaming features, command syntax, Telegram audio replies, and the custom clone engine.\n\n"
            f"👇 <b>Select a guide category below:</b>\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📖 Getting Started", callback_data="menu:guide:start", style="primary", icon_custom_emoji_id="5217822164362739968"),
                    InlineKeyboardButton(text="🎛️ Audio & DSP", callback_data="menu:guide:dsp", style="primary", icon_custom_emoji_id="5033184522489825051"),
                ],
                [
                    InlineKeyboardButton(text="🤖 Clone Engine", callback_data="menu:guide:clone", style="primary", icon_custom_emoji_id="5361741454685256344"),
                    InlineKeyboardButton(text="📜 All Commands", callback_data="menu:guide:commands", style="primary", icon_custom_emoji_id="5373251851074415873"),
                ],
                [
                    InlineKeyboardButton(text="❓ FAQs & Troubleshooting", callback_data="menu:guide:faq", style="primary", icon_custom_emoji_id="5427168083074628963")
                ],
                [
                    InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="menu:start", style="primary", icon_custom_emoji_id="5434144690511290129")
                ]
            ]
        )
        return text, kb

    @staticmethod
    def get_getting_started() -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            f"📖 <b>Getting Started — Quick Setup Manual</b>\n\n"
            f"Follow these simple steps to stream lossless music in your Telegram Supergroup:\n\n"
            f"1. <b>Add Bot to Group:</b> Add the bot and grant <b>Admin permissions</b> (<i>Invite Users via Link</i>, <i>Manage Voice Chats</i>, <i>Delete Messages</i>).\n"
            f"2. <b>Start Voice Chat:</b> Open group profile, tap ⋮ menu, and select <b>Start Video/Voice Chat</b>.\n"
            f"3. <b>Play Any Track:</b>\n"
            f"   • <code>/play &lt;song name or URL&gt;</code> — Searches and plays instantly\n"
            f"   • <b>Reply with <code>/play</code></b> to any uploaded audio file, voice message, or document in the chat!\n\n"
            f"⚡ <i>The assistant userbot will auto-join your group and immediately stream 48kHz audio!</i>\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🎛️ Audio & DSP", callback_data="menu:guide:dsp", style="primary", icon_custom_emoji_id="5033184522489825051"),
                    InlineKeyboardButton(text="📜 Commands", callback_data="menu:guide:commands", style="primary", icon_custom_emoji_id="5373251851074415873"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Help Menu", callback_data="menu:help", style="primary", icon_custom_emoji_id="5434144690511290129")
                ]
            ]
        )
        return text, kb

    @staticmethod
    def get_dsp_guide() -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            f"🎛️ <b>High-Definition Audio & Live DSP Modifiers</b>\n\n"
            f"Our engine streams true <b>320kbps / 48kHz stereo sound</b> with real-time FFmpeg biquad DSP processing:\n\n"
            f"• 🔥 <b>Bass Boost (<code>/bass [on|off|dB]</code>):</b>\n"
            f"  Amplifies sub-bass frequencies (50Hz - 120Hz) up to +12dB with zero distortion.\n\n"
            f"• 🎧 <b>8D Spatial Audio (<code>/8d [on|off]</code>):</b>\n"
            f"  Simulates an immersive 360-degree acoustic rotating soundfield best experienced on headphones.\n\n"
            f"• ⚡ <b>Tempo & Speed (<code>/speed [1.0|1.2|1.5]</code>):</b>\n"
            f"  Pitch-compensated audio time-stretching for high-tempo playback.\n\n"
            f"💡 <i>All DSP settings can be toggled via the <b>🎛️ Options</b> button on the player card.</i>\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🤖 Clone Engine", callback_data="menu:guide:clone", style="primary", icon_custom_emoji_id="5361741454685256344"),
                    InlineKeyboardButton(text="📜 Commands", callback_data="menu:guide:commands", style="primary", icon_custom_emoji_id="5373251851074415873"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Help Menu", callback_data="menu:help", style="primary", icon_custom_emoji_id="5434144690511290129")
                ]
            ]
        )
        return text, kb

    @staticmethod
    def get_clone_guide() -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            f"🤖 <b>Make Your Own Music Bot (Clone Engine)</b>\n\n"
            f"Create your own customized Telegram Music Bot running on our enterprise streaming infrastructure:\n\n"
            f"1. <b>Create Bot on @BotFather:</b>\n"
            f"   • Open @BotFather on Telegram and send <code>/newbot</code>.\n"
            f"   • Choose a name and username ending in <code>bot</code>.\n"
            f"2. <b>Obtain Token:</b> Copy the HTTP API token provided by BotFather.\n"
            f"3. <b>Connect to Engine:</b>\n"
            f"   • Send <code>/clone</code> to this bot or <b>forward the BotFather message</b> directly.\n\n"
            f"🎉 <i>Your personal music bot is immediately live, captures your userbase into the database, and has its own private broadcast system!</i>\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🤖 Clone Now", callback_data="menu:clone_prompt", style="success", icon_custom_emoji_id="5361741454685256344"),
                    InlineKeyboardButton(text="📜 Commands", callback_data="menu:guide:commands", style="primary", icon_custom_emoji_id="5373251851074415873"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Help Menu", callback_data="menu:help", style="primary", icon_custom_emoji_id="5434144690511290129")
                ]
            ]
        )
        return text, kb

    @staticmethod
    def get_commands_guide() -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            f"📜 <b>Complete Command Reference Guide</b>\n\n"
            f"<b>🎵 Playback & Media Controls:</b>\n"
            f"• <code>/play &lt;query/url&gt;</code> — Play audio track in Voice Chat\n"
            f"• <b>Reply with <code>/play</code></b> — Play replied audio/voice/document file\n"
            f"• <code>/pause</code> — Pause current playback\n"
            f"• <code>/resume</code> — Resume paused track\n"
            f"• <code>/skip</code> — Skip to the next queued song\n"
            f"• <code>/stop</code> — End playback & leave Voice Chat\n"
            f"• <code>/queue</code> — View active song queue\n\n"
            f"<b>🎛️ Live Audio DSP Modifiers:</b>\n"
            f"• <code>/bass [on|off|dB]</code> — Toggle bass boost\n"
            f"• <code>/8d [on|off]</code> — Toggle 8D spatial audio\n"
            f"• <code>/speed [1.0|1.2|1.5]</code> — Change playback speed\n\n"
            f"<b>👑 Bot Management & Telemetry:</b>\n"
            f"• <code>/clone</code> — Create your own music bot\n"
            f"• <code>/help</code> | <code>/manual</code> | <code>/faq</code> — Knowledge manual\n"
            f"• <code>/stats</code> — View system load & fleet telemetry\n"
            f"• <code>/broadcast</code> / <code>/gcast</code> — Mass announcement engine\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="❓ FAQs", callback_data="menu:guide:faq", style="primary", icon_custom_emoji_id="5427168083074628963"),
                    InlineKeyboardButton(text="📖 Setup", callback_data="menu:guide:start", style="primary", icon_custom_emoji_id="5217822164362739968"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Help Menu", callback_data="menu:help", style="primary", icon_custom_emoji_id="5434144690511290129")
                ]
            ]
        )
        return text, kb

    @staticmethod
    def get_faq_guide() -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            f"❓ <b>Frequently Asked Questions (FAQs)</b>\n\n"
            f"<b>Q: Why does the bot say 'Voice Chat is not active'?</b>\n"
            f"A: Telegram requires group Voice Chats to be opened before bots can stream. Open the group header, tap ⋮, and choose 'Start Voice Chat'.\n\n"
            f"<b>Q: Do I need to manually invite the assistant userbot?</b>\n"
            f"A: No! The bot automatically creates a secure invite link, auto-approves join requests if approval is required, and streams unmuted.\n\n"
            f"<b>Q: Can I stream audio files uploaded directly in Telegram?</b>\n"
            f"A: Yes! Simply reply to any audio file, MP3, voice message, or document with <code>/play</code>.\n\n"
            f"<b>Q: How many bots can I clone?</b>\n"
            f"A: Unlimited! Every cloned bot connects to our 7-assistant hot-standby pool and has its own private broadcast system.\n\n"
            f"{POWERED_BY_FOOTER}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📜 All Commands", callback_data="menu:guide:commands", style="primary", icon_custom_emoji_id="5373251851074415873"),
                    InlineKeyboardButton(text="🔙 Help Menu", callback_data="menu:help", style="primary", icon_custom_emoji_id="5434144690511290129")
                ]
            ]
        )
        return text, kb


help_manual = HelpManualService()
