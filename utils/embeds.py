from datetime import datetime

import disnake
from disnake.ext import commands

COLOR = 0x05FFC5


class BaseEmbed(disnake.Embed):
    def __init__(
        self,
        ctx: commands.Context | disnake.Interaction | disnake.Message,
        title: str,
        description: str,
    ):
        super().__init__(
            color=COLOR, title=title, description=description, timestamp=datetime.now()
        )
        self.set_footer(text=str(ctx.author), icon_url=ctx.author.display_avatar.url)
