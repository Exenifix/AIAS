from datetime import datetime
from typing import Union

import disnake
from disnake.ext import commands

Contextable = Union[disnake.Interaction, commands.Context, disnake.Message]
COLOR = 0x05FFC5


class Emojis:
    checkmark: disnake.Emoji
    exclamation: disnake.Emoji
    warning: disnake.Emoji


emojis = Emojis()


def init(emj: Emojis):
    global emojis
    emojis = emj


class BaseEmbed(disnake.Embed):
    def __init__(
            self,
            ctx: Contextable | disnake.Member | disnake.User,
            title: str,
            description: str,
    ):
        super().__init__(
            color=COLOR, title=title, description=description, timestamp=datetime.now()
        )
        if isinstance(ctx, (disnake.Member, disnake.User)):
            self.set_footer(text=ctx, icon_url=ctx.display_avatar.url)
        else:
            self.set_footer(
                text=str(ctx.author), icon_url=ctx.author.display_avatar.url
            )


class SuccessEmbed(BaseEmbed):
    def __init__(self, ctx: Contextable, description: str, disable_bold: bool = False):
        text = f"**{description}**" if not disable_bold else description
        super().__init__(ctx, f"{emojis.checkmark} Success", text)


class WarningEmbed(BaseEmbed):
    def __init__(self, ctx: Contextable, *, title: str = "Warning", description: str):
        super().__init__(ctx, f"{emojis.warning} {title}", description)


class ErrorEmbed(BaseEmbed):
    def __init__(self, ctx: Contextable, description: str):
        super().__init__(ctx, f"{emojis.exclamation} Error Occurred", description)
