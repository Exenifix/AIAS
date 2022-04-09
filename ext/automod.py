import disnake
from disnake.ext import commands
from ai.predictor import is_spam
from utils.bot import Bot
from utils.blacklist import is_blacklisted
from utils.embeds import BaseEmbed
from utils.errors import ManagerOnly
from utils.enums import BlacklistMode


class Automod(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        await self.bot.db.register_message(message.content)

        if await self._process_antispam(message):
            return

        elif await self._process_blacklist(message):
            return

    async def _process_antispam(self, message: disnake.Message) -> bool:
        if is_spam(message.content):
            await message.add_reaction("🧿")
            return True

        return False

    async def _process_blacklist(self, message: disnake.Message) -> bool:
        guild = self.bot.db.get_guild(message.guild.id)
        blacklist = await guild.get_blacklist_data()
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
            else:
                await message.channel.send(
                    f"{message.author.mention} your message was deleted for containing blacklisted content.",
                    delete_after=3,
                )

        return is_curse


class AutomodManagement(commands.Cog):
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
    async def blacklist_group(self, inter: disnake.ApplicationCommandInteraction):
        pass

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
**SUPER** - works just like the **WILD** but ignores spaces. Example: blacklisted - `frick`; expression - `fr icki ng`",
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
        bl = await self.bot.db.get_guild(inter.guild.id).get_blacklist_data()
        await bl.add_word(expression, mode)

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
        bl = await self.bot.db.get_guild(inter.guild.id).get_blacklist_data()
        await bl.remove_word(expression, mode)

        await inter.send(
            f"Successfully removed `{expression}` from the `{mode.value}` blacklist!"
        )


def setup(bot: Bot):
    bot.add_cog(Automod(bot))
    bot.add_cog(AutomodManagement(bot))
