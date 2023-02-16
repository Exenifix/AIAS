import asyncio
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO

import aiohttp
import disnake
from disnake.ext import commands, tasks
from dotenv import load_dotenv

from ai import predictor
from ai.train import train as train_ai
from utils import env
from utils.bot import Bot
from utils.constants import TRAIN_GUILD_IDS
from utils.embeds import BaseEmbed, ErrorEmbed, SuccessEmbed
from utils.enums import FetchMode
from utils.errors import UNKNOWN, get_error_message


class SystemListeners(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener("on_slash_command_error")
    @commands.Cog.listener("on_user_command_error")
    @commands.Cog.listener("on_message_command_error")
    async def error_handler(self, inter: disnake.Interaction, error: commands.CommandError):
        msg = get_error_message(inter, error)

        if msg is UNKNOWN:
            await inter.send(
                embed=ErrorEmbed(
                    inter,
                    description="Sorry, the bot has encountered unknown exception. The developer has already "
                    "been notified and this will be resolved as soon as possible. To get notified when it's fixed, "
                    "head to bot's [GitHub page](https://github.com/Exenifix/AIAS) and press **Watch** -> "
                    "**Custom Activity** -> **Releases**. When the issue is fixed, a new release will "
                    "be published. Also, you may join our [support server](https://discord.gg/TsSAfdN4hS) "
                    "and ask the developers themselves about it.",
                )
            )
            raise error

        await inter.send(embed=ErrorEmbed(inter, description=f"Sorry, an error occurred:\n```py\n{msg}```"))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: disnake.Guild):
        self.bot.log.info("Joined guild: %s. Serving %s guilds now.", guild.name, len(self.bot.guilds))
        await self.bot.db.execute(
            "INSERT INTO guilds (id, description) VALUES ($1, $2) "
            "ON CONFLICT (id) DO UPDATE SET description = $2 WHERE guilds.id = $1",
            guild.id,
            guild.description,
        )
        await self.bot.log_channel.send(
            embed=BaseEmbed(
                self.bot.owner,
                "Joined Guild",
                f"**Name:** `{guild.name}`\n**Owner:** {guild.owner}\n**Members:** `{guild.member_count}`",
            )
        )

        # attempt to find general and send a message to there
        embed = disnake.Embed(
            color=0x00FF00,
            title=":wave: Thanks for Inviting AIAS!",
            description="""Please complete bot setup as described \
            [here](https://github.com/Exenifix/AIAS/blob/master/README.md). \
Notice that **antispam is already enabled.**\n
Our bot uses AI to detect spam and may mistake sometimes, although it is trained on > 10k samples. \
If it blocks the message that is not spam, please lead to log channel \
(if you have setup it) and press **Not Spam** button. \
If bot didn't block spam message, use message command **Delete and Warn**. \
This will submit a sample to us for further review.\n
Once again, thanks for inviting AIAS! We hope it will help you improve moderation in your server!""",
        )
        channels_priority = ["general", "chat"]
        for name in channels_priority:
            for channel in guild.text_channels:
                if name in channel.name and channel.permissions_for(channel.guild.me).send_messages:
                    try:
                        await channel.send(embed=embed)
                        return
                    except disnake.HTTPException:
                        pass

        # in case the channel with expected name wasn't found, send the message to the first available
        for channel in guild.text_channels:
            if channel.permissions_for(channel.guild.me).send_messages:
                try:
                    await channel.send(embed=embed)
                    return
                except disnake.HTTPException:
                    continue

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: disnake.Guild):
        self.bot.log.info("Left guild: %s. Serving %s guilds now.", guild.name, len(self.bot.guilds))
        await self.bot.log_channel.send(
            embed=BaseEmbed(
                self.bot.owner,
                "Left Guild",
                f"**Name:** `{guild.name}`\n**Owner:** {guild.owner}\n**Members:** `{guild.member_count}`",
            )
        )

    @commands.Cog.listener()
    async def on_guild_update(self, before: disnake.Guild, after: disnake.Guild):
        if before.description != after.description:
            await self.bot.db.execute(
                "UPDATE guilds SET description = $1 WHERE id = $2",
                after.description,
                after.id,
            )


class SystemLoops(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.last_amount_submitted: int | None = None

        load_dotenv()
        self.tgg_token = env.main.TOPGG_TOKEN

        if not self.bot.test_version:
            self.presence_updater.start()

    @tasks.loop(minutes=30)
    async def presence_updater(self):
        # reset stats here not to create another useless loop
        if (await self.bot.db.get_daily_reset()).day != datetime.now().day:
            await self.bot.db.reset_daily_stats()

        guilds_count = len(self.bot.guilds)
        await self.bot.change_presence(
            activity=disnake.Activity(type=disnake.ActivityType.watching, name=f"{guilds_count} guilds...")
        )
        if self.last_amount_submitted != guilds_count:
            async with aiohttp.ClientSession(headers={"Authorization": self.tgg_token}) as session:
                r = await session.post(
                    "https://top.gg/api/bots/962093056910323743/stats",
                    json={"server_count": guilds_count},
                )
                if r.status != 200:
                    resp: dict = await r.json()
                    self.bot.log.warning(
                        "Failed to update top.gg stats. Error code: %s\nError: %s",
                        r.status,
                        resp.get("error", resp),
                    )
                else:
                    self.bot.log.ok("Successfully updated top.gg stats with %s", guilds_count)
                    self.last_amount_submitted = guilds_count

    @presence_updater.before_loop
    async def loop_waiter(self):
        await self.bot.wait_until_ready()


class SystemCommands(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
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
            await inter.send("Query was executed successfully with no return.")

        elif fetch_mode == FetchMode.VAL:
            await inter.send(f"Query was executed successfully with return: ```py\n{r}```")

        elif fetch_mode == FetchMode.ROW:
            text = "\t".join(map(str, r.values()))
            await inter.send(f"Query was executed successfully with return: ```py\n{text}```")

        elif fetch_mode == FetchMode.ALL:
            text = "\n".join(["\t".join(map(str, q.values())) for q in r])
            if len(text) > 1000:
                text = text[:1000]
            await inter.send(f"Query was executed successfully with return: ```py\n{text}```")

    @commands.slash_command(name="retrain", description="Retrains the model", guild_ids=TRAIN_GUILD_IDS)
    @commands.is_owner()
    async def retrain(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        predictor.load_model()
        await train_ai(self.bot.db)
        await inter.send("Model was retrained successfully!")


def setup(bot: Bot):
    bot.auto_setup(__name__)
