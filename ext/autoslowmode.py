from datetime import datetime, timedelta

import disnake
from disnake.ext import commands

from utils.bot import Bot
from utils.checks import is_automod_manager
from utils.constants import AUTOSLOWMODE_EDIT_DELAY
from utils.embeds import BaseEmbed, ErrorEmbed, SuccessEmbed
from utils.utils import Queue


class Autoslowmode(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.cached_autoslowmode_channels: set[int] = set()
        self._cache_loaded = False
        self._slowmode_cooldowns: dict[int, datetime] = {}

        self.asm_data: dict[int, Queue[disnake.Message]] = {}

    async def cog_slash_command_check(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> bool:
        return await is_automod_manager(self.bot, inter)

    async def is_channel_autoslowmode(self, channel: disnake.TextChannel) -> bool:
        if not self._cache_loaded:
            self.cached_autoslowmode_channels = set(
                await self.bot.db.get_autoslowmode_channels()
            )
            self._cache_loaded = True

        return channel.id in self.cached_autoslowmode_channels

    def add_to_data(self, message: disnake.Message) -> Queue[disnake.Message]:
        if message.channel.id not in self.asm_data:
            q = Queue([message], max_size=10)
            self.asm_data[message.channel.id] = q
        else:
            q = self.asm_data[message.channel.id]
            q.add(message)

        return q

    @commands.Cog.listener("on_message")
    async def autoslowmode_controller(self, message: disnake.Message):
        if not await self.is_channel_autoslowmode(message.channel):
            return

        queue = self.add_to_data(message)
        if (
            len(queue) < 10
            or message.channel.id not in self._slowmode_cooldowns
            or datetime.now() > self._slowmode_cooldowns[message.channel.id]
        ):
            return

        try:
            new_slowmode = int(
                30 / (queue.getright().created_at - queue.getleft().created_at).seconds
            )
            if abs(new_slowmode - message.channel.slowmode_delay) >= 5:
                await message.channel.edit(
                    slowmode_delay=new_slowmode,
                    reason="Autoslowmode",
                )
                self._slowmode_cooldowns[
                    message.channel.id
                ] = datetime.now() + timedelta(seconds=AUTOSLOWMODE_EDIT_DELAY)
                await message.channel.send(
                    embed=BaseEmbed(
                        message.guild.me,
                        "Autoslowmode",
                        f"Slowmode in this channel was set to **{new_slowmode}s**.",
                    ),
                    delete_after=3,
                )

        except disnake.HTTPException:
            self.bot.log.warning("Failed to update slowmode in %s", message.channel.id)

    @commands.slash_command(name="autoslowmode")
    async def autoslowmode(self, _):
        pass

    @autoslowmode.sub_command(
        name="addchannel", description="Registers a channel for autoslowmode tracking."
    )
    async def asm_addchannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        if not channel.permissions_for(inter.guild.me).manage_channels:
            await inter.send(
                embed=ErrorEmbed(
                    inter,
                    "Sorry, but I need a permission to manage that channel to apply autoslowmode!",
                ),
                ephemeral=True,
            )
            return

        await self.bot.db.add_autoslowmode_channel(channel)
        self.cached_autoslowmode_channels.add(channel.id)
        await inter.send(
            embed=SuccessEmbed(
                inter, f"Successfully added {channel.mention} to autoslowmode channels."
            )
        )

    @autoslowmode.sub_command(
        name="removechannel", description="Removes autoslowmode from a channel."
    )
    async def asm_removechannel(
        self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel
    ):
        await self.bot.db.remove_autoslowmode_channel(channel.id)
        try:
            self.cached_autoslowmode_channels.remove(channel.id)
        except KeyError:
            pass

        await inter.send(
            embed=SuccessEmbed(
                inter, f"Successfully removed autoslowmode from {channel.mention}!"
            )
        )


def setup(bot: Bot):
    bot.auto_setup(__name__)
