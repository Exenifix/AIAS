import disnake

from utils.enums import ViewResponse


class PhraseProcessingView(disnake.ui.View):
    def __init__(self, user_id: int):
        self.value = None
        self.user_id = user_id
        super().__init__()

    async def interaction_check(self, inter: disnake.MessageInteraction):
        if inter.author.id != self.user_id:
            await inter.send("This button is not for you :wink:", ephemeral=True)
            return False

        return True

    async def on_timeout(self):
        self.value = ViewResponse.TIMEOUT
        self.stop()

    @disnake.ui.button(label="Yes", style=disnake.ButtonStyle.green)
    async def yes_button(self, *_):
        self.value = ViewResponse.YES
        self.stop()

    @disnake.ui.button(label="No", style=disnake.ButtonStyle.red)
    async def no_button(self, *_):
        self.value = ViewResponse.NO
        self.stop()

    @disnake.ui.button(label="Exit", style=disnake.ButtonStyle.blurple, row=2)
    async def exit_button(self, *_):
        self.value = ViewResponse.EXIT
        self.stop()

    async def get_result(self):
        await self.wait()
        return self.value
