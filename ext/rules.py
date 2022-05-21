import disnake
from disnake.ext import commands

from utils.autocomplete import autocomplete_rules
from utils.bot import Bot
from utils.checks import is_automod_manager
from utils.embeds import BaseEmbed, SuccessEmbed
from utils.utils import sorted_dict, split_text


class RulesManagement(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ):
        return await is_automod_manager(self.bot, inter)

    @commands.slash_command(
        name="addrule", description="Adds a single rule to the rules storage."
    )
    async def addrule(
        self, inter: disnake.ApplicationCommandInteraction, key: str, value: str
    ):
        await self.bot.db.get_guild(inter.guild.id).add_rule(key, value)
        await inter.send(embed=SuccessEmbed(inter, "Successfully added a new rule."))

    @commands.slash_command(
        name="removerule", description="Removes a single rule from the rules storage."
    )
    async def removerule(self, inter: disnake.ApplicationCommandInteraction, key: str):
        await self.bot.db.get_guild(inter.guild.id).remove_rule(key)
        await inter.send(
            embed=SuccessEmbed(inter, f"Successfully removed rule `{key}`")
        )


class Rules(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.slash_command(
        name="listruleskeys",
        description="Lists rules' **keys**.",
    )
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def listruleskeys(self, inter: disnake.ApplicationCommandInteraction):
        rules = await self.bot.db.get_guild(inter.guild.id).get_all_rules()
        if rules is None:
            await inter.send(f"There are no rules.", ephemeral=True)
            return

        rules = sorted(rules.keys())
        await inter.send(
            embed=BaseEmbed(inter, "Rules", "`" + "`, `".join(rules) + "`")
        )

    @commands.slash_command(
        name="listrules", description="List all rules as an ephemeral message."
    )
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def listrules(self, inter: disnake.ApplicationCommandInteraction):
        rules = await self.bot.db.get_guild(inter.guild.id).get_all_rules()
        if rules is None:
            await inter.send(f"There are no rules.", ephemeral=True)

        rules = sorted_dict(rules)
        text = ""
        for k, v in rules.items():
            text += f"{k}: {v}\n"

        texts = []
        if len(text) > 1024:
            texts = split_text(text, 1024)
        else:
            texts = [text]

        for txt in texts:
            await inter.send(txt, ephemeral=True)

    @commands.slash_command(
        name="rule", description="Fetches contents of a single rule."
    )
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def select_rule(
        self,
        inter: disnake.ApplicationCommandInteraction,
        key: str = commands.Param(autocomplete=autocomplete_rules),
    ):
        rule = await self.bot.db.get_guild(inter.guild.id).get_rule(key)
        await inter.send(embed=BaseEmbed(inter, f"Rule {key}", rule))


def setup(bot: Bot):
    bot.auto_setup(__name__)
