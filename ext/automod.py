from datetime import timedelta

import disnake
from ai.predictor import is_spam
from disnake.ext import commands, tasks
from utils.blacklist import is_blacklisted, preformat
from utils.bot import Bot
from utils.constants import MAX_SPAM_QUEUE_SIZE
from utils.embeds import BaseEmbed
from utils.enums import BlacklistMode
from utils.errors import ManagerOnly
from utils.utils import Queue


class Automod(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.warnings: dict[int, dict[int, int]] = {}
        self.antispam_queue: dict[int, dict[int, Queue[disnake.Message]]] = {}
        self.blacklist_queue: dict[int, dict[int, Queue[disnake.Message]]] = {}
        # structure {guild_id: {member1_id: Queue[Message], member2_id: Queue[Message]}}

        self.warnings_reseter.start()

    @tasks.loop(minutes=5)
    async def warnings_reseter(self):
        for guild_id in self.warnings:
            for member_id in self.warnings[guild_id]:
                if self.warnings[guild_id][member_id] > 0:
                    self.warnings[guild_id][member_id] -= 1

    @warnings_reseter.before_loop
    async def loop_waiter(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot:
            return
        await self.bot.db.register_message(message.content)

        if await self._process_antispam(message):
            return

        elif await self._process_blacklist(message):
            return

        elif await self._process_antispam_queue(message):
            return

        elif await self._process_blacklist_queue(message):
            return

    def _get_warnings(self, author: disnake.Member):
        if not author.guild.id in self.warnings:
            self.warnings[author.guild.id] = {author.id: 0}
            return 0
        elif not author.id in self.warnings[author.guild.id]:
            self.warnings[author.guild.id][author.id] = 0
            return 0
        else:
            return self.warnings[author.guild.id][author.id]

    async def _add_warning(self, message: disnake.Message):
        current_warnings = self._get_warnings(message.author)
        self.warnings[message.guild.id][message.author.id] += 1
        if current_warnings >= 3:
            await message.channel.send(f"{message.author.mention} enjoy your mute!")
            await message.author.timeout(
                duration=timedelta(minutes=15), reason="Warnings threshold exceed."
            )  # TODO: should be customizable
            self.warnings[message.guild.id][message.author.id] += 1
            return -1
        else:
            return 3 - current_warnings

    async def _process_antispam_queue(self, message: disnake.Message) -> bool:
        if not message.guild.id in self.antispam_queue:
            self.antispam_queue[message.guild.id] = {
                message.author.id: Queue([message], max_size=MAX_SPAM_QUEUE_SIZE)
            }
            return False
        elif not message.author.id in self.antispam_queue[message.guild.id]:
            self.antispam_queue[message.guild.id][message.author.id] = Queue(
                [message], max_size=MAX_SPAM_QUEUE_SIZE
            )
            return False
        elif len(self.antispam_queue[message.guild.id][message.author.id]) <= 1:
            queue = self.antispam_queue[message.guild.id][message.author.id]
            queue.add(message)
            return False
        else:
            queue = self.antispam_queue[message.guild.id][message.author.id]
            queue.add(message)
            full_content = " ".join([m.content for m in queue])
            if is_spam(full_content):
                warnings = await self._add_warning(message)
                if warnings != -1:
                    await message.channel.send(
                        f"{message.author.mention} stop spamming! You will be muted in **{warnings}** warnings."
                    )
                await message.channel.delete_messages(queue)
                queue.clear()
                return True

        return False

    async def _process_blacklist_queue(self, message: disnake.Message):
        if not message.guild.id in self.blacklist_queue:
            self.blacklist_queue[message.guild.id] = {
                message.author.id: Queue([message], max_size=MAX_SPAM_QUEUE_SIZE)
            }
            return False
        elif not message.author.id in self.blacklist_queue[message.guild.id]:
            self.blacklist_queue[message.guild.id][message.author.id] = Queue(
                [message], max_size=MAX_SPAM_QUEUE_SIZE
            )
            return False
        elif len(self.blacklist_queue[message.guild.id][message.author.id]) <= 1:
            queue = self.blacklist_queue[message.guild.id][message.author.id]
            queue.add(message)
            return False
        else:
            queue = self.blacklist_queue[message.guild.id][message.author.id]
            queue.add(message)
            full_content = " ".join([m.content for m in queue])
            if is_blacklisted(
                await self.bot.db.get_guild(message.guild.id).get_blacklist_data(),
                full_content,
            )[0]:
                warnings = await self._add_warning(message)
                if warnings != -1:
                    await message.channel.send(
                        f"{message.author.mention} do not curse! You will be muted in **{warnings}** warnings."
                    )
                await message.channel.delete_messages(queue)
                queue.clear()
                return True

        return False

    async def _process_antispam(self, message: disnake.Message) -> bool:
        antispam = await self.bot.db.get_guild(message.guild.id).get_antispam_data()
        if (
            not antispam.enabled
            or message.author.guild_permissions.manage_guild
            or message.channel.id in antispam.ignored
            or any([r.id in antispam.ignored for r in message.author.roles])
        ):
            return False

        if is_spam(message.content):
            await message.delete()
            warnings = await self._add_warning(message)
            if warnings != -1:
                await message.channel.send(
                    f"{message.author.mention} stop spamming! You will be muted in **{warnings}** warnings."
                )
            return True

    async def _process_blacklist(self, message: disnake.Message) -> bool:
        guild = self.bot.db.get_guild(message.guild.id)
        blacklist = await guild.get_blacklist_data()
        if (
            not blacklist.enabled
            or message.author.guild_permissions.manage_guild
            or message.channel.id in blacklist.ignored
            or any([r.id in blacklist.ignored for r in message.author.roles])
        ):
            return False

        is_curse, expr = is_blacklisted(blacklist, message.content)

        if is_curse:
            await message.delete()
            if expr is not None:
                await message.channel.send(
                    embed=BaseEmbed(
                        message,
                        "Cursing Detected",
                        f"Message authored by {message.author.mention} was deleted. Censoured version:\n```{expr}```",
                    )
                )
            warnings = await self._add_warning(message)
            if warnings != -1:
                await message.channel.send(
                    f"{message.author.mention} do not curse! You will be muted in **{warnings}** warnings."
                )
        return is_curse


class BlacklistManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> bool:
        managers = await self.bot.db.get_guild(inter.guild.id).get_automod_managers()
        if (
            inter.author.id in managers
            or inter.author.guild_permissions.manage_guild
            or any(r in managers for r in [role.id for role in inter.author.roles])
        ):
            return True

        raise ManagerOnly()

    @commands.slash_command(name="blacklist")
    async def blacklist_group(self, *_):
        pass

    @blacklist_group.sub_command(
        name="enable", description="Enables blacklist filtering."
    )
    async def blacklist_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_enabled(True)
        await inter.send(f"Successfully enabled blacklist for this server.")

    @blacklist_group.sub_command(
        name="disable", description="Disaales blacklist filtering."
    )
    async def blacklist_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_enabled(False)
        await inter.send(f"Successfully disabled blacklist for this server.")

    @blacklist_group.sub_command(
        name="setfilter",
        description="Set whether to send the censoured versions of the messages upon blacklisted expressions detection.",
    )
    async def blacklist_setfilter(
        self, inter: disnake.ApplicationCommandInteraction, value: bool
    ):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_filter_enabled(value)
        await inter.send(
            f"Successfully {'enabled' if value else 'disabled'} blacklist filter fot this server."
        )

    @blacklist_group.sub_command(
        name="list", description="Lists all the blacklisted expressions."
    )
    async def blacklist_list(
        self,
        inter: disnake.ApplicationCommandInteraction,
        hidden: bool = commands.Param(
            True,
            description="Whether to send the message as ephemeral, invisible to others.",
        ),
    ):
        bl = await self.bot.db.get_guild(inter.guild.id).get_blacklist_data()
        embed = BaseEmbed(
            inter,
            "Blacklisted Expressions",
            "**COMMON** - searches for exact occurences of the blacklisted words in a message.\n\
**WILD** - searches for the occurences of the blacklisted words everywhere in a message. This means that word may be spotted even if it is inside of another word. Example: blacklisted - `frick`; expression: `fricking`\n\
**SUPER** - works just like the **WILD** but ignores spaces. This can also detect words *across several messages*. Example: blacklisted - `frick`; expression - `fr icki ng`",
        )
        embed.add_field("Common", "`" + "`, `".join(bl.common) + "`")
        embed.add_field("Wild", "`" + "`, `".join(bl.wild) + "`")
        embed.add_field("Super", "`" + "`, `".join(bl.super) + "`")
        await inter.send(embed=embed, ephemeral=hidden)

    @blacklist_group.sub_command(
        name="add", description="Adds a new blacklisted expression."
    )
    async def blacklist_add(
        self,
        inter: disnake.ApplicationCommandInteraction,
        mode: BlacklistMode = commands.Param(
            description="See the `/blacklist list` for more info about modes."
        ),
        expression: str = commands.Param(),
    ):
        mode = BlacklistMode(mode)
        expression = preformat(expression, mode)
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_word(expression, mode)

        await inter.send(
            f"Successfully added new word to the `{mode.value}` blacklist!"
        )

    @blacklist_group.sub_command(
        name="remove", description="Removes a blacklisted expression."
    )
    async def blacklist_remove(
        self,
        inter: disnake.ApplicationCommandInteraction,
        mode: BlacklistMode = commands.Param(
            description="See the `/blacklist list` for more info about modes."
        ),
        expression: str = commands.Param(),
    ):
        mode = BlacklistMode(mode)
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_word(
            expression, mode
        )

        await inter.send(
            f"Successfully removed `{expression}` from the `{mode.value}` blacklist!"
        )

    @blacklist_group.sub_command_group(name="ignore")
    async def blacklist_ignore(self, *_):
        pass

    @blacklist_ignore.sub_command(
        name="addrole", description="Adds a role to the blacklist ignored roles."
    )
    async def bi_addrole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_ignored(role.id)
        await inter.send(f"Added {role.mention} to blacklist ignored roles.")

    @blacklist_ignore.sub_command(
        name="addchannel", description="Adds a channel to the blacklist ignored roles."
    )
    async def bi_addchannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_ignored(channel.id)
        await inter.send(f"Added {channel.mention} to the blacklist ignored channels.")

    @blacklist_ignore.sub_command(
        name="removerole",
        description="Removes a role from the blacklist ignored roles.",
    )
    async def bi_removerole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_ignored(role.id)
        await inter.send(f"Removed {role.mention} from the blacklist ignored roles.")

    @blacklist_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the blacklist ignored roles.",
    )
    async def bi_removechannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_ignored(channel.id)
        await inter.send(
            f"Removed {channel.mention} from the blacklist ignored channels."
        )


class AntiSpamManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ):
        # basically copying the slash check from blacklist management, might bring this out to external function
        return await BlacklistManagement.cog_slash_command_check(self, inter)

    @commands.slash_command(name="antispam")
    async def antispam_group(self, *_):
        pass

    @antispam_group.sub_command(
        name="enable", description="Enables antispam filtering."
    )
    async def antispam_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antispam_enabled(True)
        await inter.send(f"Successfully enabled antispam for this guild.")

    @antispam_group.sub_command(
        name="disable", description="Disaales antispam filtering."
    )
    async def antispam_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antispam_enabled(False)
        await inter.send(f"Successfully disabled antispam for this guild.")

    @antispam_group.sub_command_group(name="ignore")
    async def antispam_ignore(self, *_):
        pass

    @antispam_ignore.sub_command(
        name="addrole", description="Adds a role to the antispam ignored roles."
    )
    async def as_addrole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).add_antispam_ignored(role.id)
        await inter.send(f"Added {role.mention} to antispam ignored roles.")

    @antispam_ignore.sub_command(
        name="addchannel", description="Adds a channel to the antispam ignored roles."
    )
    async def as_addchannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).add_antispam_ignored(channel.id)
        await inter.send(f"Added {channel.mention} to the antispam ignored channels.")

    @antispam_ignore.sub_command(
        name="removerole",
        description="Removes a role from the antispam ignored roles.",
    )
    async def as_removerole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_antispam_ignored(role.id)
        await inter.send(f"Removed {role.mention} from the antispam ignored roles.")

    @antispam_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the antispam ignored roles.",
    )
    async def as_removechannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_antispam_ignored(channel.id)
        await inter.send(
            f"Removed {channel.mention} from the antispam ignored channels."
        )


def setup(bot: Bot):
    bot.add_cog(Automod(bot))
    bot.add_cog(BlacklistManagement(bot))
    bot.add_cog(AntiSpamManagement(bot))
