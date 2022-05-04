from random import randint

import disnake
from utils.bot import Bot
from utils.embeds import WarningEmbed
from utils.enums import AntiraidPunishment
from utils.utils import Queue, try_send


class AntiraidProcessor:
    bot: Bot
    data: dict[int, Queue[disnake.Member]]

    def __init__(self, bot: Bot):
        self.bot = bot
        self.data = {}

    def add(self, member: disnake.Member, limit: int):
        if not member.guild.id in self.data:
            queue = Queue([member], limit)
            self.data[member.guild.id] = queue
            return False
        else:
            queue = self.data[member.guild.id]
            if queue.max_size != limit:
                queue.max_size = limit
                queue.clear()

            # to avoid same member processing
            for m in queue:
                if m.id == member.id:
                    queue.remove(m)
                    break

            queue.add(member)
            return queue

    async def process(self, member: disnake.Member) -> int:
        guild_data = self.bot.db.get_guild(member.guild.id)
        antiraid = await guild_data.get_antiraid_data()
        if not antiraid.enabled:
            return 0

        queue = self.add(member, antiraid.members_limit)
        if queue == False:
            return 0

        if (
            len(queue) == antiraid.members_limit
            and (queue.popright().joined_at - queue.popleft().joined_at).seconds
            < antiraid.join_interval
        ):
            log = await guild_data.get_logger(self.bot)
            for member in queue:
                try:
                    if antiraid.punishment == AntiraidPunishment.BAN:
                        await try_send(
                            member,
                            embed=WarningEmbed(
                                member,
                                title="AntiRaid",
                                description=f"You were banned from {member.guild.name} because of suspect of raid. \
    If it was a mistake, staff members will unban you.",
                            ),
                        )
                        await member.ban(reason="Antiraid")
                        await log.log_antiraid_ban(member)

                    elif antiraid.punishment == AntiraidPunishment.KICK:
                        await try_send(
                            member,
                            embed=WarningEmbed(
                                member,
                                title="AntiRaid",
                                description=f"You were kicked from {member.guild.name} because of suspect of raid.",
                            ),
                        )
                        await member.kick(reason="Antiraid")
                        await log.log_antiraid_kick(member)

                    elif antiraid.punishment == AntiraidPunishment.TIMEOUT:
                        duration = randint(30, 120)
                        await try_send(
                            member,
                            embed=WarningEmbed(
                                member,
                                title="AntiRaid",
                                description=f"You were timeouted in {member.guild.name} for `{duration}` minutes because of suspect of raid. \
    If it was a mistake, staff members will untimeout you.",
                            ),
                        )
                        await member.timeout(duration=duration * 60)
                        await log.log_timeout(member, duration, True)

                except Exception as e:
                    self.bot.log.warning(
                        "Failed to ban member in %s because: %s",
                        member.guild,
                        str(e),
                    )

            amount = len(queue)
            queue.clear()
            return amount
