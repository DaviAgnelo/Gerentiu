import discord
from discord import app_commands
from discord.ext import commands


HELP_DATA = {
    "translation": {
        "config": (
            """ Type `/tr_add` in any text channel on your Discord server and choose the
            channels you want to mirror, then choose the language you want for each
            channel in a list.
        """
        ),
        "works": (
            """
            Gerentiu gets the message sent on a text channel and verifies if it's on a
            translation pair, if it's not, he just throws it away (No messages are saved!
            Privacy!). If it is, then he translates it using ArgosTranslate and does some
            Webhook magic (Uuuhh) and sends it as if it is the message author, with profile
            picture and name! He mirrors images, emojis, gifs and other stuff aswell. Fantastic
        """
        ),
        "remove":
             """Type `/tr_remove` in any text channel on your Discord server and choose the
             pair of channels you wish to remove.
             """
    },
    "antispam": {
        "config": "Type `/antispam_enable` on any text channel to enable the antispam system on your server.",
        "works":
            """ The AntiSpam system work by veryfying if a server has antispam enabled, then it
            detects how many messages are being sent by each user in an interval of time. Depending
            on the Max Messages per Interval of Seconds and Maximum Punishment, it can Warn, Delete
            the Spam messages, Timeout, Kick or Ban the Spammer
        """,
        "remove": "Type `/antipam_disable` on any text channel to disable the antispam system on your server.",
        "max_punishment":
            """Type '/antispam max' and choose the maximum punishment you wish to apply on spammers on your
            server.
        """,
        "interval_of_seconds":
            """🕚 Type 'antispam interval_seconds' on any text channel to define an interval in seconds for
            the system to detect spam messages.
        """,
        "max_messages":
            """⚠️  Type 'antispam max_messages' on any text channel to define the number of messages before antispam kicks in.
        """
    }
}


def pretty_name(text: str) -> str:
    return text.replace("_", " ").title()


class MainSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=pretty_name(category), value=category)
            for category in HELP_DATA.keys()
        ]

        super().__init__(
            placeholder="Choose a system...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        view = SubView(category)

        await interaction.response.edit_message(
            content=f"Selected: **{pretty_name(category)}**\nNow choose an option:",
            embed=None,
            view=view
        )


class SubSelect(discord.ui.Select):
    def __init__(self, category: str):
        self.category = category

        options = [
            discord.SelectOption(label=pretty_name(action), value=action)
            for action in HELP_DATA[category].keys()
        ]

        super().__init__(
            placeholder="Choose an option...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        text = HELP_DATA[self.category][action]

        embed = discord.Embed(
            title=f"{pretty_name(self.category)} • {pretty_name(action)}",
            description=text,
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=None
        )


class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(MainSelect())


class SubView(discord.ui.View):
    def __init__(self, category: str):
        super().__init__(timeout=120)
        self.add_item(SubSelect(category))


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show help for Gerentiu systems.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            content="Choose a system:",
            view=MainView(),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
