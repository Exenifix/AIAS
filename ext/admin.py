import disnake
from disnake.ext import commands
from utils.bot import Bot


class Administration(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ):
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
    async def admin_addmanagerrole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).add_automod_manager(role.id)
        await inter.send(
            f"{self.bot.sys_emojis.checkmark} | **Successfully added {role.mention} to the manager roles.**"
        )

    @admin_group.sub_command(
        name="addmanagermember",
        description="Adds a manager member. Managers have permissions to modify filters.",
    )
    async def admin_addmanagermember(
        self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member
    ):
        await self.bot.db.get_guild(inter.guild.id).add_automod_manager(member.id)
        await inter.send(
            f"{self.bot.sys_emojis.checkmark} | **Successfully added {member.mention} to the managers.**"
        )

    @admin_group.sub_command(
        name="removemanagerrole", description="Removes a role from managers."
    )
    async def admin_removemanagerrole(
        self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_automod_manager(role.id)
        await inter.send(
            f"{self.bot.sys_emojis.checkmark} | **Successfully removed {role.mention} from the manager roles.**"
        )

    @admin_group.sub_command(
        name="removemanagermember", description="Removes a member from managers."
    )
    async def admin_addmanagermember(
        self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member
    ):
        await self.bot.db.get_guild(inter.guild.id).remove_automod_manager(member.id)
        await inter.send(
            f"{self.bot.sys_emojis.checkmark} | **Successfully removed {member.mention} from the managers.**"
        )


def setup(bot: Bot):
    bot.add_cog(Administration(bot))
