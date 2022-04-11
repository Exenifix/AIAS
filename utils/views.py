from typing import Any
import disnake

from utils.enums import ViewResponse


class Button(disnake.ui.Button):
    def __init__(self, return_value=None, **kwargs):
        super().__init__(**kwargs)
        self.return_value = return_value

    async def callback(self, interaction: disnake.MessageInteraction):
        self.view: BaseView
        self.view.set_value(self.return_value, interaction)


class BaseView(disnake.ui.View):
    def __init__(self, user_id: int, buttons: list[Button]):
        self.value = None
        self.inter: disnake.MessageInteraction = None
        self.user_id = user_id
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

    async def get_result(self) -> tuple[Any, disnake.MessageInteraction]:
        await self.wait()
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
        )
