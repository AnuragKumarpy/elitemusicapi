"""
Centralized asynchronous database service with cross-bot user tracking,
supergroup indexing, broadcast target retrieval, and live ecosystem breakdown.
"""
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.db_models import Base, BotUser, BotChat, BroadcastRecord, UserDSPSettings

DB_URL = "sqlite+aiosqlite:////home/ubuntu/elitemusicapi/elitemusic.db"


def get_utc_now():
    return datetime.now(timezone.utc)


class DatabaseService:
    def __init__(self):
        self.engine = create_async_engine(DB_URL, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def track_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_bot: bool = False,
        source_bot: str = "EliteMusicApiBot",
        bot_token_id: Optional[str] = None
    ):
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    query = select(BotUser).where(BotUser.id == user_id)
                    result = await session.execute(query)
                    user = result.scalars().first()

                    if user:
                        user.username = username
                        user.first_name = first_name
                        user.last_name = last_name
                        user.source_bot = source_bot
                        if bot_token_id:
                            user.bot_token_id = bot_token_id
                        user.last_seen = get_utc_now()
                    else:
                        new_user = BotUser(
                            id=user_id,
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            is_bot=is_bot,
                            source_bot=source_bot,
                            bot_token_id=bot_token_id,
                            first_seen=get_utc_now(),
                            last_seen=get_utc_now()
                        )
                        session.add(new_user)
        except Exception as e:
            print(f"[DB] track_user warning: {e}")

    async def track_chat(
        self,
        chat_id: int,
        title: Optional[str] = None,
        chat_type: str = "supergroup",
        username: Optional[str] = None,
        added_by_user_id: Optional[int] = None,
        source_bot: str = "EliteMusicApiBot",
        bot_token_id: Optional[str] = None
    ):
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    query = select(BotChat).where(BotChat.id == chat_id)
                    result = await session.execute(query)
                    chat = result.scalars().first()

                    if chat:
                        chat.title = title
                        chat.username = username
                        chat.source_bot = source_bot
                        if bot_token_id:
                            chat.bot_token_id = bot_token_id
                        chat.last_active_at = get_utc_now()
                        chat.is_active = True
                    else:
                        new_chat = BotChat(
                            id=chat_id,
                            title=title,
                            chat_type=chat_type,
                            username=username,
                            added_by_user_id=added_by_user_id,
                            source_bot=source_bot,
                            bot_token_id=bot_token_id,
                            is_active=True,
                            created_at=get_utc_now(),
                            last_active_at=get_utc_now()
                        )
                        session.add(new_chat)
        except Exception as e:
            print(f"[DB] track_chat warning: {e}")

    async def get_all_user_ids(self, source_bot: str = "global") -> List[int]:
        async with self.session_factory() as session:
            if source_bot == "global":
                query = select(distinct(BotUser.id))
            else:
                query = select(distinct(BotUser.id)).where(BotUser.source_bot == source_bot)
            result = await session.execute(query)
            return [row[0] for row in result.fetchall()]

    async def get_all_chat_ids(self, source_bot: str = "global") -> List[int]:
        async with self.session_factory() as session:
            if source_bot == "global":
                query = select(distinct(BotChat.id)).where(BotChat.is_active == True)
            else:
                query = select(distinct(BotChat.id)).where(
                    BotChat.source_bot == source_bot,
                    BotChat.is_active == True
                )
            result = await session.execute(query)
            return [row[0] for row in result.fetchall()]

    async def get_network_stats(self) -> Dict[str, Any]:
        async with self.session_factory() as session:
            u_count = await session.scalar(select(func.count(distinct(BotUser.id))))
            c_count = await session.scalar(select(func.count(distinct(BotChat.id))))
            return {
                "total_users": u_count or 0,
                "active_chats": c_count or 0
            }

    async def get_ecosystem_telemetry(self) -> Dict[str, Any]:
        """Aggregate metrics per bot instance and total network metrics."""
        async with self.session_factory() as session:
            tot_users = await session.scalar(select(func.count(distinct(BotUser.id)))) or 0
            tot_chats = await session.scalar(select(func.count(distinct(BotChat.id)))) or 0

            u_query = select(BotUser.source_bot, func.count(distinct(BotUser.id))).group_by(BotUser.source_bot)
            u_rows = (await session.execute(u_query)).fetchall()
            users_by_bot = {row[0]: row[1] for row in u_rows}

            c_query = select(BotChat.source_bot, func.count(distinct(BotChat.id))).where(BotChat.is_active == True).group_by(BotChat.source_bot)
            c_rows = (await session.execute(c_query)).fetchall()
            chats_by_bot = {row[0]: row[1] for row in c_rows}

            all_bot_names = set(users_by_bot.keys()).union(set(chats_by_bot.keys()))
            if "EliteMusicApiBot" not in all_bot_names:
                all_bot_names.add("EliteMusicApiBot")

            breakdown = []
            for b_name in sorted(list(all_bot_names)):
                clean_name = b_name.replace("@", "")
                is_main = (clean_name == "EliteMusicApiBot")
                breakdown.append({
                    "username": clean_name,
                    "is_official": is_main,
                    "users_count": users_by_bot.get(b_name, 0),
                    "chats_count": chats_by_bot.get(b_name, 0),
                })

            breakdown.sort(key=lambda x: (not x["is_official"], -(x["users_count"] + x["chats_count"])))

            return {
                "total_users": tot_users,
                "total_chats": tot_chats,
                "bot_breakdown": breakdown
            }



    async def get_user_dsp(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve persistent DSP audio settings configured by this user."""
        try:
            async with self.session_factory() as session:
                query = select(UserDSPSettings).where(UserDSPSettings.user_id == user_id)
                result = await session.execute(query)
                row = result.scalars().first()
                if row:
                    return {
                        "bass_boost_db": float(row.bass_boost_db),
                        "spatial_8d": bool(row.spatial_8d),
                        "nightcore": bool(row.nightcore),
                        "speed": float(row.speed) / 100.0 if row.speed else 1.0,
                        "volume": int(row.volume or 100)
                    }
        except Exception as e:
            print(f"[DB] get_user_dsp error: {e}")
        return None

    async def set_user_dsp(
        self,
        user_id: int,
        bass_boost_db: Optional[float] = None,
        spatial_8d: Optional[bool] = None,
        nightcore: Optional[bool] = None,
        speed: Optional[float] = None,
        volume: Optional[int] = None
    ):
        """Store or update per-user persistent DSP equalizer preset."""
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    query = select(UserDSPSettings).where(UserDSPSettings.user_id == user_id)
                    result = await session.execute(query)
                    row = result.scalars().first()

                    if row:
                        if bass_boost_db is not None:
                            row.bass_boost_db = int(bass_boost_db)
                        if spatial_8d is not None:
                            row.spatial_8d = spatial_8d
                        if nightcore is not None:
                            row.nightcore = nightcore
                        if speed is not None:
                            row.speed = int(speed * 100)
                        if volume is not None:
                            row.volume = volume
                        row.updated_at = get_utc_now()
                    else:
                        new_row = UserDSPSettings(
                            user_id=user_id,
                            bass_boost_db=int(bass_boost_db) if bass_boost_db is not None else 0,
                            spatial_8d=spatial_8d if spatial_8d is not None else False,
                            nightcore=nightcore if nightcore is not None else False,
                            speed=int(speed * 100) if speed is not None else 100,
                            volume=volume if volume is not None else 100,
                            updated_at=get_utc_now()
                        )
                        session.add(new_row)
        except Exception as e:
            print(f"[DB] set_user_dsp error: {e}")

    async def clear_user_dsp(self, user_id: int):
        """Reset user DSP back to clean studio default."""
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    query = select(UserDSPSettings).where(UserDSPSettings.user_id == user_id)
                    result = await session.execute(query)
                    row = result.scalars().first()
                    if row:
                        await session.delete(row)
        except Exception as e:
            print(f"[DB] clear_user_dsp error: {e}")


db_service = DatabaseService()
