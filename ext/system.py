import disnake
from disnake.ext import commands
from utils.bot import Bot
from utils.errors import get_error_message, UNKNOWN


class SystemListeners(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_slash_command_error(
        self, inter: disnake.Interaction, error: commands.CommandError
    ):
        msg = get_error_message(inter, error)

        if msg is UNKNOWN:
            await inter.send(f"Unknown error occured: {error}")
            raise error

        await inter.send(f"Sorry, an error occured\n```py\n{msg}```")


def setup(bot: Bot):
    bot.add_cog(SystemListeners(bot))
