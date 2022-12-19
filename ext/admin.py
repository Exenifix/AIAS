import disnake
from disnake.ext import commands

from utils.bot import Bot
from utils.embeds import ErrorEmbed, SuccessEmbed


class Administration(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction):
        if inter.author.guild_permissions.manage_guild:
            return True

        raise commands.MissingPermissions(["manage_guild"])

    @commands.slash_command(name="admin")
    async def admin_group(self, *_):
        pass

    @admin_group.sub_command(
        name="addmanagerrole",
        description="Adds a manager role. Managers have permissions to modify filters.",
    )
    async def admin_addmanagerrole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).add_automod_manager(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Successfully added {role.mention} to the manager roles."))

    @admin_group.sub_command(
        name="addmanagermember",
        description="Adds a manager member. Managers have permissions to modify filters.",
    )
    async def admin_addmanagermember(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        await self.bot.db.get_guild(inter.guild.id).add_automod_manager(member.id)
        await inter.send(embed=SuccessEmbed(inter, f"Successfully added {member.mention} to the managers."))

    @admin_group.sub_command(name="removemanagerrole", description="Removes a role from managers.")
    async def admin_removemanagerrole(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        await self.bot.db.get_guild(inter.guild.id).remove_automod_manager(role.id)
        await inter.send(embed=SuccessEmbed(inter, f"Successfully removed {role.mention} from the manager roles."))

    @admin_group.sub_command(name="removemanagermember", description="Removes a member from managers.")
    async def admin_removemanagermember(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        await self.bot.db.get_guild(inter.guild.id).remove_automod_manager(member.id)
        await inter.send(embed=SuccessEmbed(inter, f"Successfully removed {member.mention} from the managers."))

    @admin_group.sub_command(name="setlogchannel", description="Sets a channel for logs.")
    async def setlogchannel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        if not channel.permissions_for(inter.me).send_messages:
            await inter.send(embed=ErrorEmbed(inter, "I am not able to send messages in that channel."))
            return

        await self.bot.db.get_guild(inter.guild.id).set_log_channel_id(channel.id)
        await inter.send(embed=SuccessEmbed(inter, f"Successfully set the log channel to {channel.mention}."))

    @admin_group.sub_command(name="disablelog", description="Disables the logging for this guild.")
    async def disablelog(self, inter: disnake.ApplicationCommandInteraction):
        await self.bot.db.get_guild(inter.guild.id).set_log_channel_id(None)
        await inter.send(embed=SuccessEmbed(inter, "Successfully disabled logging in this server."))


def setup(bot: Bot):
    bot.auto_setup(__name__)
