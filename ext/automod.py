from datetime import datetime
import json

import disnake
from ai.predictor import is_spam
from disnake.ext import commands
from utils.bot import Bot
from utils.checks import is_automod_manager
from utils.constants import MAX_BLACKLIST_QUEUE_SIZE, MAX_SPAM_QUEUE_SIZE
from utils.embeds import BaseEmbed, ErrorEmbed, SuccessEmbed, WarningEmbed
from utils.enums import BlacklistMode, ViewResponse
from utils.filters.blacklist import is_blacklisted, preformat
from utils.filters.whitelist import contains_fonts
from utils.nicknames import generate_random_nick
from utils.utils import Queue, try_send
from utils.views import BaseView, Button, ConfirmationView


class Automod(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.antispam_queue: dict[int, dict[int, Queue[disnake.Message]]] = {}
        self.blacklist_queue: dict[int, dict[int, Queue[disnake.Message]]] = {}
        self.permission_warnings: dict[int, datetime] = {}
        # structure {guild_id: {member1_id: Queue[Message], member2_id: Queue[Message]}}

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        if before.content != after.content:
            await self.on_message(after)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot or len(message.content) == 0:
            return
        await self.bot.db.register_message(message.content)
        if message.author.guild_permissions.manage_guild:
            return

        try:
            if await self._process_whitelist(message):
                return

            elif await self._process_antispam(message):
                return

            elif await self._process_blacklist(message):
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
        except Exception as e:
            raise e

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):

        if before.nick == after.nick:
            return

        await self._process_nickfilter(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member):
        await self._process_nickfilter(member)

    async def _process_nickfilter(self, member: disnake.Member) -> bool:
        guild_data = self.bot.db.get_guild(member.guild.id)
        enabled, ignored = await guild_data.get_nickfilter_data()
        if not enabled or any(r.id in ignored for r in member.roles):
            return

        bl = await guild_data.get_blacklist_data()
        old_nick = member.display_name
        if is_blacklisted(bl, old_nick)[0]:
            nick = generate_random_nick()
            await member.edit(nick=nick)
            await try_send(
                member,
                f"Your current name on **{member.guild.name}** does not pass its blacklist filter, so you were given randomly generated **{nick}** nickname.",
            )
            log = await guild_data.get_logger(self.bot)
            await log.log_nick_change(member, old_nick, nick)

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
                    )
                log = await self.bot.db.get_guild(message.guild.id).get_logger(self.bot)
                await log.log_queue_deletion(message.author, message.channel, queue)
                await message.channel.delete_messages(queue)
                queue.clear()
                return True

        return False

    async def _process_blacklist_queue(self, message: disnake.Message):
        if not message.guild.id in self.blacklist_queue:
            self.blacklist_queue[message.guild.id] = {
                message.author.id: Queue([message], max_size=MAX_BLACKLIST_QUEUE_SIZE)
            }
            return False
        elif not message.author.id in self.blacklist_queue[message.guild.id]:
            self.blacklist_queue[message.guild.id][message.author.id] = Queue(
                [message], max_size=MAX_BLACKLIST_QUEUE_SIZE
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
                    )
                log = await guild_data.get_logger(self.bot)
                await log.log_queue_deletion(message.author, message.channel, queue)
                await message.channel.delete_messages(queue)
                queue.clear()
                return True

        return False

    async def _process_whitelist(self, message: disnake.Message):
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
                )
            )
            log = await guild_data.get_logger(self.bot)
            await log.log_single_deletion(
                message.author, message.channel, message.content
            )
            return True

        return False

    async def _process_antispam(self, message: disnake.Message) -> bool:
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
                )
            log = await guild_data.get_logger(self.bot)
            await log.log_antispam(message.author, message.channel, message.content)
            return True
        else:
            return await self._process_antispam_queue(message)

    async def _process_blacklist(self, message: disnake.Message) -> bool:
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
                    description=f"A message sent by {message.author.mention} was deleted for containing blacklisted expressions.\n\
This member will be muted in **{warnings} warnings.**",
                )
                if expr is not None:
                    embed.add_field("Censoured Version", f"```{expr}```", inline=False)

                await message.channel.send(
                    f"**{message.author.mention}, do not curse!**", embed=embed
                )
                log = await guild.get_logger(self.bot)
                await log.log_single_deletion(
                    message.author, message.channel, message.content
                )
        else:
            return await self._process_blacklist_queue(message)
        return is_curse


class BlacklistManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        with open("res/templates/blacklist.json", "r") as f:
            self.templates: dict[str, list[str]] = json.load(f)

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> bool:
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="blacklist")
    async def blacklist_group(self, *_):
        pass

    @blacklist_group.sub_command(
        name="enable", description="Enables blacklist filtering."
    )
    async def blacklist_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_enabled(True)
        await inter.send(
            embed=SuccessEmbed(inter, "Successfully enabled blacklist for this server.")
        )

    @blacklist_group.sub_command(
        name="disable", description="Disables blacklist filtering."
    )
    async def blacklist_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_enabled(False)
        await inter.send(
            embed=SuccessEmbed(
                inter, "Successfully disabled blacklist for this server."
            )
        )

    @blacklist_group.sub_command(
        name="setfilter",
        description="Set whether to send the censoured versions of the messages upon blacklisted expressions detection.",
    )
    async def blacklist_setfilter(
        self, inter: disnake.ApplicationCommandInteraction, value: bool
    ):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_filter_enabled(value)
        await inter.send(
            embed=SuccessEmbed(
                inter,
                f"Successfully {'enabled' if value else 'disabled'} blacklist filter fot this server.",
            )
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
            "**COMMON** - searches for exact occurences of the blacklisted words in a message.\n\n\
**WILD** - searches for the occurences of the blacklisted words everywhere in a message. \
This means that word may be spotted even if it is inside of another word. Example: blacklisted - `frick`; expression: `fricking`\n\n\
**SUPER** - works just like the **WILD** but ignores spaces. \
This can also detect words *across several messages*. Example: blacklisted - `frick`; expression - `fr icki ng`",
        )
        embed.add_field("Common", "`" + "`, `".join(bl.common) + "`")
        embed.add_field("Wild", "`" + "`, `".join(bl.wild) + "`")
        embed.add_field("Super", "`" + "`, `".join(bl.super) + "`")
        await inter.send(embed=embed, ephemeral=hidden)

    @blacklist_group.sub_command(
        name="templates",
        description="Load the word blacklist from the standart template. This preserves already existing words.",
    )
    async def blacklist_template(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        guild_data = self.bot.db.get_guild(inter.guild.id)
        for mode in BlacklistMode:
            await guild_data.addmany_blacklist_words(self.templates[mode.value], mode)

        await inter.send(
            embed=SuccessEmbed(inter, "Successfully loaded blacklist from template.")
        )

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
        if len(expression) == 0:
            await inter.send(
                embed=ErrorEmbed(
                    inter, f"The formatted version of this expression will be empty."
                )
            )
            return
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_word(expression, mode)

        await inter.send(
            embed=SuccessEmbed(
                inter, f"Successfully added new word to the `{mode.value}` blacklist!"
            )
        )

    @blacklist_group.sub_command(
        name="addmany",
        description="Adds several words to the blacklist. The words must be separated by commas.",
    )
    async def blacklist_addmany(
        self,
        inter: disnake.ApplicationCommandInteraction,
        mode: BlacklistMode = commands.Param(
            description="See the `/blacklist list` for more info about modes."
        ),
        words: str = commands.Param(description="The words separated by commas."),
    ):
        mode = BlacklistMode(mode)
        await inter.response.defer()
        await self.bot.db.get_guild(inter.guild.id).addmany_blacklist_words(
            words.split(","), mode
        )
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Successfully added new words to the `{mode.value}` blacklist!"
            )
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
            embed=SuccessEmbed(
                inter,
                f"Successfully removed `{expression}` from the `{mode.value}` blacklist!",
            )
        )

    @blacklist_group.sub_command(
        name="clear", description="Clears a certain blacklist (or all)."
    )
    async def blacklist_clear(
        self,
        inter: disnake.ApplicationCommandInteraction,
        mode: str = commands.Param(choices=[m.value for m in BlacklistMode] + ["all"]),
    ):
        if mode == "all":
            mode = None
        else:
            mode = BlacklistMode(mode)

        view = ConfirmationView(inter.author.id)
        await inter.send(
            embed=WarningEmbed(
                inter,
                title="Confirm Action",
                description=f"Are you sure you want to clear {'**all** blacklists?' if mode is None else mode.value + ' blacklist?'}",
            ),
            view=view,
        )
        res, inter = await view.get_result()
        if res == ViewResponse.YES:
            await self.bot.db.get_guild(inter.guild.id).clear_blacklist(mode)
            await inter.send(
                embed=SuccessEmbed(
                    inter, "Successfully cleared the requested blacklist."
                )
            )
        else:
            await inter.send(f"Operation cancelled.", delete_after=3)

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
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Added {role.mention} to blacklist ignored roles."
            )
        )

    @blacklist_ignore.sub_command(
        name="addchannel", description="Adds a channel to the blacklist ignored roles."
    )
    async def bi_addchannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_ignored(channel.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Added {channel.mention} to the blacklist ignored channels."
            )
        )

    @blacklist_ignore.sub_command(
        name="removerole",
        description="Removes a role from the blacklist ignored roles.",
    )
    async def bi_removerole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_ignored(role.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Removed {role.mention} from the blacklist ignored roles."
            )
        )

    @blacklist_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the blacklist ignored roles.",
    )
    async def bi_removechannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_ignored(channel.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Removed {channel.mention} from the blacklist ignored channels."
            )
        )


class AntiSpamManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ):
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="antispam")
    async def antispam_group(self, *_):
        pass

    @antispam_group.sub_command(
        name="enable", description="Enables antispam filtering."
    )
    async def antispam_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antispam_enabled(True)
        await inter.send(
            embed=SuccessEmbed(inter, "Successfully enabled antispam for this guild.")
        )

    @antispam_group.sub_command(
        name="disable", description="Disables antispam filtering."
    )
    async def antispam_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antispam_enabled(False)
        await inter.send(
            embed=SuccessEmbed(inter, "Successfully disabled antispam for this guild.")
        )

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
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Added {role.mention} to antispam ignored roles."
            )
        )

    @antispam_ignore.sub_command(
        name="addchannel",
        description="Adds a channel to the antispam ignored channels.",
    )
    async def as_addchannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).add_antispam_ignored(channel.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Added {channel.mention} to the antispam ignored channels."
            )
        )

    @antispam_ignore.sub_command(
        name="removerole",
        description="Removes a role from the antispam ignored roles.",
    )
    async def as_removerole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_antispam_ignored(role.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Removed {role.mention} from the antispam ignored roles"
            )
        )

    @antispam_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the antispam ignored channels.",
    )
    async def as_removechannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_antispam_ignored(channel.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Removed {channel.mention} from the antispam ignored channels."
            )
        )


class WhitelistManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        with open("res/templates/whitelist.json", "r") as f:
            self.templates: dict[str, str] = json.load(f)

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ):
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="whitelist")
    async def whitelist_group(self, *_):
        pass

    @whitelist_group.sub_command(
        name="enable", description="Enables character whitelist."
    )
    async def whitelist_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_whitelist_enabled(True)
        await inter.send(
            embed=SuccessEmbed(inter, "Successfully enabled whitelist for this guild.")
        )

    @whitelist_group.sub_command(
        name="disable", description="Disables whitelist filtering."
    )
    async def whitelist_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_whitelist_enabled(False)
        await inter.send(
            embed=SuccessEmbed(inter, "Successfully disabled whitelist for this guild.")
        )

    @whitelist_group.sub_command(
        name="setcharacters",
        description="Sets the characters that should be **only** be allowed in this server.",
    )
    async def whitelist_setcharacters(
        self, inter: disnake.ApplicationCommandInteraction, characters: str
    ):
        guild_data = self.bot.db.get_guild(inter.guild.id)
        data = await guild_data.get_whitelist_data()
        view = ConfirmationView(inter.author.id)
        await inter.send(
            embed=BaseEmbed(
                inter,
                f"{self.bot.sys_emojis.warning} Confirm Action",
                f"You are going to change the whitelisted characters.\n\
The whitelist is currently **{'enabled' if data.enabled else 'disabled'}**\n\
Current whitelisted characters: ```{data.characters}```\n\
**WARNING**\nAdding new set of characters will overwrite the existing ones. \
Please do not add uppercase symbols because all the messages are converted to lowercase.\n\n\
__**Are you sure you want to overwrite the existing characters with the new ones?**__\n\
```{data.characters}``` --> ```{characters}```",
            ),
            view=view,
        )
        res, inter = await view.get_result()
        if res == ViewResponse.YES:
            characters = "".join(set(characters.lower()))
            await guild_data.set_whitelist_characters(characters)
            await inter.send(
                embed=SuccessEmbed(
                    inter, "Successfully updated the whitelisted characters."
                )
            )
        else:
            await inter.send(f"Operation cancelled.", delete_after=3)

    @whitelist_group.sub_command(
        name="templates", description="Load a prepared whitelist template."
    )
    async def whitelist_templates(self, inter: disnake.ApplicationCommandInteraction):
        embed = BaseEmbed(
            inter,
            "Please choose a template",
            "Press the corresponding button to select a template. **THIS WILL __OVERWRITE__ THE CURRENT WHITELISTED CHARACTERS!**",
        )
        view = BaseView(inter.author.id, [])
        for name, value in self.templates.items():
            embed.add_field(name.capitalize(), f"```{value}```", inline=False)
            view.add_item(Button(name, label=name, style=disnake.ButtonStyle.blurple))

        view.add_item(Button("cancel", label="Cancel", style=disnake.ButtonStyle.red))

        await inter.send(embed=embed, view=view)
        res, inter = await view.get_result()
        if res == "cancel":
            await inter.send(f"Operation cancelled.")
            return

        await self.bot.db.get_guild(inter.guild.id).set_whitelist_characters(
            self.templates[res]
        )
        await inter.send(
            embed=SuccessEmbed(
                inter, "Successfully updated the whitelisted characters."
            )
        )

    @whitelist_group.sub_command_group(name="ignore")
    async def whitelist_ignore(self, *_):
        pass

    @whitelist_ignore.sub_command(
        name="addrole", description="Adds a role to the whitelist ignored roles."
    )
    async def wl_addrole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).add_whitelist_ignored(role.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Added {role.mention} to whitelist ignored roles."
            )
        )

    @whitelist_ignore.sub_command(
        name="addchannel",
        description="Adds a channel to the whitelist ignored channels.",
    )
    async def wl_addchannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).add_whitelist_ignored(channel.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Added {channel.mention} to the whitelist ignored channels."
            )
        )

    @whitelist_ignore.sub_command(
        name="removerole",
        description="Removes a role from the whitelist ignored roles.",
    )
    async def wl_removerole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_whitelist_ignored(role.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Removed {role.mention} from the whitelist ignored roles."
            )
        )

    @whitelist_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the whitelist ignored channels.",
    )
    async def wl_removechannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_whitelist_ignored(channel.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Removed {channel.mention} from the whitelist ignored channels."
            )
        )


class NickfilterManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> bool:
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="nickfilter")
    async def nickfilter_group(self, *_):
        pass

    @nickfilter_group.sub_command(name="enable", description="Enables NickFilter.")
    async def nickfilter_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_nickfilter_enabled(True)
        await inter.send(
            embed=SuccessEmbed(inter, "Successfully enabled NickFilter for this guild.")
        )

    @nickfilter_group.sub_command(name="disable", description="Disables NickFilter.")
    async def nickfilter_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_nickfilter_enabled(False)
        await inter.send(
            embed=SuccessEmbed(
                inter, "Successfully disabled NickFilter for this guild."
            )
        )

    @nickfilter_group.sub_command_group(name="ignore")
    async def nickfilter_ignore(self, *_):
        pass

    @nickfilter_ignore.sub_command(
        name="addrole", description="Adds a role to the NickFilter ignored roles."
    )
    async def nf_addrole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).add_nickfilter_ignored(role.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Added {role.mention} to NickFilter ignored roles."
            )
        )

    @nickfilter_ignore.sub_command(
        name="removerole",
        description="Removes a role from the NickFilter ignored roles.",
    )
    async def nf_removerole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_nickfilter_ignored(role.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Removed {role.mention} from the NickFilter ignored roles."
            )
        )


class Automation(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_message_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> bool:
        if inter.author.guild_permissions.manage_messages:
            return True

        raise commands.MissingPermissions("manage_messages")

    @commands.message_command(name="Delete and Warn")
    async def delete_and_warn(
        self, inter: disnake.MessageCommandInteraction, message: disnake.Message
    ):
        await message.delete()
        warnings = await self.bot.warnings.add_warning(message)
        if warnings != -1:
            await inter.send(
                embed=WarningEmbed(
                    message,
                    title="Message Blocked",
                    description=f"A message sent by {message.author.mention} was deleted by {inter.author.mention}.\n\
This member will be muted in **{warnings} warnings.**",
                ),
            )
        else:
            await inter.send(f"Member was muted", ephemeral=True)


class AutotimeoutManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, interaction: disnake.ApplicationCommandInteraction
    ):
        return await is_automod_manager(self.bot, interaction)

    @commands.slash_command(
        name="setwarningsthreshold",
        description="Sets the warnings threshold - the amount of warnings member receives before getting timeouted.",
    )
    async def setwarningsthreshold(
        self,
        inter: disnake.ApplicationCommandInteraction,
        amount: int = commands.Param(gt=0, le=10),
    ):
        await self.bot.db.get_guild(inter.guild.id).set_warnings_threshold(amount)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Successfully set warnings threshold to `{amount}`"
            )
        )

    @commands.slash_command(
        name="settimeoutduration", description="Sets the timeout duration for automod."
    )
    async def settimeoutduration(
        self,
        inter: disnake.ApplicationCommandInteraction,
        duration: int = commands.Param(
            description="The duration in minutes.", gt=0, le=80000
        ),
    ):
        await self.bot.db.get_guild(inter.guild.id).set_timeout_duration(duration)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Successfully set timeout duration to `{duration} m`"
            )
        )


def setup(bot: Bot):
    bot.auto_setup(__name__)
