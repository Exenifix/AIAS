import re
from typing import Literal

import disnake

from ai.predictor import is_spam
from utils.bot import Bot
from utils.constants import MAX_SPAM_QUEUE_SIZE
from utils.embeds import WarningEmbed
from utils.filters.blacklist import is_blacklisted
from utils.filters.whitelist import contains_fonts
from utils.utils import Queue

LINK_REGEX = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z\d@:%._+~#=]{1,256}\.[a-zA-Z\d()]{1,6}\b([-a-zA-Z\d()@:%_+.~#?&/=]*)"
)


class MessageQueueProcessor:
    data: dict[int, dict[int, Queue[disnake.Message]]]
    bot: Bot

    def __init__(self, bot: Bot):
        self.data = {}
        self.bot = bot

    def add(self, message: disnake.Message) -> Queue[disnake.Message] | Literal[False]:
        if message.guild.id not in self.data:
            self.data[message.guild.id] = {
                message.author.id: Queue([message], max_size=MAX_SPAM_QUEUE_SIZE)
            }
            return False
        elif message.author.id not in self.data[message.guild.id]:
            self.data[message.guild.id][message.author.id] = Queue(
                [message], max_size=MAX_SPAM_QUEUE_SIZE
            )
            return False
        else:
            queue = self.data[message.guild.id][message.author.id]

            # replace the message in case it was edited
            for m in queue:
                if m.id == message.id:
                    queue.remove(m)
                    break

            queue.add(message)
            if len(self.data[message.guild.id][message.author.id]) <= 1:
                return False
            return queue

    def remove(self, message: disnake.Message):
        try:
            self.data[message.guild.id][message.author.id].remove(message)
            return True
        except (KeyError, ValueError):
            return False

    async def process(self, message: disnake.Message) -> bool:
        pass


class AntiSpamQueueProcessor(MessageQueueProcessor):
    async def process(self, message: disnake.Message) -> bool:
        queue = self.add(message)
        if queue is False:
            return False

        full_content = " ".join([m.content for m in queue])
        if is_spam(full_content):
            warnings = await self.bot.warnings.add_warning(message)
            if warnings != -1:
                await message.channel.send(
                    f"**{message.author.mention} stop spamming!**",
                    embed=WarningEmbed(
                        message,
                        title="Spam Blocked",
                        description=f"A sequence of messages ({len(queue)}) sent by {message.author.mention} was deleted.\n\
This member will be muted in **{warnings} warnings.**",
                    ),
                    delete_after=5,
                )
            log = await self.bot.db.get_guild(message.guild.id).get_logger(self.bot)
            await log.log_queue_deletion(message.author, message.channel, queue)
            await message.channel.delete_messages(queue)
            queue.clear()
            await self.bot.db.register_message(full_content)
            return True

        return False


class AntiSpamProcessor:
    queue_processor: AntiSpamQueueProcessor
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot
        self.queue_processor = AntiSpamQueueProcessor(bot)

    async def process(self, message: disnake.Message) -> bool:
        guild_data = self.bot.db.get_guild(message.guild.id)
        antispam = await guild_data.get_antispam_data()
        if (
            not antispam.enabled
            or message.channel.id in antispam.ignored
            or any(r.id in antispam.ignored for r in message.author.roles)
        ):
            return False

        if is_spam(message.content):
            await message.delete()
            warnings = await self.bot.warnings.add_warning(message)
            if warnings != -1:
                await message.channel.send(
                    f"**{message.author.mention}, stop spamming!**",
                    embed=WarningEmbed(
                        message,
                        title="Spam Blocked",
                        description=f"A message sent by {message.author.mention} was deleted.\n\
This member will be muted in **{warnings} warnings.**",
                    ),
                    delete_after=5,
                )
            log = await guild_data.get_logger(self.bot)
            await log.log_antispam(message.author, message.channel, message.content)
            await self.bot.db.register_message(message.content)
            return True
        else:
            return await self.queue_processor.process(message)


class BlacklistQueueProcessor(MessageQueueProcessor):
    async def process(self, message: disnake.Message) -> bool:
        queue = self.add(message)
        if queue is False:
            return False

        full_content = " ".join([m.content for m in queue])
        guild_data = self.bot.db.get_guild(message.guild.id)
        if is_blacklisted(
            await guild_data.get_blacklist_data(),
            full_content,
        )[0]:
            warnings = await self.bot.warnings.add_warning(message)
            if warnings != -1:
                await message.channel.send(
                    f"**{message.author.mention} do not curse!**",
                    embed=WarningEmbed(
                        message,
                        title="Blacklisted Expression Blocked",
                        description=f"A sequence of messages ({len(queue)}) sent by {message.author.mention} was deleted.\n\
This member will be muted in **{warnings} warnings.**",
                    ),
                    delete_after=5,
                )
            log = await guild_data.get_logger(self.bot)
            await log.log_queue_deletion(message.author, message.channel, queue)
            await message.channel.delete_messages(queue)
            queue.clear()
            return True

        return False


class BlacklistProcessor:
    queue_processor: BlacklistQueueProcessor
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot
        self.queue_processor = BlacklistQueueProcessor(bot)

    async def process(self, message: disnake.Message):
        guild = self.bot.db.get_guild(message.guild.id)
        blacklist = await guild.get_blacklist_data()
        if (
            not blacklist.enabled
            or message.channel.id in blacklist.ignored
            or any(r.id in blacklist.ignored for r in message.author.roles)
        ):
            return False

        is_curse, expr = is_blacklisted(blacklist, message.content)

        if is_curse:
            await message.delete()
            warnings = await self.bot.warnings.add_warning(message)
            if warnings != -1:
                embed = WarningEmbed(
                    message,
                    title="Blacklisted Expression Blocked",
                    description=f"A message sent by {message.author.mention} was deleted for \
containing blacklisted expressions.\n\
This member will be muted in **{warnings} warnings.**",
                )
                if expr is not None:
                    embed.add_field("Censored Version", f"```{expr}```", inline=False)

                await message.channel.send(
                    f"**{message.author.mention}, do not curse!**",
                    embed=embed,
                    delete_after=5,
                )
            log = await guild.get_logger(self.bot)
            await log.log_single_deletion(
                message.author, message.channel, message.content
            )
            return True
        else:
            return await self.queue_processor.process(message)


class WhitelistProcessor:
    bot: Bot

    def __init__(self, bot: Bot):
        self.bot = bot

    async def process(self, message: disnake.Message) -> bool:
        guild_data = self.bot.db.get_guild(message.guild.id)
        data = await guild_data.get_whitelist_data()
        if (
            not data.enabled
            or message.channel.id in data.ignored
            or any(r.id in data.ignored for r in message.author.roles)
        ):
            return False

        is_fonted, chars = contains_fonts(data.characters, message.content)

        if is_fonted:
            await message.delete()
            if len(chars) > 10:
                chars = chars[:10]
            await message.channel.send(
                embed=WarningEmbed(
                    message,
                    title="Fonts Detected",
                    description=f"{message.author.mention}, your message was removed because it contains blacklisted symbols.\n\
Blocked symbols: `{'`, `'.join(chars)}`.",
                ),
                delete_after=5,
            )
            log = await guild_data.get_logger(self.bot)
            await log.log_single_deletion(
                message.author, message.channel, message.content
            )
            return True

        return False


class LinksProcessor:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def process(self, message: disnake.Message) -> bool:
        if not await self.bot.db.get_guild(message.guild.id).get_linkfilter_enabled():
            return False

        raw_links = re.findall(LINK_REGEX, message.content)
        if len(raw_links) == 0:
            return False

        try:
            await message.add_reaction(self.bot.sys_emojis.load)
        except disnake.HTTPException:
            pass

        links = []
        for t in raw_links:
            for link in t:
                if len(link) > 0:
                    links.append(link)

        for link in links:
            if not await self.bot.db.is_link_safe(link):
                await message.delete()
                warnings = await self.bot.warnings.add_warning(message)
                if warnings != -1:
                    await message.channel.send(
                        embed=WarningEmbed(
                            message,
                            title="Malicious Link",
                            description=f"A message sent by {message.author.mention} \
was deleted because it contained a malicious link. This member will be muted in **{warnings}** warnings.",
                        )
                    )
                log = await self.bot.db.get_guild(message.guild.id).get_logger(self.bot)
                await log.log_single_deletion(
                    message.author, message.channel, message.content
                )
                return True
        try:
            await message.remove_reaction(self.bot.sys_emojis.load, self.bot.user)
            await message.add_reaction(self.bot.sys_emojis.checkmark)
        except disnake.HTTPException:
            pass

        return False
