import disnake
from ai.predictor import is_spam
from disnake.ext import commands
from utils.bot import Bot
from utils.constants import TRAIN_GUILD_IDS
from utils.enums import FetchMode, ViewResponse
from utils.views import PhraseProcessingView


class Training(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.active_sessions: list[int] = []

    @commands.slash_command(
        name="count",
        description="Shows how many records the antispam model has been trained on.",
    )
    async def count(self, inter: disnake.ApplicationCommandInteraction):
        count_total = await self.bot.db.execute(
            "SELECT COUNT(1) FROM data", fetch_mode=FetchMode.VAL
        )
        count_validated = await self.bot.db.execute(
            "SELECT COUNT(1) FROM data WHERE is_spam IS NOT NULL",
            fetch_mode=FetchMode.VAL,
        )
        await inter.send(f"**Total: {count_total}**\n**Validated: {count_validated}**")

    @commands.slash_command(
        name="validate",
        description="Special command for owner to validate all the spam samples",
        guild_ids=TRAIN_GUILD_IDS,
    )
    @commands.is_owner()
    async def validate(self, inter: disnake.ApplicationCommandInteraction):
        res = None

        try:
            while res not in (ViewResponse.EXIT, ViewResponse.TIMEOUT):
                id, rec = await self.bot.db.get_unmarked_message()
                if id is None:
                    await inter.send(
                        f"No more records to analyse left!", ephemeral=True
                    )
                    return

                view = PhraseProcessingView(inter.author.id)
                await inter.send(
                    embed=disnake.Embed(
                        title="Is this message a spam?", description=f"{rec}"
                    )
                    .add_field(
                        "AI Prediction", "YES" if is_spam(rec) else "NO", inline=False
                    )
                    .add_field("ID", str(id), inline=False),
                    view=view,
                    ephemeral=True,
                )
                res, inter = await view.get_result()
                if res == ViewResponse.YES:
                    await self.bot.db.mark_message_as_spam(id, True)

                elif res == ViewResponse.NO:
                    await self.bot.db.mark_message_as_spam(id, False)

                elif res == ViewResponse.EXIT:
                    await inter.send(f"Messages validated!", ephemeral=True)
                    break

                elif res == ViewResponse.TIMEOUT:
                    await inter.send(
                        f"{inter.author.mention} timeout exceeded", ephemeral=True
                    )
                    break
        except Exception as e:
            await inter.send(
                f"Sorry, {inter.author.mention}, something went wrong, we are already investigating",
                ephemeral=True,
            )
            raise e


def setup(bot: Bot):
    bot.auto_setup(__name__)
