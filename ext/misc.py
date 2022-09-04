import os
import platform

import disnake
import psutil
from disnake.ext import commands

from utils.bot import Bot
from utils.embeds import BaseEmbed, ErrorEmbed, SuccessEmbed
from utils.enums import FetchMode
from utils.nicknames import generate_random_nick


class Miscellaneous(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.slash_command(name="stats", description="Show stats about the bot.")
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def stats(self, inter: disnake.ApplicationCommandInteraction):
        total_records = await self.bot.db.execute(
            "SELECT COUNT(1) FROM data", fetch_mode=FetchMode.VAL
        )
        validated_records = await self.bot.db.execute(
            "SELECT COUNT(1) FROM data WHERE is_spam IS NOT NULL",
            fetch_mode=FetchMode.VAL,
        )
        embed = (
            BaseEmbed(inter, "Bot Stats", "The stats of the AIAS!")
            .add_field("Bot Stats", await self.bot.db.get_stats(), inline=False)
            .add_field(
                "Server Stats",
                f"**CPU LOAD:** `{psutil.cpu_percent()}%`\n\
**MEMORY LOAD:** `{psutil.virtual_memory().percent}%`\n\
**PLATFORM:** `{platform.platform()}`\n\
**CPU:** `{platform.processor() or 'NO DATA'}`\n\
**PYTHON VERSION:** `{platform.python_version()}`",
                inline=False,
            )
            .add_field(
                "AI Stats",
                f"**MODEL SIZE:** `{os.path.getsize('ai/models/model.ai') // 1024}kb`\n\
**RECORDS:** `{total_records}` total, `{validated_records}` validated.",
                inline=False,
            )
        )

        await inter.send(embed=embed)

    @commands.message_command(name="Purge All Below")
    @commands.has_permissions(manage_messages=True)
    async def purge_all_below(
        self, inter: disnake.MessageCommandInteraction, message: disnake.Message
    ):
        await inter.response.defer(ephemeral=True)
        messages = await inter.channel.purge(
            after=message.created_at, check=lambda m: not m.pinned
        )
        await inter.send(
            embed=SuccessEmbed(
                inter,
                f"Successfully purged **{len(messages)} messages** here!",
                disable_bold=True,
            ),
            ephemeral=True,
        )

    @commands.user_command(name="Set Random Nick", dm_permission=False)
    @commands.has_permissions(manage_nicknames=True)
    async def set_random_nick(
        self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member
    ):
        if inter.user.top_role <= user.top_role:
            await inter.send(
                embed=ErrorEmbed(
                    inter,
                    "You cannot assign random nickname to someone higher or equal in role than you",
                ),
                ephemeral=True,
            )
            return
        nick = generate_random_nick()
        try:
            await user.edit(nick=nick)
        except disnake.Forbidden:
            await inter.send(
                embed=ErrorEmbed(inter, "Bot cannot edit nickname of this person"),
                ephemeral=True,
            )
            return
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Successfully set {user.mention}'s nickname to **{nick}**"
            )
        )


def setup(bot: Bot):
    bot.auto_setup(__name__)
