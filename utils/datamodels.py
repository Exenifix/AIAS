import sys
from os import getenv
from random import choice
from typing import Any

import asyncpg
from ai.analyser import analyse_sample
from dotenv import load_dotenv
from exencolorlogs import Logger

from utils.constants import SPAM_VERIFICATION_THRESHOLD
from utils.db_updater import update_db
from utils.enums import BlacklistMode, FetchMode
from utils.errors import (
    AlreadyIgnored,
    AlreadyManager,
    NotIgnored,
    NotManager,
    WordAlreadyExists,
    WordNotFound,
)

load_dotenv()

DATABASE = getenv("DATABASE")
HOST = getenv("HOST")
USER = getenv("USER")
PASSWORD = getenv("PASSWORD")

if DATABASE is None:
    print(".env file not filled up properly")
    sys.exit(1)


class Database:
    log: Logger
    _pool: asyncpg.Pool
    _connection_config: dict[str, Any]

    def __init__(self, **connection_config):
        self.log = Logger("DB")
        self._connection_config = {
            "database": DATABASE,
            "host": HOST or "127.0.0.1",
            "user": USER,
        }
        if PASSWORD is not None:
            self._connection_config["password"] = PASSWORD

        self._connection_config.update(connection_config)

    async def connect(self):
        self.log.info("Creating connection pool...")
        self._pool = await asyncpg.create_pool(**self._connection_config)
        self.log.info("Connection pool created successfully!")

    async def close(self):
        self.log.info("Closing connection pool...")
        await self._pool.close()
        self.log.info("Connection pool closed successfully")

    async def execute(self, query: str, *args, fetch_mode: FetchMode = FetchMode.NONE):
        async with self._pool.acquire() as con:
            con: asyncpg.Connection
            match fetch_mode:
                case FetchMode.NONE:
                    return await con.execute(query, *args)
                case FetchMode.VAL:
                    return await con.fetchval(query, *args)
                case FetchMode.ROW:
                    return await con.fetchrow(query, *args)
                case FetchMode.ALL:
                    return await con.fetch(query, *args)

    async def setup(self, filename: str = "base_config.sql"):
        self.log.info("Executing setup statements...")
        with open(filename, "r") as f:
            async with self._pool.acquire() as con:
                con: asyncpg.Connection
                for sql in f.read().split(";"):
                    if len(sql) <= 1:
                        continue
                    await con.execute(sql)

        await update_db(self)

    def get_guild(self, id: int) -> "GuildData":
        return GuildData(self, id)

    async def register_message(self, content: str):
        content = content.lower()
        data = analyse_sample(content)
        await self.execute(
            "INSERT INTO data (content, total_chars, unique_chars, total_words, unique_words) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            content,
            *data,
        )

    async def modify_message_score(self, id: int, upvote: bool):
        if upvote:
            await self.execute(
                "UPDATE data SET upvotes = upvotes + 1 WHERE id = $1", id
            )
        else:
            await self.execute(
                "UPDATE data SET downvotes = downvotes + 1 WHERE id = $1", id
            )

    async def get_random_record(self) -> tuple[int, str]:
        records = await self.execute(
            "SELECT id, content FROM data WHERE upvotes + downvotes < $1 AND is_spam IS NULL LIMIT 50",
            SPAM_VERIFICATION_THRESHOLD,
            fetch_mode=FetchMode.ALL,
        )
        if len(records) == 0:
            return None, None
        return tuple(choice(records).values())

    async def mark_message_as_spam(self, id: int, is_spam: bool):
        await self.execute("UPDATE data SET is_spam = $1 WHERE id = $2", is_spam, id)

    async def get_unmarked_message(self):
        record = await self.execute(
            "SELECT id, content FROM data WHERE is_spam IS NULL LIMIT 1",
            fetch_mode=FetchMode.ROW,
        )
        if record is None:
            return None, None
        return tuple(record.values())


class SubData:
    _guild: "GuildData"

    def __init__(self, guild: "GuildData"):
        self._guild = guild

    async def load(self):
        prefix: str = self.__class__.__name__.replace("Data", "").lower() + "_"
        data = await self._guild._select(
            ", ".join(
                prefix + slot for slot in self.__slots__ if not slot.startswith("_")
            )
        )
        for k, v in data.items():
            setattr(self, k.replace(prefix, ""), v)


class AntiSpamData(SubData):
    _guild: "GuildData"
    enabled: bool
    ignored: list[int]

    __slots__ = ["_guild", "enabled", "ignored"]


class BlacklistData(SubData):
    _guild: "GuildData"
    enabled: bool
    ignored: list[int]
    common: list[str]
    wild: list[str]
    super: list[str]
    filter_enabled: bool

    __slots__ = ["enabled", "ignored", "common", "wild", "super", "filter_enabled"]


class GuildData:
    id: int

    def __init__(self, _db: Database, id: int):
        self.id = id
        self._db = _db

    async def _validate_existence(self):
        await self._db.execute(
            "INSERT INTO guilds (id) VALUES ($1) ON CONFLICT DO NOTHING", self.id
        )

    async def _select(self, args: str, fetch_mode: FetchMode = FetchMode.ROW):
        await self._validate_existence()
        return await self._db.execute(
            f"SELECT {args} FROM guilds WHERE id = $1", self.id, fetch_mode=fetch_mode
        )

    async def _update(self, **kwargs):
        text = ""
        for i, k in enumerate(kwargs, 2):
            text += f"{k} = ${i}, "

        text = text[:-2]
        await self._validate_existence()
        await self._db.execute(
            f"UPDATE guilds SET {text} WHERE id = $1", self.id, *kwargs.values()
        )

    async def get_prefixes(self) -> list[str]:
        return await self._select("prefixes", FetchMode.VAL)

    async def get_antispam_data(self) -> AntiSpamData:
        data = AntiSpamData(self)
        await data.load()

        return data

    async def get_blacklist_data(self) -> BlacklistData:
        data = BlacklistData(self)
        await data.load()

        return data

    async def get_automod_managers(self) -> list[int]:
        return await self._select("automod_managers", FetchMode.VAL)

    async def add_automod_manager(self, value: int):
        managers = await self.get_automod_managers()
        if value in managers:
            raise AlreadyManager(value)

        managers.append(value)
        await self._update(automod_managers=managers)

    async def remove_automod_manager(self, value: int):
        try:
            managers = await self.get_automod_managers()
            managers.remove(value)
        except ValueError:
            raise NotManager(value)

        await self._update(automod_managers=managers)

    async def set_antispam_enabled(self, value: bool):
        await self._update(antispam_enabled=value)

    async def add_antispam_ignored(self, value: int):
        ignored = await self._select("antispam_ignored", FetchMode.VAL)
        if value in ignored:
            raise AlreadyIgnored(value)

        ignored.append(value)
        await self._update(antispam_ignored=ignored)

    async def remove_antispam_ignored(self, value: int):
        try:
            ignored = await self._select("antispam_ignored", FetchMode.VAL)
            ignored.remove(value)
            await self._update(antispam_ignored=ignored)
        except ValueError:
            raise NotIgnored(value)

    async def set_blacklist_enabled(self, value: bool):
        await self._update(blacklist_enabled=value)

    async def set_blacklist_filter_enabled(self, value: bool):
        await self._update(blacklist_filter_enabled=value)

    async def add_blacklist_ignored(self, value: int):
        ignored = await self._select("blacklist_ignored", FetchMode.VAL)
        if value in ignored:
            raise AlreadyIgnored(value)

        ignored.append(value)
        await self._update(blacklist_ignored=ignored)

    async def remove_blacklist_ignored(self, value: int):
        try:
            ignored = await self._select("blacklist_ignored", FetchMode.VAL)
            ignored.remove(value)
            await self._update(blacklist_ignored=ignored)
        except ValueError:
            raise NotIgnored(value)

    async def add_blacklist_word(self, value: str, mode: BlacklistMode):
        current: list[str] = await self._select(
            "blacklist_" + mode.value, FetchMode.VAL
        )

        if value in current:
            raise WordAlreadyExists(value, mode.value)

        current.append(value)
        await self._update(**{"blacklist_" + mode.value: current})

    async def remove_blacklist_word(self, value: str, mode: BlacklistMode):
        current: list[str] = await self._select(
            "blacklist_" + mode.value, FetchMode.VAL
        )
        try:
            current.remove(value)
            await self._update(**{"blacklist_" + mode.value: current})
        except ValueError:
            raise WordNotFound(value, mode.value)
