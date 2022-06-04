import os
import platform

import disnake
import psutil
from disnake.ext import commands

from utils.bot import Bot
from utils.embeds import BaseEmbed
from utils.enums import FetchMode


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


def setup(bot: Bot):
    bot.auto_setup(__name__)
