import discord
import datetime
import re
import time
from urllib.parse import urlsplit, urlunsplit
from discord import app_commands
from discord.ext import commands
from gerentiu.db import (
    get_antispam_config,
    set_antispam_enabled,
    set_antispam_max_messages,
    set_antispam_interval_seconds,
    set_antispam_max_punishment,
    increment_antispam_strikes
)
from collections import defaultdict, deque

URL_RE = re.compile(
    r"(?:(?:https?://|www\.)[^\s<>()]+|(?:discord\.gg|discord(?:app)?\.com/invite)/[^\s<>()]+)",
    re.IGNORECASE
)
WHITESPACE_RE = re.compile(r"\s+")
ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"
TRAILING_URL_PUNCTUATION = ".,!?;:)]}>\"'"

class ModerationCog(commands.Cog):
    CROSS_CHANNEL_MIN_CHANNELS = 2
    MIN_DUPLICATE_TEXT_LENGTH = 12

    def __init__(self, bot: commands.Bot):
        self.message_history = defaultdict(deque)
        self.cross_channel_history = defaultdict(deque)
        self.bot = bot

# Cria a classe Moderation para montar o cog "Moderation"

    @app_commands.command(name="ping", description="Ping test for Gerentiu.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong ✅", ephemeral=True)

# Comando teste para verificar se o bot está respondendo

    @staticmethod
    def get_missing_antispam_permissions(guild: discord.Guild) -> list[str]:
        me = guild.me
        if me is None:
            return ["Could not resolve bot member."]

        perms = me.guild_permissions
        missing = []

        if not perms.manage_messages:
            missing.append("Manage Messages")

        if not perms.moderate_members:
            missing.append("Moderate Members")

        if not perms.kick_members:
            missing.append("Kick Members")

        if not perms.ban_members:
            missing.append("Ban Members")

        return missing

    antispam_group = app_commands.Group(
        name="antispam",
        description="Anti-spam configuration system."
    )

    @antispam_group.command(name="enable", description="Activates anti-spam on this server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antispam_enable(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used on servers.",
                ephemeral=True
            )
            return

        missing = self.get_missing_antispam_permissions(interaction.guild)
        if missing:
            await interaction.response.send_message(
                "Gerentiu is missing the following permissions: " + ", ".join(missing),
                ephemeral=True
            )
            return

        await set_antispam_enabled(interaction.guild.id, True)

        await interaction.response.send_message(
            "Anti-spam succesfully activated. 🛡️",
            ephemeral=True
        )

    @antispam_group.command(name="disable", description="Deactivates anti-spam on this server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antispam_disable(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used on servers.",
                ephemeral=True
            )
            return

        await set_antispam_enabled(interaction.guild.id, False)

        await interaction.response.send_message(
            "Anti-spam deactivated succesfully.",
            ephemeral=True
        )

    @antispam_group.command(name="status", description="Displays the current status of anti-spam service.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antispam_status(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used on servers.",
                ephemeral=True
            )
            return

        missing = self.get_missing_antispam_permissions(interaction.guild)
        if missing:
            await interaction.response.send_message(
                "Gerentiu is missing the following permissions: " + ", ".join(missing),
                ephemeral=True
            )
            return

        config = await get_antispam_config(interaction.guild.id)

        status_text = "ACTIVE" if config["enabled"] else "INACTIVE"

        embed = discord.Embed(
            title="Anti-Spam configuration",
            color=discord.Color.green() if config["enabled"] else discord.Color.red()
        )
        embed.add_field(name="Status", value=status_text, inline=False)
        embed.add_field(name="Max messages", value=str(config["max_messages"]), inline=True)
        embed.add_field(name="Intervals", value=str(config["interval_seconds"]), inline=True)
        embed.add_field(name="Max punishment", value=config["max_punishment"], inline=True)
        embed.add_field(
            name="Cross-channel protection",
            value="Same links and repeated messages across channels",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @antispam_enable.error
    @antispam_disable.error
    @antispam_status.error
    async def antispam_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send(
                    "You don't have permission to use this command.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "You don't have permission to use this command.",
                    ephemeral=True
                )
            return

        if interaction.response.is_done():
            await interaction.followup.send(
                f"Error upon processing command: {error}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Error upon processing command: {error}",
                ephemeral=True
            )

    @antispam_group.command(name="max_messages", description="Defines a number of messages before antispam kicks in.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def max_messages(self, interaction: discord.Interaction, value: int):
        if interaction.guild is None:
            await interaction.response.send_message(
                f"This can only be used on servers.",
                ephemeral=True
            )
            return

        missing = self.get_missing_antispam_permissions(interaction.guild)
        if missing:
            await interaction.response.send_message(
                "Gerentiu is missing the following permissions: " + ", ".join(missing),
                ephemeral=True
            )
            return

        if value < 2 or value > 20:
            await interaction.response.send_message(
                "Value must be between 2 and 20.",
                ephemeral=True
            )
            return

        await set_antispam_max_messages(interaction.guild.id, value)
        await interaction.response.send_message(
            f"Max messages set to {value}.",
            ephemeral=True
        )

    @antispam_group.command(name="interval_seconds", description="Defines the number of seconds that the messages can flood in before antispam is triggered.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def interval_seconds(self, interaction: discord.Interaction, value: int):
        if interaction.guild is None:
            await interaction.response.send_message(
                f"This can only be used on servers.",
                ephemeral=True
            )
            return

        missing = self.get_missing_antispam_permissions(interaction.guild)
        if missing:
            await interaction.response.send_message(
                "Gerentiu is missing the following permissions: " + ", ".join(missing),
                ephemeral=True
            )
            return

        if value < 5 or value > 60:
            await interaction.response.send_message(
                "Value must be between 5 and 60.",
                ephemeral=True
            )
            return

        await set_antispam_interval_seconds(interaction.guild.id, value)
        await interaction.response.send_message(
            f"Interval in seconds set to {value}.",
            ephemeral=True
        )

    @antispam_group.command(name="max", description="Defines the maximum punishment to be taken if spam is detected.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(value=[
        app_commands.Choice(name="Warn user", value="warn"),
        app_commands.Choice(name="Delete messages", value="delete"),
        app_commands.Choice(name="Timeout user", value="timeout"),
        app_commands.Choice(name="Kick user", value="kick"),
        app_commands.Choice(name="Ban user", value="ban"),
    ])
    async def max_punishment(self, interaction: discord.Interaction, value: app_commands.Choice[str]):
        if interaction.guild is None:
            await interaction.response.send_message("This can only be used on servers.", ephemeral=True)
            return
        await set_antispam_max_punishment(interaction.guild.id, value.value)

        await interaction.response.send_message(f"Maximum antispam punishment set to '{value.value}'.", ephemeral=True)

    async def apply_spam_punishment(
        self,
        member: discord.Member,
        action: str,
        spam_messages: list[discord.Message],
        channel: discord.abc.Messageable
    ):
        spam_messages = self.unique_messages(spam_messages)

        for msg in spam_messages:
            try:
                await msg.delete()
            except discord.HTTPException:
                pass

        if action == "warn":
            try:
                await channel.send(
                    f"{member.mention}, your spam messages were removed. Stop flooding the server. This is a warning.",
                    delete_after=6
                )
            except discord.HTTPException:
                pass

            try:
                await member.send("Your spam messages were removed. Stop spamming the server. This is a warning.")
            except discord.HTTPException:
                pass

        elif action == "delete":
            try:
                await channel.send(
                    f"{member.mention}, your spam messages were removed. Stop flooding the server.",
                    delete_after=6
                )
            except discord.HTTPException:
                pass

        elif action == "timeout":
            try:
                until = discord.utils.utcnow() + datetime.timedelta(minutes=10)
                await member.timeout(until, reason="Spam detected")
            except discord.HTTPException:
                pass

            try:
                await channel.send(
                    f"{member.mention}, you have been timed out for spamming.",
                    delete_after=8
                )
            except discord.HTTPException:
                pass
            try:
                await member.send("You have been timed out for spamming.")
            except discord.HTTPException:
                pass

        elif action == "kick":
            try:
                await member.send("You have been kicked for spamming.")
            except discord.HTTPException:
                pass
            try:
                await channel.send(
                    f"{member.mention} was kicked for spamming.",
                    delete_after=8
                )
            except discord.HTTPException:
                pass
            try:
                await member.kick(reason="Spam detected")
            except discord.HTTPException:
                pass

        elif action == "ban":
            try:
                await member.send("You have been banned for spamming.")
            except discord.HTTPException:
                pass
            try:
                await channel.send(
                    f"{member.mention} was banned for spamming.",
                    delete_after=8
                )
            except discord.HTTPException:
                pass
            try:
                await member.ban(reason="Spam detected", delete_message_days=0)
            except discord.HTTPException:
                pass

    PUNISHMENT_ORDER = ["warn", "delete", "timeout", "kick", "ban"]

    def resolve_spam_punishment(self, strikes: int, max_punishment: str) -> str:
        if max_punishment not in self.PUNISHMENT_ORDER:
            max_punishment = "timeout"

        max_index = self.PUNISHMENT_ORDER.index(max_punishment)
        strike_index = min(strikes - 1, max_index)
        return self.PUNISHMENT_ORDER[strike_index]

    @staticmethod
    def unique_messages(messages: list[discord.Message]) -> list[discord.Message]:
        seen = set()
        unique = []

        for message in messages:
            message_id = getattr(message, "id", None)
            message_key = message_id if message_id is not None else id(message)

            if message_key in seen:
                continue

            seen.add(message_key)
            unique.append(message)

        return unique

    @staticmethod
    def normalize_message_text(content: str) -> str:
        content = (content or "").casefold().strip()

        for char in ZERO_WIDTH_CHARS:
            content = content.replace(char, "")

        return WHITESPACE_RE.sub(" ", content)

    @classmethod
    def normalize_url(cls, raw_url: str) -> str:
        raw_url = raw_url.strip().rstrip(TRAILING_URL_PUNCTUATION)

        lowered_url = raw_url.casefold()

        if lowered_url.startswith("www."):
            raw_url = "https://" + raw_url
        elif lowered_url.startswith(("discord.gg/", "discord.com/invite/", "discordapp.com/invite/")):
            raw_url = "https://" + raw_url

        parsed = urlsplit(raw_url)
        scheme = parsed.scheme.casefold() or "https"
        netloc = parsed.netloc.casefold()
        path = parsed.path.rstrip("/")
        query = parsed.query

        return urlunsplit((scheme, netloc, path, query, ""))

    @classmethod
    def extract_urls(cls, content: str) -> list[str]:
        urls = []

        for match in URL_RE.finditer(content or ""):
            normalized = cls.normalize_url(match.group(0))
            if normalized:
                urls.append(normalized)

        return urls

    @classmethod
    def build_spam_fingerprints(cls, message: discord.Message) -> set[tuple[str, str]]:
        content = message.content or ""
        fingerprints = {
            ("url", url)
            for url in cls.extract_urls(content)
        }

        normalized_text = cls.normalize_message_text(content)
        if len(normalized_text) >= cls.MIN_DUPLICATE_TEXT_LENGTH:
            fingerprints.add(("text", normalized_text))

        return fingerprints

    @staticmethod
    def prune_history(history: deque, now: float, interval_seconds: int):
        while history and now - history[0]["created_at"] > interval_seconds:
            history.popleft()

    @staticmethod
    def cross_channel_threshold(fingerprint_type: str, max_messages: int) -> int:
        if fingerprint_type == "url":
            return max(2, min(max_messages, 3))

        return max(2, min(max_messages, 4))

    async def handle_spam_detection(
        self,
        message: discord.Message,
        spam_messages: list[discord.Message]
    ):
        guild = message.guild
        member = message.author

        if guild is None or not isinstance(member, discord.Member):
            return

        config = await get_antispam_config(guild.id)
        if config is None or not config["enabled"]:
            return

        strikes = await increment_antispam_strikes(guild.id, member.id)
        action = self.resolve_spam_punishment(strikes, config["max_punishment"])

        await self.apply_spam_punishment(member, action, spam_messages, message.channel)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        if message.author.bot:
            return

        config = await get_antispam_config(message.guild.id)
        if config is None or not config["enabled"]:
            return

        is_spam, spam_messages = self.check_spam(
            message,
            config["max_messages"],
            config["interval_seconds"]
        )

        if not is_spam:
            return

        await self.handle_spam_detection(message, spam_messages)

    def check_spam(self, message: discord.Message, max_messages: int, interval_seconds: int):
        channel_spam, channel_messages = self.check_channel_spam(
            message,
            max_messages,
            interval_seconds
        )
        cross_channel_spam, cross_channel_messages = self.check_cross_channel_spam(
            message,
            max_messages,
            interval_seconds
        )

        if cross_channel_spam:
            return True, cross_channel_messages

        if channel_spam:
            self.cross_channel_history.pop((message.guild.id, message.author.id), None)
            return True, channel_messages

        return False, []

    def check_channel_spam(self, message: discord.Message, max_messages: int, interval_seconds: int):
        key = (message.guild.id, message.author.id, message.channel.id)
        now = time.time()

        history = self.message_history[key]
        history.append({
            "created_at": now,
            "message": message,
        })

        self.prune_history(history, now, interval_seconds)

        if len(history) >= max_messages:
            spam_messages = [entry["message"] for entry in history]
            history.clear()
            return True, spam_messages

        return False, []

    def check_cross_channel_spam(self, message: discord.Message, max_messages: int, interval_seconds: int):
        fingerprints = self.build_spam_fingerprints(message)
        if not fingerprints:
            return False, []

        key = (message.guild.id, message.author.id)
        now = time.time()
        history = self.cross_channel_history[key]

        history.append({
            "created_at": now,
            "channel_id": message.channel.id,
            "message": message,
            "fingerprints": fingerprints,
        })

        self.prune_history(history, now, interval_seconds)

        for fingerprint in fingerprints:
            matches = [
                entry
                for entry in history
                if fingerprint in entry["fingerprints"]
            ]
            unique_channel_ids = {
                entry["channel_id"]
                for entry in matches
            }
            threshold = self.cross_channel_threshold(fingerprint[0], max_messages)

            if (
                len(matches) >= threshold
                and len(unique_channel_ids) >= self.CROSS_CHANNEL_MIN_CHANNELS
            ):
                spam_messages = [
                    entry["message"]
                    for entry in matches
                ]
                history.clear()
                return True, spam_messages

        return False, []



async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))

# Inicializa o cog de Moderation
