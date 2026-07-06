import discord
from discord import app_commands
from discord.ext import commands


HELP_DATA = {
    "configuration": {
        "panel":
            """ Type `/config` to open Gerentiu's interactive configuration panel.
            It lets you configure AntiSpam, AntiRaid and Translation Hubs using menus,
            buttons and forms instead of remembering every single command like some
            kind of terminal wizard. The panel also has its own Help option for quick
            explanations before you touch the dangerous-looking buttons. For channels,
            hubs, languages and common numeric settings, prefer the panel selectors
            instead of typing IDs or values by hand.
        """,
        "permissions":
            """The configuration panel requires Manage Server permission. If you can
            open it, you can configure the server. If you can't, ask an admin, or
            become one through legitimate and definitely not suspicious means.
        """
    },
    "translation": {
        "config": (
            """ Type `/hub_create` on any text channel on your server, then type the name of the translation
            hub you want to create, it will have an ID number, save it for future use. You can use the command
            `/hub_list` to see which translation hubs you have on your server and their respective ID number.
            Now, you can add a text channel to your translation hub using `/hub_add`, you will need to set
            the ID number of the hub to add your text channel and the language in which the text channel is
            being used.
        """
        ),
        "works": (
            """
            Gerentiu gets the message sent on a text channel and verifies if it's on a
            translation hub, if it's not, he just throws it away (No messages are saved!
            Privacy!). If it is, then he translates it using ArgosTranslate and does some
            Webhook magic (Uuuhh) and sends it as if it is the message author, with profile
            picture and name! He mirrors images, emojis, gifs and other stuff aswell. Fantastic
        """
        ),
        "remove":
             """Type `/hub_remove` in any text channel on your Discord server and choose the
             text channel you wish to remove from a certain hub. If you want to delete the entire
             hub and all channel routes inside it, use `/hub_delete`. That one is the big broom.
             """
    },
    "antispam": {
        "config": "Type `/antispam enable` on any text channel to enable the antispam system on your server.",
        "works":
            """ The AntiSpam system works by verifying if a server has antispam enabled, then it
            detects how many messages are being sent by each user in an interval of time. Depending
            on the Max Messages per Interval of Seconds and Maximum Punishment, it can Warn, Delete
            the Spam messages, Timeout, Kick or Ban the Spammer. It also checks if the same message
            or the same suspicious link is being thrown into multiple channels at the same time, because
            apparently some people wake up and choose chaos.
        """,
        "remove": "Type `/antispam disable` on any text channel to disable the antispam system on your server.",
        "max_punishment":
            """Type `/antispam max` and choose the maximum punishment you wish to apply on spammers on your
            server.
        """,
        "interval_of_seconds":
            """🕚 Type `/antispam interval_seconds` on any text channel to define an interval in seconds for
            the system to detect spam messages.
        """,
        "max_messages":
            """⚠️  Type `/antispam max_messages` on any text channel to define the number of messages before antispam kicks in.
        """
    },
    "antiraid": {
        "config":
            """ Type `/config` and choose `Anti-Raid`, or type `/antiraid enable` on any text channel to enable the anti-raid system on your
            server. Use `/antiraid alert_channel` to choose where Gerentiu will scream if too many
            people decide to enter your server at the same time. Lovely, isn't it?
        """,
        "works":
            """ The AntiRaid system watches how many people join your server in a short interval of time.
            It also checks if most of those accounts are suspiciously new and if recently joined users
            start sending links, invites or weird messages too fast. If the score gets ugly, Gerentiu
            alerts the staff. If it gets REALLY ugly, Gerentiu can lock text channels for a while so
            the raid loses its toys.
        """,
        "action":
            """Use `/antiraid action` to choose what Gerentiu should do when a raid is confirmed.
            You can choose `alert` if you only want warnings, or `lockdown` if you want him to close
            text channels until the configured timer runs out.
        """,
        "tuning":
            """Use `/antiraid join_threshold` to define how many joins are too many, and
            `/antiraid join_window` to define the time window in seconds. You can also use
            `/antiraid new_account_days` and `/antiraid new_account_ratio` to tell Gerentiu how
            paranoid he should be with brand new accounts.
        """,
        "alerts":
            """Use `/antiraid alert_channel` to define where raid alerts will be posted. Use
            `/antiraid status` to see if the system is active, what action is configured, how many
            channels are locked and what the current raid state looks like.
        """,
        "lockdown":
            """Use `/antiraid lockdown_duration` to define how long the channels will stay locked
            when Gerentiu confirms a raid. He saves the previous channel permissions before touching
            anything, because breaking your server permanently would be rude.
        """,
        "unlock":
            """Use `/antiraid unlock` to manually restore channels locked by the anti-raid system.
            You can also type `/antiraid disable` to turn the system off and restore locked channels
            at the same time. Emergency button. Big red energy.
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
