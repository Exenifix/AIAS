import sys
from collections import namedtuple
from datetime import datetime
from os import getenv
from typing import Any, Optional

import asyncpg
import disnake
from dotenv import load_dotenv
from exencolorlogs import Logger

from ai.analyser import analyse_sample
from utils import autocomplete, errors
from utils.constants import MAX_AUTOSLOWMODE_CHANNELS_AMOUNT
from utils.db_updater import update_db
from utils.dis_logging import GuildLogger
from utils.enums import AntiraidPunishment, BlacklistMode, FetchMode, Stat
from utils.errors import (
    AutoslowmodeChannelAlreadyExists,
    AutoslowmodeChannelsLimitReached,
)
from utils.filters.blacklist import preformat

load_dotenv()

DATABASE = getenv("DATABASE")
HOST = getenv("HOST")
USER = getenv("USER")
PASSWORD = getenv("PASSWORD")

if DATABASE is None:
    print(".env file not filled up properly")
    sys.exit(1)

warnings_data = namedtuple("warnings_data", ["timeout_duration", "warnings_threshold"])


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
        self.log.ok("Connection pool created successfully!")

    async def close(self):
        self.log.info("Closing connection pool...")
        await self._pool.close()
        self.log.ok("Connection pool closed successfully")

    async def execute(
        self, query: str, *args, fetch_mode: FetchMode = FetchMode.NONE
    ) -> None | list[dict] | dict | Any:
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
                for sql in f.read().split(";\n"):
                    if len(sql) <= 1:
                        continue
                    await con.execute(sql)

        await update_db(self)

        # inserting Stat enums
        existing_stats: list[int] = await self.execute(
            "SELECT id FROM stats", fetch_mode=FetchMode.ROW
        )
        for enum in Stat:
            if enum.value not in existing_stats:
                await self.execute(
                    "INSERT INTO stats (id) VALUES ($1) ON CONFLICT DO NOTHING",
                    enum.value,
                )

    def get_guild(self, id: int) -> "GuildData":
        return GuildData(self, id)

    async def register_message(self, content: str):
        data = analyse_sample(content)
        await self.execute(
            "INSERT INTO data (total_chars, unique_chars, total_words, unique_words, content) \
VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
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

    async def mark_message_as_spam(self, content: str, is_spam: bool):
        await self.update_sample(content, is_spam)

    async def get_unmarked_message(self) -> str | None:
        record = await self.execute(
            "SELECT MIN(id) AS id, content FROM data WHERE is_spam IS NULL GROUP BY id LIMIT 1",
            fetch_mode=FetchMode.ROW,
        )
        if record is None:
            return None
        return record["content"]

    async def update_sample(self, content: str, is_spam: bool):
        await self.execute(
            "UPDATE data SET is_spam = $1 WHERE content = $2", is_spam, content
        )
        analysis_data = analyse_sample(content)
        exists: bool = await self.execute(
            "SELECT EXISTS(SELECT 1 FROM data WHERE total_chars = $1 AND unique_chars = $2 AND total_words = $3 AND unique_words = $4)",
            *analysis_data[:4],
            fetch_mode=FetchMode.VAL,
        )
        if not exists:
            await self.register_message(content)
            return

        await self.execute(
            "UPDATE data SET is_spam = $1 WHERE total_chars = $2 AND unique_chars = $3 AND total_words = $4 AND unique_words = $5",
            is_spam,
            *analysis_data[:4],
        )

    async def register_stat_increase(self, stat: Stat, amount: int = 1):
        await self.execute(
            "UPDATE stats SET applied_totally = applied_totally + $2, applied_daily = applied_daily + $2 WHERE id = $1",
            stat.value,
            amount,
        )

    async def get_stats(self) -> str:
        data = await self.execute(
            "SELECT * FROM stats ORDER BY id", fetch_mode=FetchMode.ALL
        )
        text = ""
        for record in data:
            text += f"\n**{Stat(record['id']).name.replace('_', ' ').title()}:** `{record['applied_totally']}` total, `{record['applied_daily']}` daily"

        return text

    async def reset_daily_stats(self):
        await self.execute("UPDATE stats SET applied_daily = 0")
        await self.update_daily_reset()

    async def get_daily_reset(self) -> datetime:
        return await self.execute(
            "SELECT value FROM resets WHERE id = 0", fetch_mode=FetchMode.VAL
        )

    async def update_daily_reset(self):
        await self.execute("UPDATE resets SET value = CURRENT_TIMESTAMP WHERE id = 0")

    async def add_autoslowmode_channel(self, channel: disnake.TextChannel):
        amount: int = await self.execute(
            "SELECT COUNT(*) FROM autoslowmode WHERE guild_id = $1",
            channel.guild.id,
            fetch_mode=FetchMode.VAL,
        )
        if amount >= MAX_AUTOSLOWMODE_CHANNELS_AMOUNT:
            raise AutoslowmodeChannelsLimitReached()

        try:
            await self.execute(
                "INSERT INTO autoslowmode (id, guild_id) VALUES ($1, $2)",
                channel.id,
                channel.guild.id,
            )
        except asyncpg.UniqueViolationError:
            raise AutoslowmodeChannelAlreadyExists(channel.id)

    async def remove_autoslowmode_channel(self, channel_id: int):
        await self.execute("DELETE FROM autoslowmode WHERE id = $1", channel_id)

    async def is_channel_autoslowmode(self, channel: disnake.TextChannel):
        return bool(
            await self.execute(
                "SELECT EXISTS(SELECT 1 FROM autoslowmode WHERE id = $1)",
                channel.id,
                fetch_mode=FetchMode.VAL,
            )
        )

    async def get_autoslowmode_channels(self) -> list[int]:
        return [
            r["id"]
            for r in await self.execute(
                "SELECT id FROM autoslowmode",
                fetch_mode=FetchMode.ALL,
            )
        ]

    async def get_autoslowmode_channels_for_guild(self, guild_id: int) -> list[int]:
        return [
            r["id"]
            for r in await self.execute(
                "SELECT id FROM autoslowmode WHERE guild_id = $1",
                guild_id,
                fetch_mode=FetchMode.ALL,
            )
        ]


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


class WhitelistData(SubData):
    _guild: "GuildData"
    enabled: bool
    characters: str
    ignored: list[int]

    __slots__ = ["enabled", "characters", "ignored"]


class AntiraidData(SubData):
    _guild: "GuildData"
    enabled: bool
    join_interval: int
    members_limit: int
    punishment: AntiraidPunishment

    __slots__ = ["enabled", "join_interval", "members_limit", "punishment"]

    async def load(self):
        await super().load()
        self.punishment = AntiraidPunishment(self.punishment)


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
        args_amount = len(args.split(","))
        if fetch_mode == FetchMode.VAL and args_amount > 1:
            self._db.log.warning(
                "Selection of multiple fields with FetchMode.VAL: %s", args
            )
        elif fetch_mode != FetchMode.VAL and args_amount <= 1:
            self._db.log.warning(
                "Selection of single field with %s: %s:", fetch_mode, args
            )

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
            raise errors.AlreadyManager(value)

        managers.append(value)
        await self._update(automod_managers=managers)

    async def remove_automod_manager(self, value: int):
        try:
            managers = await self.get_automod_managers()
            managers.remove(value)
        except ValueError:
            raise errors.NotManager(value)

        await self._update(automod_managers=managers)

    async def set_antispam_enabled(self, value: bool):
        await self._update(antispam_enabled=value)

    async def add_antispam_ignored(self, value: int):
        ignored = await self._select("antispam_ignored", FetchMode.VAL)
        if value in ignored:
            raise errors.AlreadyIgnored(value)

        ignored.append(value)
        await self._update(antispam_ignored=ignored)

    async def remove_antispam_ignored(self, value: int):
        try:
            ignored: list[int] = await self._select("antispam_ignored", FetchMode.VAL)
            ignored.remove(value)
            await self._update(antispam_ignored=ignored)
        except ValueError:
            raise errors.NotIgnored(value)

    async def set_blacklist_enabled(self, value: bool):
        await self._update(blacklist_enabled=value)

    async def set_blacklist_filter_enabled(self, value: bool):
        await self._update(blacklist_filter_enabled=value)

    async def add_blacklist_ignored(self, value: int):
        ignored = await self._select("blacklist_ignored", FetchMode.VAL)
        if value in ignored:
            raise errors.AlreadyIgnored(value)

        ignored.append(value)
        await self._update(blacklist_ignored=ignored)

    async def remove_blacklist_ignored(self, value: int):
        try:
            ignored = await self._select("blacklist_ignored", FetchMode.VAL)
            ignored.remove(value)
            await self._update(blacklist_ignored=ignored)
        except ValueError:
            raise errors.NotIgnored(value)

    async def add_blacklist_word(self, value: str, mode: BlacklistMode):
        current: list[str] = await self._select(
            "blacklist_" + mode.value, FetchMode.VAL
        )

        if value in current:
            raise errors.WordAlreadyExists(value, mode.value)

        current.append(value)
        try:
            await self._update(**{"blacklist_" + mode.value: current})
        except asyncpg.CheckViolationError:
            raise errors.WordsThresholdExceeded()

    async def addmany_blacklist_words(self, words: list[str], mode: BlacklistMode):
        current: set[str] = set(
            await self._select("blacklist_" + mode.value, FetchMode.VAL)
        )
        words = set(map(lambda s: preformat(s, mode), words))

        current |= words
        try:
            await self._update(**{"blacklist_" + mode.value: current})
        except asyncpg.CheckViolationError:
            raise errors.WordsThresholdExceeded()

    async def remove_blacklist_word(self, value: str, mode: BlacklistMode):
        current: list[str] = await self._select(
            "blacklist_" + mode.value, FetchMode.VAL
        )
        try:
            current.remove(value)
            await self._update(**{"blacklist_" + mode.value: current})
        except ValueError:
            raise errors.WordNotFound(value, mode.value)

    async def clear_blacklist(self, mode: Optional[BlacklistMode] = None):
        if mode is None:
            await self._update(
                blacklist_common=[], blacklist_wild=[], blacklist_super=[]
            )
        else:
            await self._update(**{"blacklist_" + mode.value: []})

    async def get_whitelist_data(self) -> WhitelistData:
        data = WhitelistData(self)
        await data.load()

        return data

    async def set_whitelist_enabled(self, value: bool):
        await self._update(whitelist_enabled=value)

    async def set_whitelist_characters(self, value: str):
        await self._update(whitelist_characters=value)

    async def add_whitelist_ignored(self, value: int):
        ignored = await self._select("whitelist_ignored", FetchMode.VAL)
        if value in ignored:
            raise errors.AlreadyIgnored(value)

        ignored.append(value)
        await self._update(whitelist_ignored=ignored)

    async def remove_whitelist_ignored(self, value: int):
        try:
            ignored = await self._select("whitelist_ignored", FetchMode.VAL)
            ignored.remove(value)
            await self._update(whitelist_ignored=ignored)
        except ValueError:
            raise errors.NotIgnored(value)

    async def get_nickfilter_data(self) -> tuple[bool, list[int]]:
        """Returns
        ----------
        `enabled, ignored = await guild.get_nickfilter_data()`"""
        return tuple(
            (await self._select("nickfilter_enabled, nickfilter_ignored")).values()
        )

    async def set_nickfilter_enabled(self, value: bool):
        await self._update(nickfilter_enabled=value)

    async def add_nickfilter_ignored(self, value: int):
        ignored = await self._select("nickfilter_ignored", FetchMode.VAL)
        if value in ignored:
            raise errors.AlreadyIgnored(value)

        ignored.append(value)
        await self._update(nickfilter_ignored=ignored)

    async def remove_nickfilter_ignored(self, value: int):
        try:
            ignored = await self._select("nickfilter_ignored", FetchMode.VAL)
            ignored.remove(value)
            await self._update(nickfilter_ignored=ignored)
        except ValueError:
            raise errors.NotIgnored(value)

    async def add_rule(self, key: str, value: str):
        try:
            await self._db.execute(
                "INSERT INTO rules (id, rule_key, rule_text) VALUES ($1, $2, $3)",
                self.id,
                key,
                value,
            )
            autocomplete.invalidate_rules(self.id)
        except asyncpg.UniqueViolationError:
            raise errors.RuleAlreadyExists(key)

    async def remove_rule(self, key: str):
        await self._db.execute(
            "DELETE FROM rules WHERE id = $1 AND rule_key = $2", self.id, key
        )
        autocomplete.invalidate_rules(self.id)

    async def get_rule(self, key: str) -> str:
        val = await self._db.execute(
            "SELECT rule_text FROM rules WHERE id = $1 AND rule_key = $2",
            self.id,
            key,
            fetch_mode=FetchMode.VAL,
        )
        if val is None:
            raise errors.RuleNotFound(key)

        return val

    async def get_all_rules(self) -> Optional[dict[str, str]]:
        rows = await self._db.execute(
            "SELECT rule_key, rule_text FROM rules WHERE id = $1",
            self.id,
            fetch_mode=FetchMode.ALL,
        )
        if len(rows) == 0:
            return None

        return {r["rule_key"]: r["rule_text"] for r in rows}

    async def get_log_channel_id(self) -> Optional[int]:
        return await self._select("log_channel", fetch_mode=FetchMode.VAL)

    async def set_log_channel_id(self, id: int | None):
        await self._update(log_channel=id)

    async def get_logger(self, bot) -> GuildLogger:
        log = GuildLogger()
        await log.load(bot, self.id)
        return log

    async def get_warnings_data(self) -> warnings_data:
        r = await self._select("warnings_threshold, timeout_duration")
        return warnings_data(r["timeout_duration"], r["warnings_threshold"])

    async def set_timeout_duration(self, value: int):
        await self._update(timeout_duration=value)

    async def set_warnings_threshold(self, value: int):
        await self._update(warnings_threshold=value)

    async def get_antiraid_data(self) -> AntiraidData:
        data = AntiraidData(self)
        await data.load()
        return data

    async def set_antiraid_enabled(self, value: bool):
        await self._update(antiraid_enabled=value)

    async def set_antiraid_join_interval(self, value: int):
        await self._update(antiraid_join_interval=value)

    async def set_antiraid_members_limit(self, value: int):
        await self._update(antiraid_members_limit=value)

    async def set_antiraid_punishment(self, value: int):
        await self._update(antiraid_punishment=value)
