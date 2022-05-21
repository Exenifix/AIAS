import disnake
from disnake.ext import commands

from ai.predictor import is_spam
from utils.bot import Bot
from utils.constants import TRAIN_GUILD_IDS
from utils.embeds import SuccessEmbed
from utils.enums import ViewResponse
from utils.views import PhraseProcessingView


class Training(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.active_sessions: list[int] = []

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
                content = await self.bot.db.get_unmarked_message()
                if content is None:
                    await inter.send(
                        f"No more records to analyse left!", ephemeral=True
                    )
                    return

                view = PhraseProcessingView(inter.author.id)
                await inter.send(
                    embed=disnake.Embed(
                        title="Is this message a spam?", description=f"{content}"
                    ).add_field(
                        "AI Prediction",
                        "YES" if is_spam(content) else "NO",
                        inline=False,
                    ),
                    view=view,
                    ephemeral=True,
                )
                res, inter = await view.get_result()
                if res == ViewResponse.YES:
                    await self.bot.db.mark_message_as_spam(content, True)

                elif res == ViewResponse.NO:
                    await self.bot.db.mark_message_as_spam(content, False)

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

    @commands.slash_command(
        name="overwrite",
        description="Overwrites a message for AI model.",
        guild_ids=TRAIN_GUILD_IDS,
    )
    @commands.is_owner()
    async def overwrite(
        self, inter: disnake.ApplicationCommandInteraction, content: str, spam: bool
    ):
        await self.bot.db.update_sample(content, spam)
        await inter.send(
            embed=SuccessEmbed(inter, "Successfully overwrote this sample!")
        )


def setup(bot: Bot):
    bot.auto_setup(__name__)
