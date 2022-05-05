from datetime import datetime

import disnake
from disnake.ext import commands
from utils.bot import Bot
from utils.embeds import WarningEmbed
from utils.enums import Stat
from utils.filters.blacklist import is_blacklisted
from utils.nicknames import generate_random_nick
from utils.processors.antiraid import AntiraidProcessor
from utils.processors.messages import (
    AntiSpamProcessor,
    BlacklistProcessor,
    WhitelistProcessor,
)
from utils.utils import try_send


class Automod(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.antispam_processor = AntiSpamProcessor(bot)
        self.blacklist_processor = BlacklistProcessor(bot)
        self.whitelist_processor = WhitelistProcessor(bot)
        self.antiraid_processor = AntiraidProcessor(bot)
        self.permission_warnings: dict[int, datetime] = {}
        # structure {guild_id: {member1_id: Queue[Message], member2_id: Queue[Message]}}

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        if before.content != after.content:
            await self.on_message(after)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if (
            message.author.bot
            or message.channel.type == disnake.ChannelType.private
            or len(message.content) == 0
            or message.author.guild_permissions.manage_guild
            or not message.channel.permissions_for(message.guild.me).send_messages
        ):
            return

        await self._process_message(message)

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        if before.nick != after.nick:
            await self._process_nickfilter(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member):
        await self._process_nickfilter(member)
        amount = await self.antiraid_processor.process(member)
        if amount > 0:
            await self.bot.db.register_stat_increase(Stat.RAIDERS_PUNISHED)

    async def _process_message(self, message: disnake.Message):
        try:
            if await self.whitelist_processor.process(message):
                await self.bot.db.register_stat_increase(Stat.BAD_CHARACTERS_BLOCKED)
                return

            elif await self.antispam_processor.process(message):
                await self.bot.db.register_stat_increase(Stat.SPAM_BLOCKED)
                return

            elif await self.blacklist_processor.process(message):
                await self.bot.db.register_stat_increase(Stat.BAD_WORDS_BLOCKED)
                return
        except disnake.Forbidden:
            if (
                message.guild.id not in self.permission_warnings
                or (datetime.now() - self.permission_warnings[message.guild.id]).seconds
                >= 120
            ):
                self.permission_warnings[message.guild.id] = datetime.now()
                await message.channel.send(
                    embed=WarningEmbed(
                        message,
                        title="Missing Permissions",
                        description="The bot is missing `MANAGE MESSAGES` permission and cannot apply filters. Please grant the required permission to the bot.",
                    )
                )
        except disnake.NotFound:
            pass
        except Exception as e:
            raise e

    async def _process_nickfilter(self, member: disnake.Member):
        guild_data = self.bot.db.get_guild(member.guild.id)
        enabled, ignored = await guild_data.get_nickfilter_data()
        if not enabled or any(r.id in ignored for r in member.roles):
            return

        bl = await guild_data.get_blacklist_data()
        old_nick = member.display_name
        if is_blacklisted(bl, old_nick)[0]:
            nick = generate_random_nick()
            try:
                await member.edit(nick=nick)
            except disnake.Forbidden:
                self.bot.log.warning(
                    "Failed to change nickname of user %s in guild %s",
                    member,
                    member.guild,
                )
                return
            await try_send(
                member,
                f"Your current name on **{member.guild.name}** does not pass its blacklist filter, so you were given randomly generated **{nick}** nickname.",
            )
            log = await guild_data.get_logger(self.bot)
            await log.log_nick_change(member, old_nick, nick)
            await self.bot.db.register_stat_increase(Stat.NICKNAMES_FILTERED)


def setup(bot: Bot):
    bot.auto_setup(__name__)
