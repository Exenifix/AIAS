import json
import typing

import disnake
from disnake.ext import commands

from utils.bot import Bot
from utils.checks import is_automod_manager
from utils.embeds import BaseEmbed, ErrorEmbed, SuccessEmbed, WarningEmbed
from utils.enums import AntiraidPunishment, BlacklistMode, ViewResponse
from utils.filters.blacklist import preformat
from utils.views import BaseView, Button, ConfirmationView


class BlacklistManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        with open("res/templates/blacklist.json", "r") as f:
            self.templates: dict[str, list[str]] = json.load(f)

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="blacklist")
    async def blacklist_group(self, *_):
        pass

    @blacklist_group.sub_command(name="enable", description="Enables blacklist filtering.")
    async def blacklist_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_enabled(True)
        await inter.send(embed=SuccessEmbed(inter, "Successfully enabled blacklist for this server."))

    @blacklist_group.sub_command(name="disable", description="Disables blacklist filtering.")
    async def blacklist_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_enabled(False)
        await inter.send(embed=SuccessEmbed(inter, "Successfully disabled blacklist for this server."))

    @blacklist_group.sub_command(
        name="setfilter",
        description="Set whether to send the censored versions of the messages upon blacklisted expressions detection.",
    )
    async def blacklist_setfilter(self, inter: disnake.ApplicationCommandInteraction, value: bool):
        await self.bot.db.get_guild(inter.guild.id).set_blacklist_filter_enabled(value)
        await inter.send(
            embed=SuccessEmbed(
                inter,
                f"Successfully {'enabled' if value else 'disabled'} blacklist filter fot this server.",
            )
        )

    @blacklist_group.sub_command(name="list", description="Lists all the blacklisted expressions.")
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
            "**COMMON** - searches for exact occurrences of the blacklisted words in a message.\n\n\
**WILD** - searches for the occurrences of the blacklisted words everywhere in a message. \
This means that word may be spotted even if it is inside of another word. \
Example: blacklisted - `frick`; expression: `fricking`\n\n\
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

        await inter.send(embed=SuccessEmbed(inter, "Successfully loaded blacklist from template."))

    @blacklist_group.sub_command(name="add", description="Adds a new blacklisted expression.")
    async def blacklist_add(
        self,
        inter: disnake.ApplicationCommandInteraction,
        mode: BlacklistMode = commands.Param(description="See the `/blacklist list` for more info about modes."),
        expression: str = commands.Param(),
    ):
        mode = BlacklistMode(mode)
        expression = preformat(expression, mode)
        if len(expression) == 0:
            await inter.send(embed=ErrorEmbed(inter, "The formatted version of this expression will be empty."))
            return
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_word(expression, mode)

        await inter.send(embed=SuccessEmbed(inter, f"Successfully added new word to the `{mode.value}` blacklist!"))

    @blacklist_group.sub_command(
        name="addmany",
        description="Adds several words to the blacklist. The words must be separated by commas.",
    )
    async def blacklist_addmany(
        self,
        inter: disnake.ApplicationCommandInteraction,
        mode: BlacklistMode = commands.Param(description="See the `/blacklist list` for more info about modes."),
        words: str = commands.Param(description="The words separated by commas."),
    ):
        mode = BlacklistMode(mode)
        await inter.response.defer()
        await self.bot.db.get_guild(inter.guild.id).addmany_blacklist_words(words.split(","), mode)
        await inter.send(embed=SuccessEmbed(inter, f"Successfully added new words to the `{mode.value}` blacklist!"))

    @blacklist_group.sub_command(name="remove", description="Removes a blacklisted expression.")
    async def blacklist_remove(
        self,
        inter: disnake.ApplicationCommandInteraction,
        mode: BlacklistMode = commands.Param(description="See the `/blacklist list` for more info about modes."),
        expression: str = commands.Param(),
    ):
        mode = BlacklistMode(mode)
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_word(expression, mode)

        await inter.send(
            embed=SuccessEmbed(
                inter,
                f"Successfully removed `{expression}` from the `{mode.value}` blacklist!",
            )
        )

    @blacklist_group.sub_command(name="clear", description="Clears a certain blacklist (or all).")
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
                description=f"Are you sure you want to clear \
{'**all** blacklists?' if mode is None else mode.value + ' blacklist?'}",
            ),
            view=view,
        )
        res, inter = await view.get_result()
        if res == ViewResponse.YES:
            await self.bot.db.get_guild(inter.guild.id).clear_blacklist(mode)
            await inter.send(embed=SuccessEmbed(inter, "Successfully cleared the requested blacklist."))
        else:
            await inter.send("Operation cancelled.", delete_after=3)

    @blacklist_group.sub_command_group(name="ignore")
    async def blacklist_ignore(self, *_):
        pass

    @blacklist_ignore.sub_command(name="addrole", description="Adds a role to the blacklist ignored roles.")
    async def bi_addrole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Added {role.mention} to blacklist ignored roles."))

    @blacklist_ignore.sub_command(name="addchannel", description="Adds a channel to the blacklist ignored roles.")
    async def bi_addchannel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await self.bot.db.get_guild(inter.guild.id).add_blacklist_ignored(channel.id)
        await inter.send(embed=SuccessEmbed(inter, f"Added {channel.mention} to the blacklist ignored channels."))

    @blacklist_ignore.sub_command(
        name="removerole",
        description="Removes a role from the blacklist ignored roles.",
    )
    async def bi_removerole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Removed {role.mention} from the blacklist ignored roles."))

    @blacklist_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the blacklist ignored roles.",
    )
    async def bi_removechannel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await self.bot.db.get_guild(inter.guild.id).remove_blacklist_ignored(channel.id)
        await inter.send(embed=SuccessEmbed(inter, f"Removed {channel.mention} from the blacklist ignored channels."))


class AntiSpamManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction):
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="antispam")
    async def antispam_group(self, *_):
        pass

    @antispam_group.sub_command(name="enable", description="Enables antispam filtering.")
    async def antispam_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antispam_enabled(True)
        await inter.send(embed=SuccessEmbed(inter, "Successfully enabled antispam for this guild."))

    @antispam_group.sub_command(name="disable", description="Disables antispam filtering.")
    async def antispam_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antispam_enabled(False)
        await inter.send(embed=SuccessEmbed(inter, "Successfully disabled antispam for this guild."))

    @antispam_group.sub_command_group(name="ignore")
    async def antispam_ignore(self, *_):
        pass

    @antispam_ignore.sub_command(name="addrole", description="Adds a role to the antispam ignored roles.")
    async def as_addrole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).add_antispam_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Added {role.mention} to antispam ignored roles."))

    @antispam_ignore.sub_command(
        name="addchannel",
        description="Adds a channel to the antispam ignored channels.",
    )
    async def as_addchannel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await self.bot.db.get_guild(inter.guild.id).add_antispam_ignored(channel.id)
        await inter.send(embed=SuccessEmbed(inter, f"Added {channel.mention} to the antispam ignored channels."))

    @antispam_ignore.sub_command(
        name="removerole",
        description="Removes a role from the antispam ignored roles.",
    )
    async def as_removerole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).remove_antispam_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Removed {role.mention} from the antispam ignored roles"))

    @antispam_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the antispam ignored channels.",
    )
    async def as_removechannel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await self.bot.db.get_guild(inter.guild.id).remove_antispam_ignored(channel.id)
        await inter.send(embed=SuccessEmbed(inter, f"Removed {channel.mention} from the antispam ignored channels."))


class WhitelistManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        with open("res/templates/whitelist.json", "r") as f:
            self.templates: dict[str, str] = json.load(f)

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction):
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="whitelist")
    async def whitelist_group(self, *_):
        pass

    @whitelist_group.sub_command(name="enable", description="Enables character whitelist.")
    async def whitelist_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_whitelist_enabled(True)
        await inter.send(embed=SuccessEmbed(inter, "Successfully enabled whitelist for this guild."))

    @whitelist_group.sub_command(name="disable", description="Disables whitelist filtering.")
    async def whitelist_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_whitelist_enabled(False)
        await inter.send(embed=SuccessEmbed(inter, "Successfully disabled whitelist for this guild."))

    @whitelist_group.sub_command(
        name="setcharacters",
        description="Sets the characters that should be **only** be allowed in this server.",
    )
    async def whitelist_setcharacters(self, inter: disnake.ApplicationCommandInteraction, characters: str):
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
            await inter.send(embed=SuccessEmbed(inter, "Successfully updated the whitelisted characters."))
        else:
            await inter.send("Operation cancelled.", delete_after=3)

    @whitelist_group.sub_command(name="templates", description="Load a prepared whitelist template.")
    async def whitelist_templates(self, inter: disnake.ApplicationCommandInteraction):
        embed = BaseEmbed(
            inter,
            "Please choose a template",
            "Press the corresponding button to select a template. \
**THIS WILL __OVERWRITE__ THE CURRENT WHITELISTED CHARACTERS!**",
        )
        view = BaseView(inter.author.id, [])
        for name, value in self.templates.items():
            embed.add_field(name.capitalize(), f"```{value}```", inline=False)
            view.add_item(Button(name, label=name, style=disnake.ButtonStyle.blurple))

        view.add_item(Button("cancel", label="Cancel", style=disnake.ButtonStyle.red))

        await inter.send(embed=embed, view=view)
        res, inter = await view.get_result()
        if res == "cancel":
            await inter.send("Operation cancelled.")
            return

        await self.bot.db.get_guild(inter.guild.id).set_whitelist_characters(self.templates[res])
        await inter.send(embed=SuccessEmbed(inter, "Successfully updated the whitelisted characters."))

    @whitelist_group.sub_command(name="addchars", description="Adds specified characters to the whitelist.")
    async def whitelist_addchars(
        self,
        inter: disnake.ApplicationCommandInteraction,
        characters: str = disnake.Option(
            "characters",
            description="Just a load of characters you want to add, no any separators.",
        ),
    ):
        if len(characters) >= 50:
            await inter.send("No more than 50 characters can be added at once.")
        await inter.response.defer()
        added = await self.bot.db.get_guild(inter.guild.id).add_whitelist_characters(characters)
        await inter.send(f"Successfully added **{added}** characters.")

    @whitelist_group.sub_command(
        name="removechars",
        description="Removes specified characters from the whitelist.",
    )
    async def whitelist_removechars(
        self,
        inter: disnake.ApplicationCommandInteraction,
        characters: str = disnake.Option(
            "characters",
            description="Just a load of characters you want to remove, no any separators.",
        ),
    ):
        await inter.response.defer()
        removed = await self.bot.db.get_guild(inter.guild.id).add_whitelist_characters(characters)
        await inter.send(f"Successfully removed **{removed}** characters.")

    @whitelist_group.sub_command_group(name="ignore")
    async def whitelist_ignore(self, *_):
        pass

    @whitelist_ignore.sub_command(name="addrole", description="Adds a role to the whitelist ignored roles.")
    async def wl_addrole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).add_whitelist_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Added {role.mention} to whitelist ignored roles."))

    @whitelist_ignore.sub_command(
        name="addchannel",
        description="Adds a channel to the whitelist ignored channels.",
    )
    async def wl_addchannel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await self.bot.db.get_guild(inter.guild.id).add_whitelist_ignored(channel.id)
        await inter.send(embed=SuccessEmbed(inter, f"Added {channel.mention} to the whitelist ignored channels."))

    @whitelist_ignore.sub_command(
        name="removerole",
        description="Removes a role from the whitelist ignored roles.",
    )
    async def wl_removerole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).remove_whitelist_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Removed {role.mention} from the whitelist ignored roles."))

    @whitelist_ignore.sub_command(
        name="removechannel",
        description="Removes a channel from the whitelist ignored channels.",
    )
    async def wl_removechannel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await self.bot.db.get_guild(inter.guild.id).remove_whitelist_ignored(channel.id)
        await inter.send(embed=SuccessEmbed(inter, f"Removed {channel.mention} from the whitelist ignored channels."))


class NickfilterManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="nickfilter")
    async def nickfilter_group(self, *_):
        pass

    @nickfilter_group.sub_command(name="enable", description="Enables NickFilter.")
    async def nickfilter_enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_nickfilter_enabled(True)
        await inter.send(embed=SuccessEmbed(inter, "Successfully enabled NickFilter for this guild."))

    @nickfilter_group.sub_command(name="disable", description="Disables NickFilter.")
    async def nickfilter_disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_nickfilter_enabled(False)
        await inter.send(embed=SuccessEmbed(inter, "Successfully disabled NickFilter for this guild."))

    @nickfilter_group.sub_command_group(name="ignore")
    async def nickfilter_ignore(self, *_):
        pass

    @nickfilter_ignore.sub_command(name="addrole", description="Adds a role to the NickFilter ignored roles.")
    async def nf_addrole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).add_nickfilter_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Added {role.mention} to NickFilter ignored roles."))

    @nickfilter_ignore.sub_command(
        name="removerole",
        description="Removes a role from the NickFilter ignored roles.",
    )
    async def nf_removerole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).remove_nickfilter_ignored(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Removed {role.mention} from the NickFilter ignored roles."))


class Automation(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_message_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if inter.author.guild_permissions.manage_messages:
            return True

        raise commands.MissingPermissions(["manage_messages"])

    @commands.message_command(name="Delete and Warn")
    async def delete_and_warn(self, inter: disnake.MessageCommandInteraction, message: disnake.Message):
        await inter.response.defer(ephemeral=True)
        await message.delete()
        warnings = await self.bot.warnings.add_warning(message)
        if warnings != -1:
            await inter.channel.send(
                embed=WarningEmbed(
                    message,
                    title="Message Blocked",
                    description=f"A message sent by {message.author.mention} was deleted by {inter.author.mention}.\n\
This member will be muted in **{warnings} warnings.**",
                ),
            )
        else:
            await inter.send("Member was muted", ephemeral=True)

        view = ConfirmationView(inter.author.id)
        await inter.send("Was this message a spam message?", view=view)
        res, inter = await view.get_result()
        if res == ViewResponse.YES:
            await inter.send(
                "Okay, we sent the message to our database for further review. Thanks for helping us improve!",
                ephemeral=True,
            )
            await self.bot.db.register_message(message.content)
        elif res == ViewResponse.NO:
            await inter.send("Thanks for feedback!", ephemeral=True)
        elif res == ViewResponse.TIMEOUT:
            await inter.edit_original_message(content="Interaction timed out.", view=None)


class AutotimeoutManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(self, interaction: disnake.ApplicationCommandInteraction):
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
        await inter.send(embed=SuccessEmbed(inter, f"Successfully set warnings threshold to `{amount}`"))

    @commands.slash_command(name="settimeoutduration", description="Sets the timeout duration for automod.")
    async def settimeoutduration(
        self,
        inter: disnake.ApplicationCommandInteraction,
        duration: int = commands.Param(description="The duration in minutes.", gt=0, le=80000),
    ):
        await self.bot.db.get_guild(inter.guild.id).set_timeout_duration(duration)
        await inter.send(embed=SuccessEmbed(inter, f"Successfully set timeout duration to `{duration} m`"))


class AntiraidManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(name="antiraid")
    async def antiraid(self, _):
        pass

    @antiraid.sub_command(name="enable", description="Enables antiraid for this server. BETA FEATURE!")
    async def enable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antiraid_enabled(True)
        await inter.send(embed=SuccessEmbed(inter, "Successfully enabled antiraid for this server!"))

    @antiraid.sub_command(name="disable", description="Disables antiraid for this server.")
    async def disable(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_antiraid_enabled(False)
        await inter.send(embed=SuccessEmbed(inter, "Successfully disabled antiraid for this server!"))

    @antiraid.sub_command(name="setup", description="Set how many members can join per certain interval.")
    async def setup(
        self,
        inter: disnake.ApplicationCommandInteraction,
        members: int = commands.Param(ge=3, le=15),
        interval: int = commands.Param(description="In seconds", ge=5, le=120),
    ):
        guild_data = self.bot.db.get_guild(inter.guild.id)
        await guild_data.set_antiraid_members_limit(members)
        await guild_data.set_antiraid_join_interval(interval)
        await inter.send(
            embed=SuccessEmbed(
                inter,
                f"Successfully set antiraid limit to `{members}` members per `{interval}` seconds!",
            )
        )

    @antiraid.sub_command(name="setpunishment", description="Set punishment for raiders.")
    async def setpunishment(
        self,
        inter: disnake.ApplicationCommandInteraction,
        punishment: AntiraidPunishment,
    ):
        await self.bot.db.get_guild(inter.guild.id).set_antiraid_punishment(typing.cast(int, punishment))
        await inter.send(embed=SuccessEmbed(inter, "Successfully updated antiraid punishment!"))

    @antiraid.sub_command(name="setinvitepauseduration")
    async def setinvitepauseduration(self, inter: disnake.ApplicationCommandInteraction, duration: int):
        """
        Set the invite pause duration when the raid occurs

        Parameters
        ----------
        duration: Minutes to pause invites for. Set to 0 to disable

        """
        await self.bot.db.get_guild(inter.guild.id).set_antiraid_invite_pause_duration(
            abs(duration) if duration != 0 else None
        )
        await inter.send(
            embed=SuccessEmbed(
                inter,
                "Successfully set new invite pause duration" if duration != 0 else "Successfully disabled invite pause",
            )
        )


def setup(bot: Bot):
    bot.auto_setup(__name__)
