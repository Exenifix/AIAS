import asyncio
from contextlib import redirect_stdout
from io import StringIO

import disnake
from disnake.ext import commands, tasks
from utils.bot import Bot
from utils.constants import TRAIN_GUILD_IDS
from utils.embeds import BaseEmbed, ErrorEmbed, SuccessEmbed
from utils.enums import FetchMode
from utils.errors import UNKNOWN, get_error_message


class SystemListeners(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_slash_command_error(
        self, inter: disnake.Interaction, error: commands.CommandError
    ):
        msg = get_error_message(inter, error)

        if msg is UNKNOWN:
            await inter.send(
                embed=ErrorEmbed(
                    inter, description=f"Unknown error occured\n```py\n{error}```"
                )
            )
            raise error

        await inter.send(
            embed=ErrorEmbed(
                inter, description=f"Sorry, an error occured:\n```py\n{msg}```"
            )
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: disnake.Guild):
        self.bot.log.info(
            "Joined guild: %s. Serving %s guilds now.", guild.name, len(self.bot.guilds)
        )
        await self.bot.log_channel.send(
            embed=BaseEmbed(
                self.bot.owner,
                "Joined Guild",
                f"**Name:** `{guild.name}\n**Owner:** {guild.owner}\n**Members:** `{guild.member_count}`",
            )
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: disnake.Guild):
        self.bot.log.info(
            "Left guild: %s. Serving %s guilds now.", guild.name, len(self.bot.guilds)
        )
        await self.bot.log_channel.send(
            embed=BaseEmbed(
                self.bot.owner,
                "Left Guild",
                f"**Name:** `{guild.name}\n**Owner:** {guild.owner}\n**Members:** `{guild.member_count}`",
            )
        )


class SystemLoops(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        self.presence_updater.start()

    @tasks.loop(minutes=30)
    async def presence_updater(self):
        await self.bot.change_presence(
            activity=disnake.Game(f"Watching {len(self.bot.guilds)} guilds...")
        )

    @presence_updater.before_loop
    async def loop_waiter(self):
        await self.bot.wait_until_ready()


class SystemCommands(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> bool:
        is_owner = await self.bot.is_owner(inter.author)
        if is_owner:
            return True

        raise commands.NotOwner()

    @commands.slash_command(
        name="exec",
        description="Executes some code. **Owner only**.",
        guild_ids=TRAIN_GUILD_IDS,
    )
    async def _exec(self, inter: disnake.ApplicationCommandInteraction, code: str):
        indented_code = ""
        for line in code.split("\n"):
            indented_code += " " * 12 + line + "\n"
        code = f"""
async def asyncf():
    try:
        s = StringIO()
        with redirect_stdout(s):
{indented_code}
        res = s.getvalue()
        embed = SuccessEmbed(inter, "Code was evaluated successfully.")
        if len(res) > 0:
            embed.add_field("Output", "```py\\n" + res + "```")
        await inter.send(embed=embed)
    except Exception as e:
        await inter.send(embed=ErrorEmbed(inter, "Failed to execute code.").add_field("Exception", str(e)))
    
asyncio.run_coroutine_threadsafe(asyncf(), asyncio.get_running_loop())"""
        env = {
            "asyncio": asyncio,
            "self": self,
            "inter": inter,
            "SuccessEmbed": SuccessEmbed,
            "ErrorEmbed": ErrorEmbed,
            "StringIO": StringIO,
            "redirect_stdout": redirect_stdout,
        }
        try:
            exec(code, env)
        except Exception as e:
            await inter.send(
                embed=ErrorEmbed(
                    inter,
                    description=f"Code was not executed due to an exception:\n```py{e}```",
                )
            )

    @commands.slash_command(
        name="execsql",
        description="Executes SQL query. **Owner only**",
        guild_ids=TRAIN_GUILD_IDS,
    )
    async def execsql(
        self,
        inter: disnake.ApplicationCommandInteraction,
        query: str,
        fetch_mode: FetchMode,
    ):
        fetch_mode = FetchMode(fetch_mode)
        r = await self.bot.db.execute(query, fetch_mode=fetch_mode)
        if fetch_mode == FetchMode.NONE or r is None:
            await inter.send(f"Query was executed successfully with no return.")

        elif fetch_mode == FetchMode.VAL:
            await inter.send(
                f"Query was executed successfully with return: ```py\n{r}```"
            )

        elif fetch_mode == FetchMode.ROW:
            text = "\t".join(map(str, r.values()))
            await inter.send(
                f"Query was executed successfully with return: ```py\n{text}```"
            )

        elif fetch_mode == FetchMode.ALL:
            text = "\n".join(["\t".join(map(str, q.values())) for q in r])
            if len(text) > 1000:
                text = text[:1000]
            await inter.send(
                f"Query was executed successfully with return: ```py\n{text}```"
            )


def setup(bot: Bot):
    bot.auto_setup(__name__)
