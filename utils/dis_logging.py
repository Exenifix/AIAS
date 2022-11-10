from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, TYPE_CHECKING

import disnake
from exencolorlogs import Logger

from utils.embeds import BaseEmbed
from utils.enums import ActionType
from utils.views import AntispamView, UnbanView, UntimeoutView

if TYPE_CHECKING:
    from utils.bot import Bot

cooldowns: dict[int, "LogEntry"] = {}


@dataclass
class LogEntry:
    action: ActionType
    target: disnake.Member
    time: datetime


class GuildLogger:
    guild: disnake.Guild
    log_channel: disnake.TextChannel | None
    log: Logger
    bot: "Bot"

    async def load(self, bot: "Bot", guild_id: int):
        self.bot = bot
        self.guild: disnake.Guild = bot.get_guild(guild_id)
        self.log = Logger(f"GUILDLOG {guild_id}")
        guild = bot.db.get_guild(guild_id)
        log_id = await guild.get_log_channel_id()
        if log_id is None:
            self.log_channel = None
        else:
            try:
                self.log_channel = await self.guild.fetch_channel(log_id)
            except disnake.HTTPException:
                await guild.set_log_channel_id(None)
                self.log_channel = None

    async def _log_action(
        self,
        action: ActionType,
        target: disnake.Member,
        *,
        channel: disnake.TextChannel = None,
        blocked_content: str = None,
        deleted_messages: Sequence[disnake.Message] = None,
        timeout_duration: int = None,
        is_antiraid: bool = False,
        old_nickname: str = None,
        new_nickname: str = None,
        filtered_expression: str = None,
    ):
        if self.log_channel is None:
            return

        last_log_entry = cooldowns.get(target.guild.id, None)
        if last_log_entry is not None and (
            (last_log_entry.target == target and last_log_entry.action == action)
            or (datetime.now() - last_log_entry.time).seconds < 3
        ):
            return
        cooldowns[target.guild.id] = LogEntry(action, target, datetime.now())

        if blocked_content is not None and len(blocked_content) > 600:
            blocked_content = blocked_content[:600] + "..."

        embed = BaseEmbed(
            target,
            f"{self.bot.sys_emojis.checkmark} Action Logging",
            disnake.Embed.Empty,
        )
        embed.add_field("Target", f"**{target}** {target.mention}\n`{target.id}`")
        match action:
            case ActionType.SINGLE_DELETION:
                embed.description = f"A message was deleted from {channel.mention}."
                embed.add_field(
                    "Blocked Content", f"```{blocked_content}```", inline=False
                )

            case ActionType.BLACKLIST_DELETION:
                embed.description = (
                    f"A message was deleted from {channel.mention} because it contained blacklisted "
                    "expressions."
                )
                embed.add_field(
                    "Blocked Content", f"```{blocked_content}```", inline=False
                )
                if filtered_expression is not None:
                    embed.add_field("Filtered", filtered_expression)

            case ActionType.QUEUE_DELETION:
                embed.description = f"{len(deleted_messages)} messages were deleted from {channel.mention}."
                text = ""
                for msg in deleted_messages:
                    content = msg.content[:200]
                    text += f"[**{msg.author}**]: {content}\n"
                if len(text) == 0:
                    return
                embed.add_field("Deleted Messages", text, inline=False)

            case ActionType.ANTISPAM:
                view = AntispamView()
                embed.description = f"A message was deleted from {channel.mention}."
                embed.add_field(
                    "Blocked Content", f"```{blocked_content}```", inline=False
                )
                await self.log_channel.send(embed=embed, view=view)
                return

            case ActionType.TIMEOUT:
                embed.title = f"{self.bot.sys_emojis.checkmark} Member Timeout"
                embed.description = f"A member was timed out{' due to suspect of raid' if is_antiraid else ''}."
                embed.add_field("Duration", f"{timeout_duration} minutes", inline=False)
                view = UntimeoutView()
                await self.log_channel.send(embed=embed, view=view)
                return

            case ActionType.NICK_CHANGE:
                embed.title = f"{self.bot.sys_emojis.checkmark} Nick Blocked"
                embed.description = "A nickname was considered inappropriate."
                embed.add_field("Old Nickname", old_nickname, inline=False)
                embed.add_field("New Nickname", new_nickname, inline=False)

            case ActionType.ANTIRAID_BAN:
                embed.title = f"{self.bot.sys_emojis.exclamation} Member Banned"
                embed.description = "Member was suspected to be a raider."
                view = UnbanView()
                await self.log_channel.send(embed=embed, view=view)
                return

            case ActionType.ANTIRAID_KICK:
                embed.title = f"{self.bot.sys_emojis.warning} Member Kicked"
                embed.description = "Member was suspected to be a raider."

        try:
            await self.log_channel.send(embed=embed)
        except disnake.Forbidden:
            self.log.warning(
                "Failed to complete logging action in guild %s", self.guild
            )

    async def log_single_deletion(
        self, target: disnake.Member, channel: disnake.TextChannel, blocked_content: str
    ):
        await self._log_action(
            ActionType.SINGLE_DELETION,
            target,
            channel=channel,
            blocked_content=blocked_content,
        )

    async def log_queue_deletion(
        self,
        target: disnake.Member,
        channel: disnake.TextChannel,
        deleted_messages: Sequence[disnake.Message],
    ):
        await self._log_action(
            ActionType.QUEUE_DELETION,
            target,
            channel=channel,
            deleted_messages=deleted_messages,
        )

    async def log_timeout(
        self, target: disnake.Member, timeout_duration: int, is_antiraid: bool = False
    ):
        await self._log_action(
            ActionType.TIMEOUT,
            target,
            timeout_duration=timeout_duration,
            is_antiraid=is_antiraid,
        )

    async def log_nick_change(
        self, target: disnake.Member, old_nickname: str, new_nickname: str
    ):
        await self._log_action(
            ActionType.NICK_CHANGE,
            target,
            old_nickname=old_nickname,
            new_nickname=new_nickname,
        )

    async def log_antispam(
        self, target: disnake.Member, channel: disnake.TextChannel, blocked_content: str
    ):
        await self._log_action(
            ActionType.ANTISPAM,
            target,
            channel=channel,
            blocked_content=blocked_content,
        )

    async def log_antiraid_ban(self, target: disnake.Member):
        await self._log_action(ActionType.ANTIRAID_BAN, target)

    async def log_antiraid_kick(self, target: disnake.Member):
        await self._log_action(ActionType.ANTIRAID_KICK, target)

    async def log_blacklist_deletion(
        self,
        target: disnake.Member,
        channel: disnake.TextChannel,
        blocked_content: str,
        filtered_expression: str | None,
    ):
        await self._log_action(
            ActionType.BLACKLIST_DELETION,
            target,
            channel=channel,
            blocked_content=blocked_content,
            filtered_expression=filtered_expression,
        )
