from disnake import ApplicationCommandInteraction

from utils.bot import Bot
from utils.errors import ManagerOnly


async def is_automod_manager(bot: Bot, inter: ApplicationCommandInteraction) -> bool:
    managers = await bot.db.get_guild(inter.guild.id).get_automod_managers()
    if (
        inter.author.id in managers
        or inter.author.guild_permissions.manage_guild
        or any(r in managers for r in [role.id for role in inter.author.roles])
    ):
        return True

    raise ManagerOnly()
