from typing import Generic, TypeVar

import disnake

from ai.analyser import analyse_sample, extract_mentions
from utils.embeds import BaseEmbed, SuccessEmbed
from utils.enums import FetchMode, ViewResponse

T = TypeVar("T")


class Button(disnake.ui.Button, Generic[T]):
    def __init__(self, return_value: T = None, **kwargs):
        super().__init__(**kwargs)
        self.return_value = return_value

    async def callback(self, interaction: disnake.MessageInteraction):
        self.view: BaseView
        self.view.set_value(self.return_value, interaction)


class BaseView(disnake.ui.View, Generic[T]):
    def __init__(
        self,
        user_id: int,
        buttons: list[Button[T]],
        disable_after_interaction: bool = True,
    ):
        self.value: T = None
        self.inter: disnake.MessageInteraction = None
        self.user_id = user_id
        self.disable_after_interaction = disable_after_interaction
        super().__init__()
        for button in buttons:
            self.add_item(button)

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        if inter.author.id != self.user_id:
            await inter.send("This button is not for you :wink:", ephemeral=True)
            return False

        return True

    def set_value(self, value, inter: disnake.MessageInteraction):
        self.value = value
        self.inter = inter
        self.stop()

    async def get_result(self) -> tuple[T, disnake.MessageInteraction]:
        await self.wait()
        if self.disable_after_interaction:
            for child in self.children:
                child.disabled = True

            await self.inter.message.edit(view=self)

        return self.value, self.inter


class PhraseProcessingView(BaseView):
    def __init__(self, user_id: int):
        super().__init__(
            user_id,
            [
                Button(ViewResponse.YES, label="Yes", style=disnake.ButtonStyle.green),
                Button(ViewResponse.NO, label="No", style=disnake.ButtonStyle.red),
                Button(
                    ViewResponse.EXIT,
                    label="Exit",
                    style=disnake.ButtonStyle.blurple,
                    row=2,
                ),
            ],
            disable_after_interaction=False,
        )


class ConfirmationView(BaseView):
    def __init__(self, user_id: int):
        super().__init__(
            user_id,
            [
                Button(ViewResponse.YES, label="Yes", style=disnake.ButtonStyle.green),
                Button(ViewResponse.NO, label="No", style=disnake.ButtonStyle.red),
            ],
        )


class AntispamView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(
        label="Not Spam", custom_id="not_spam", style=disnake.ButtonStyle.red
    )
    async def not_spam(self, _, inter: disnake.MessageInteraction):
        embed = inter.message.embeds[0]
        content = None
        for proxy in embed.fields:
            if proxy.name == "Blocked Content":
                content = proxy.value
                break

        await inter.bot.log_channel.send(
            embed=BaseEmbed(
                inter,
                "Not Spam Report",
                f"Reported non spam message from {inter.guild.id}",
            ).add_field("Reported Content", content),
            view=ReportedNotSpamView(),
        )
        await inter.message.edit(view=None)
        await inter.send(
            embed=SuccessEmbed(inter, f"Your report was submitted successfully!"),
            ephemeral=True,
        )


class ReportedNotSpamView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(
        label="Overwrite",
        custom_id="antispam_overwrite",
        style=disnake.ButtonStyle.green,
    )
    async def antispam_overwrite(self, _, inter: disnake.MessageInteraction):
        embed = inter.message.embeds[0]
        content = None
        for proxy in embed.fields:
            if proxy.name == "Reported Content":
                content = proxy.value
                break

        content = extract_mentions(content[3:-3].lower())
        id = await inter.bot.db.execute(
            "SELECT id FROM data WHERE content = $1", content, fetch_mode=FetchMode.VAL
        )
        if id is None:
            data = analyse_sample(content)
            await inter.bot.db.execute(
                "INSERT INTO data (content, total_chars, unique_chars, total_words, unique_words) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                content,
                *data,
            )
        else:
            await inter.bot.db.execute(
                "UPDATE data SET is_spam = FALSE WHERE id = $1", id
            )

        await inter.message.edit(view=None)
        await inter.send(
            f"Successfully updated sample `#{id}`. Retraining required.", ephemeral=True
        )

    @disnake.ui.button(
        label="Ignore", custom_id="antispam_ignore", style=disnake.ButtonStyle.red
    )
    async def antispam_ignore(self, _, inter: disnake.MessageInteraction):
        await inter.message.edit(view=None)
        await inter.send(f"Sample ignored.", ephemeral=True)
