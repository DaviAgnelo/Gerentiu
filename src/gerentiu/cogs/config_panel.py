import discord
from discord import app_commands
from discord.ext import commands

from gerentiu.cogs.translation_hubs import LANG_NAMES
from gerentiu.db import (
    add_channel_to_hub,
    create_translation_hub,
    delete_translation_hub,
    get_antiraid_config,
    get_antispam_config,
    list_antiraid_lockdown_channels,
    list_translation_hubs,
    remove_channel_from_hub,
    set_antiraid_action,
    set_antiraid_alert_channel,
    set_antiraid_enabled,
    set_antiraid_join_threshold,
    set_antiraid_join_window_seconds,
    set_antiraid_lockdown_duration_seconds,
    set_antiraid_new_account_max_age_days,
    set_antiraid_new_account_ratio_threshold,
    set_antispam_enabled,
    set_antispam_interval_seconds,
    set_antispam_max_messages,
    set_antispam_max_punishment,
)


PUNISHMENT_CHOICES = ["warn", "delete", "timeout", "kick", "ban"]
ANTIRAID_ACTION_CHOICES = ["alert", "lockdown"]


def invalidate_translation_cache(bot: commands.Bot, guild_id: int):
    listener = bot.get_cog("TranslationListenerCog")
    if listener is not None:
        listener.invalidate_translation_hub_cache(guild_id)


def short_text(value: str, limit: int) -> str:
    value = str(value)
    if len(value) <= limit:
        return value

    return value[: limit - 1] + "..."


def channel_label(guild: discord.Guild, channel_id: int) -> str:
    channel = guild.get_channel(channel_id)
    if channel is None:
        return f"#{channel_id}"

    return f"#{channel.name}"


def selected_text_channel(
    guild: discord.Guild | None,
    selected: object,
) -> discord.TextChannel | None:
    """Resolve ChannelSelect values returned as channels or app-command models."""
    if guild is None:
        return None

    channel_id = getattr(selected, "id", None)
    channel = guild.get_channel(channel_id) if channel_id is not None else None
    if isinstance(channel, discord.TextChannel):
        return channel

    if isinstance(selected, discord.TextChannel):
        return selected

    return None


def hub_options(hubs: list[dict]) -> list[discord.SelectOption]:
    options = []
    for hub in hubs[:25]:
        channel_count = len(hub["channels"])
        options.append(
            discord.SelectOption(
                label=short_text(hub["hub_name"], 80),
                value=str(hub["hub_id"]),
                description=f"{channel_count} configured channel(s)",
            )
        )

    return options


def language_options() -> list[discord.SelectOption]:
    return [
        discord.SelectOption(label=name, value=code, description=code)
        for code, name in LANG_NAMES.items()
    ]


def configured_channel_options(guild: discord.Guild, hub: dict) -> list[discord.SelectOption]:
    options = []
    for channel in hub["channels"][:25]:
        language = LANG_NAMES.get(channel["language"], channel["language"])
        options.append(
            discord.SelectOption(
                label=short_text(channel_label(guild, channel["channel_id"]), 80),
                value=str(channel["channel_id"]),
                description=short_text(language, 100),
            )
        )

    return options


class AdminConfigView(discord.ui.View):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.author_id = author_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This configuration panel belongs to another administrator.",
                ephemeral=True,
            )
            return False

        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This panel can only be used in the server where it was opened.",
                ephemeral=True,
            )
            return False

        perms = interaction.user.guild_permissions  # type: ignore
        if not perms.manage_guild:
            await interaction.response.send_message(
                "You need Manage Server permission to use this panel.",
                ephemeral=True,
            )
            return False

        return True


class BackToMainButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = MainConfigView(self.view.cog, self.view.author_id, self.view.guild_id)  # type: ignore
        await interaction.response.edit_message(
            embed=self.view.cog.build_main_embed(),  # type: ignore
            view=view,
        )


class BackToAntiSpamButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = AntiSpamConfigView(self.view.cog, self.view.author_id, self.view.guild_id)  # type: ignore
        await interaction.response.edit_message(
            embed=await self.view.cog.build_antispam_embed(interaction.guild),  # type: ignore
            view=view,
        )


class BackToAntiRaidButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = AntiRaidConfigView(self.view.cog, self.view.author_id, self.view.guild_id)  # type: ignore
        await interaction.response.edit_message(
            embed=await self.view.cog.build_antiraid_embed(interaction.guild),  # type: ignore
            view=view,
        )


class BackToTranslationButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = TranslationHubConfigView(self.view.cog, self.view.author_id, self.view.guild_id)  # type: ignore
        await interaction.response.edit_message(
            embed=await self.view.cog.build_translation_embed(interaction.guild),  # type: ignore
            view=view,
        )


class MainConfigView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(SystemSelect())


class SystemSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Anti-Spam",
                value="antispam",
                description="Enable, disable and tune spam punishment.",
            ),
            discord.SelectOption(
                label="Anti-Raid",
                value="antiraid",
                description="Configure join detection, alerts and lockdown.",
            ),
            discord.SelectOption(
                label="Translation Hubs",
                value="translation",
                description="Create hubs and connect translated channels.",
            ),
            discord.SelectOption(
                label="Help",
                value="help",
                description="Explain what each panel option does.",
            ),
        ]
        super().__init__(
            placeholder="Choose what you want to configure...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AdminConfigView = self.view  # type: ignore

        if self.values[0] == "antispam":
            embed = await view.cog.build_antispam_embed(interaction.guild)
            next_view = AntiSpamConfigView(view.cog, view.author_id, view.guild_id)
        elif self.values[0] == "antiraid":
            embed = await view.cog.build_antiraid_embed(interaction.guild)
            next_view = AntiRaidConfigView(view.cog, view.author_id, view.guild_id)
        elif self.values[0] == "translation":
            embed = await view.cog.build_translation_embed(interaction.guild)
            next_view = TranslationHubConfigView(view.cog, view.author_id, view.guild_id)
        else:
            embed = view.cog.build_config_help_embed()
            next_view = ConfigHelpView(view.cog, view.author_id, view.guild_id)

        await interaction.response.edit_message(embed=embed, view=next_view)


class ConfigHelpView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(BackToMainButton())


class IntegerSettingModal(discord.ui.Modal):
    def __init__(
        self,
        title: str,
        label: str,
        min_value: int,
        max_value: int,
        setter,
        success_message: str,
        transform=None,
    ):
        super().__init__(title=title)
        self.min_value = min_value
        self.max_value = max_value
        self.setter = setter
        self.success_message = success_message
        self.transform = transform or (lambda value: value)
        self.value_input = discord.ui.TextInput(
            label=label,
            placeholder=f"{min_value} - {max_value}",
            required=True,
            max_length=10,
        )
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        try:
            value = int(str(self.value_input.value).strip())
        except ValueError:
            return await interaction.response.send_message("Type a valid number.", ephemeral=True)

        if value < self.min_value or value > self.max_value:
            return await interaction.response.send_message(
                f"Value must be between {self.min_value} and {self.max_value}.",
                ephemeral=True,
            )

        await self.setter(interaction.guild.id, self.transform(value))
        await interaction.response.send_message(
            self.success_message.format(value=value),
            ephemeral=True,
        )


class PresetValueView(AdminConfigView):
    def __init__(
        self,
        cog: "ConfigPanelCog",
        author_id: int,
        guild_id: int,
        *,
        title: str,
        description: str,
        options: list[tuple[str, int, str]],
        setter,
        success_message: str,
        min_value: int,
        max_value: int,
        custom_label: str,
        return_target: str,
        transform=None,
    ):
        super().__init__(cog, author_id, guild_id)
        self.title = title
        self.description = description
        self.options = options
        self.setter = setter
        self.success_message = success_message
        self.min_value = min_value
        self.max_value = max_value
        self.custom_label = custom_label
        self.return_target = return_target
        self.transform = transform or (lambda value: value)
        self.add_item(PresetValueSelect(options))
        self.add_item(CustomValueButton(row=1))
        if return_target == "antispam":
            self.add_item(BackToAntiSpamButton(row=1))
        else:
            self.add_item(BackToAntiRaidButton(row=1))

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Custom",
            value=f"Use Custom value only if none of the presets fit. Range: {self.min_value}-{self.max_value}.",
            inline=False,
        )
        return embed

    async def return_to_config(self, interaction: discord.Interaction, raw_value: int):
        await self.setter(interaction.guild.id, self.transform(raw_value))

        if self.return_target == "antispam":
            embed = await self.cog.build_antispam_embed(interaction.guild)
            next_view = AntiSpamConfigView(self.cog, self.author_id, self.guild_id)
        else:
            embed = await self.cog.build_antiraid_embed(interaction.guild)
            next_view = AntiRaidConfigView(self.cog, self.author_id, self.guild_id)

        embed.add_field(name="Updated", value=self.success_message.format(value=raw_value), inline=False)
        await interaction.response.edit_message(embed=embed, view=next_view)


class PresetValueSelect(discord.ui.Select):
    def __init__(self, options: list[tuple[str, int, str]]):
        super().__init__(
            placeholder="Choose a preset...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=label, value=str(value), description=description)
                for label, value, description in options
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view: PresetValueView = self.view  # type: ignore
        await view.return_to_config(interaction, int(self.values[0]))


class CustomValueButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Custom value", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view: PresetValueView = self.view  # type: ignore
        await interaction.response.send_modal(
            IntegerSettingModal(
                view.title,
                view.custom_label,
                view.min_value,
                view.max_value,
                view.setter,
                view.success_message,
                transform=view.transform,
            )
        )


class AntiSpamConfigView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(AntiSpamSettingsSelect())
        self.add_item(BackToMainButton())

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await get_antispam_config(interaction.guild.id)
        moderation_cog = interaction.client.get_cog("ModerationCog")
        if moderation_cog is None:
            return await interaction.response.send_message(
                "Anti-spam cog is not loaded.",
                ephemeral=True,
            )

        missing = moderation_cog.get_missing_antispam_permissions(
            interaction.guild,
            config["max_punishment"],
        )
        if missing:
            return await interaction.response.send_message(
                "Gerentiu is missing the permissions required by this configuration: "
                + ", ".join(missing),
                ephemeral=True,
            )

        await set_antispam_enabled(interaction.guild.id, True)
        await interaction.response.edit_message(
            embed=await self.cog.build_antispam_embed(interaction.guild),
            view=AntiSpamConfigView(self.cog, self.author_id, self.guild_id),
        )

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await set_antispam_enabled(interaction.guild.id, False)
        await interaction.response.edit_message(
            embed=await self.cog.build_antispam_embed(interaction.guild),
            view=AntiSpamConfigView(self.cog, self.author_id, self.guild_id),
        )


class AntiSpamSettingsSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Max messages", value="max_messages"),
            discord.SelectOption(label="Interval seconds", value="interval_seconds"),
            discord.SelectOption(label="Max punishment", value="max_punishment"),
        ]
        super().__init__(
            placeholder="Choose an anti-spam setting...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AntiSpamConfigView = self.view  # type: ignore
        value = self.values[0]

        if value == "max_messages":
            next_view = PresetValueView(
                view.cog,
                view.author_id,
                view.guild_id,
                title="Anti-Spam max messages",
                description="Choose how many messages a user can send before spam detection reacts.",
                options=[
                    ("Strict - 3 messages", 3, "Fast reaction"),
                    ("Balanced - 5 messages", 5, "Recommended default"),
                    ("Relaxed - 8 messages", 8, "Busy chats"),
                    ("High traffic - 12 messages", 12, "Large active servers"),
                ],
                setter=set_antispam_max_messages,
                success_message="Max messages set to {value}.",
                min_value=2,
                max_value=20,
                custom_label="Messages before antispam kicks in",
                return_target="antispam",
            )
            return await interaction.response.edit_message(embed=next_view.build_embed(), view=next_view)

        if value == "interval_seconds":
            next_view = PresetValueView(
                view.cog,
                view.author_id,
                view.guild_id,
                title="Anti-Spam interval",
                description="Choose the time window used to count repeated messages.",
                options=[
                    ("5 seconds", 5, "Very strict"),
                    ("8 seconds", 8, "Recommended default"),
                    ("15 seconds", 15, "Moderate"),
                    ("30 seconds", 30, "Relaxed"),
                    ("60 seconds", 60, "Very relaxed"),
                ],
                setter=set_antispam_interval_seconds,
                success_message="Interval set to {value}s.",
                min_value=5,
                max_value=60,
                custom_label="Detection interval in seconds",
                return_target="antispam",
            )
            return await interaction.response.edit_message(embed=next_view.build_embed(), view=next_view)

        next_view = AntiSpamPunishmentView(view.cog, view.author_id, view.guild_id)
        await interaction.response.edit_message(
            embed=await view.cog.build_antispam_embed(interaction.guild),
            view=next_view,
        )


class AntiSpamPunishmentView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(AntiSpamPunishmentSelect())
        self.add_item(BackToMainButton())


class AntiSpamPunishmentSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=choice.title(), value=choice)
            for choice in PUNISHMENT_CHOICES
        ]
        super().__init__(
            placeholder="Choose maximum punishment...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AntiSpamPunishmentView = self.view  # type: ignore
        moderation_cog = interaction.client.get_cog("ModerationCog")
        if moderation_cog is None:
            return await interaction.response.send_message(
                "Anti-spam cog is not loaded.",
                ephemeral=True,
            )

        missing = moderation_cog.get_missing_antispam_permissions(
            interaction.guild,
            self.values[0],
        )
        if missing:
            return await interaction.response.send_message(
                "Gerentiu is missing the permissions required for that punishment: "
                + ", ".join(missing),
                ephemeral=True,
            )

        await set_antispam_max_punishment(interaction.guild.id, self.values[0])
        await interaction.response.edit_message(
            embed=await view.cog.build_antispam_embed(interaction.guild),
            view=AntiSpamConfigView(view.cog, view.author_id, view.guild_id),
        )


class AntiRaidConfigView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(AntiRaidSettingsSelect())
        self.add_item(BackToMainButton())

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await get_antiraid_config(interaction.guild.id)
        antiraid_cog = interaction.client.get_cog("AntiRaidCog")
        if antiraid_cog is None:
            return await interaction.response.send_message(
                "Anti-raid cog is not loaded.",
                ephemeral=True,
            )

        missing = antiraid_cog.get_missing_antiraid_permissions(
            interaction.guild,
            config["action"],
        )
        if missing:
            return await interaction.response.send_message(
                "Gerentiu is missing the permissions required by this configuration: "
                + ", ".join(missing),
                ephemeral=True,
            )

        await set_antiraid_enabled(interaction.guild.id, True)
        antiraid_cog.detector.reset_guild(interaction.guild.id)

        await interaction.response.edit_message(
            embed=await self.cog.build_antiraid_embed(interaction.guild),
            view=AntiRaidConfigView(self.cog, self.author_id, self.guild_id),
        )

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await set_antiraid_enabled(interaction.guild.id, False)

        restored = 0
        failed = 0
        antiraid_cog = interaction.client.get_cog("AntiRaidCog")
        if antiraid_cog is not None:
            antiraid_cog.detector.reset_guild(interaction.guild.id)
            restored, failed = await antiraid_cog.restore_lockdown(
                interaction.guild,
                "Anti-raid disabled from config panel",
            )

        await interaction.followup.send(
            f"Anti-raid disabled. Restored channels: {restored}. Failed restores: {failed}.",
            ephemeral=True,
        )

    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.primary)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        antiraid_cog = interaction.client.get_cog("AntiRaidCog")
        if antiraid_cog is None:
            return await interaction.followup.send("Anti-raid cog is not loaded.", ephemeral=True)

        restored, failed = await antiraid_cog.restore_lockdown(
            interaction.guild,
            "Anti-raid manually unlocked from config panel",
        )
        await interaction.followup.send(
            f"Restored channels: {restored}. Failed restores: {failed}.",
            ephemeral=True,
        )


class AntiRaidSettingsSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Join threshold", value="join_threshold"),
            discord.SelectOption(label="Join window", value="join_window"),
            discord.SelectOption(label="Action", value="action"),
            discord.SelectOption(label="Lockdown duration", value="lockdown_duration"),
            discord.SelectOption(label="Alert channel", value="alert_channel"),
            discord.SelectOption(label="New account days", value="new_account_days"),
            discord.SelectOption(label="New account ratio", value="new_account_ratio"),
        ]
        super().__init__(
            placeholder="Choose an anti-raid setting...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AntiRaidConfigView = self.view  # type: ignore
        value = self.values[0]

        if value == "join_threshold":
            next_view = PresetValueView(
                view.cog,
                view.author_id,
                view.guild_id,
                title="Anti-Raid join threshold",
                description="Choose how many joins inside the window should look suspicious.",
                options=[
                    ("Very strict - 3 joins", 3, "Small private servers"),
                    ("Strict - 5 joins", 5, "Recommended default"),
                    ("Balanced - 8 joins", 8, "Medium communities"),
                    ("Relaxed - 12 joins", 12, "Busy public servers"),
                    ("High traffic - 20 joins", 20, "Large launches/events"),
                ],
                setter=set_antiraid_join_threshold,
                success_message="Anti-raid join threshold set to {value}.",
                min_value=2,
                max_value=100,
                custom_label="Joins before suspicion",
                return_target="antiraid",
            )
            return await interaction.response.edit_message(embed=next_view.build_embed(), view=next_view)

        if value == "join_window":
            next_view = PresetValueView(
                view.cog,
                view.author_id,
                view.guild_id,
                title="Anti-Raid join window",
                description="Choose the time window used to count new joins.",
                options=[
                    ("10 seconds", 10, "Very strict"),
                    ("15 seconds", 15, "Recommended default"),
                    ("30 seconds", 30, "Balanced"),
                    ("60 seconds", 60, "Relaxed"),
                    ("120 seconds", 120, "Slow raid detection"),
                ],
                setter=set_antiraid_join_window_seconds,
                success_message="Anti-raid join window set to {value}s.",
                min_value=5,
                max_value=300,
                custom_label="Window in seconds",
                return_target="antiraid",
            )
            return await interaction.response.edit_message(embed=next_view.build_embed(), view=next_view)

        if value == "lockdown_duration":
            next_view = PresetValueView(
                view.cog,
                view.author_id,
                view.guild_id,
                title="Anti-Raid lockdown duration",
                description="Choose how long text channels stay locked after a confirmed raid.",
                options=[
                    ("5 minutes", 300, "Quick pause"),
                    ("10 minutes", 600, "Recommended default"),
                    ("30 minutes", 1800, "Serious raid"),
                    ("1 hour", 3600, "Long containment"),
                    ("3 hours", 10800, "Emergency mode"),
                ],
                setter=set_antiraid_lockdown_duration_seconds,
                success_message="Lockdown duration set to {value}s.",
                min_value=60,
                max_value=86400,
                custom_label="Duration in seconds",
                return_target="antiraid",
            )
            return await interaction.response.edit_message(embed=next_view.build_embed(), view=next_view)

        if value == "new_account_days":
            next_view = PresetValueView(
                view.cog,
                view.author_id,
                view.guild_id,
                title="Anti-Raid new account days",
                description="Choose what account age counts as suspiciously new.",
                options=[
                    ("Disabled - 0 days", 0, "Ignore account age"),
                    ("1 day", 1, "Very strict"),
                    ("3 days", 3, "Strict"),
                    ("7 days", 7, "Recommended default"),
                    ("14 days", 14, "Cautious"),
                    ("30 days", 30, "Very cautious"),
                ],
                setter=set_antiraid_new_account_max_age_days,
                success_message="New account window set to {value} days.",
                min_value=0,
                max_value=365,
                custom_label="Maximum account age in days",
                return_target="antiraid",
            )
            return await interaction.response.edit_message(embed=next_view.build_embed(), view=next_view)

        if value == "new_account_ratio":
            next_view = PresetValueView(
                view.cog,
                view.author_id,
                view.guild_id,
                title="Anti-Raid new account ratio",
                description="Choose how many recent joins must be new accounts before the rule matters.",
                options=[
                    ("40%", 40, "Very strict"),
                    ("60%", 60, "Recommended default"),
                    ("75%", 75, "Balanced"),
                    ("90%", 90, "Only obvious raids"),
                ],
                setter=set_antiraid_new_account_ratio_threshold,
                success_message="New account ratio set to {value}%.",
                min_value=0,
                max_value=100,
                custom_label="Required percentage",
                return_target="antiraid",
                transform=lambda item: item / 100,
            )
            return await interaction.response.edit_message(embed=next_view.build_embed(), view=next_view)

        if value == "alert_channel":
            return await interaction.response.edit_message(
                embed=view.cog.build_antiraid_alert_channel_embed(),
                view=AntiRaidAlertChannelView(view.cog, view.author_id, view.guild_id),
            )

        next_view = AntiRaidActionView(view.cog, view.author_id, view.guild_id)
        await interaction.response.edit_message(
            embed=await view.cog.build_antiraid_embed(interaction.guild),
            view=next_view,
        )


class AntiRaidAlertChannelView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(AntiRaidAlertChannelSelect())
        self.add_item(AntiRaidAutoAlertChannelButton(row=1))
        self.add_item(BackToAntiRaidButton(row=1))


class AntiRaidAlertChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Choose the anti-raid alert channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AntiRaidAlertChannelView = self.view  # type: ignore
        channel = selected_text_channel(interaction.guild, self.values[0])
        if channel is None:
            return await interaction.response.send_message("Choose a text channel.", ephemeral=True)

        await set_antiraid_alert_channel(interaction.guild.id, channel.id)
        embed = await view.cog.build_antiraid_embed(interaction.guild)
        embed.add_field(name="Updated", value=f"Alerts will be sent to {channel.mention}.", inline=False)
        await interaction.response.edit_message(
            embed=embed,
            view=AntiRaidConfigView(view.cog, view.author_id, view.guild_id),
        )


class AntiRaidAutoAlertChannelButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Use automatic channel", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view: AntiRaidAlertChannelView = self.view  # type: ignore
        await set_antiraid_alert_channel(interaction.guild.id, None)
        embed = await view.cog.build_antiraid_embed(interaction.guild)
        embed.add_field(name="Updated", value="Gerentiu will choose the alert channel automatically.", inline=False)
        await interaction.response.edit_message(
            embed=embed,
            view=AntiRaidConfigView(view.cog, view.author_id, view.guild_id),
        )


class AntiRaidActionView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(AntiRaidActionSelect())
        self.add_item(BackToMainButton())


class AntiRaidActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=choice.title(), value=choice)
            for choice in ANTIRAID_ACTION_CHOICES
        ]
        super().__init__(
            placeholder="Choose anti-raid action...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AntiRaidActionView = self.view  # type: ignore
        antiraid_cog = interaction.client.get_cog("AntiRaidCog")
        if antiraid_cog is None:
            return await interaction.response.send_message(
                "Anti-raid cog is not loaded.",
                ephemeral=True,
            )

        missing = antiraid_cog.get_missing_antiraid_permissions(
            interaction.guild,
            self.values[0],
        )
        if missing:
            return await interaction.response.send_message(
                "Gerentiu is missing the permissions required for that action: "
                + ", ".join(missing),
                ephemeral=True,
            )

        await set_antiraid_action(interaction.guild.id, self.values[0])
        await interaction.response.edit_message(
            embed=await view.cog.build_antiraid_embed(interaction.guild),
            view=AntiRaidConfigView(view.cog, view.author_id, view.guild_id),
        )


class TranslationHubConfigView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int):
        super().__init__(cog, author_id, guild_id)
        self.add_item(BackToMainButton(row=2))

    async def open_hub_picker(self, interaction: discord.Interaction, action: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        hubs = await list_translation_hubs(interaction.guild.id)
        if not hubs:
            return await interaction.response.send_message(
                "Create a translation hub first.",
                ephemeral=True,
            )

        await interaction.response.edit_message(
            embed=self.cog.build_hub_picker_embed(action, hubs),
            view=HubPickerView(self.cog, self.author_id, self.guild_id, action, hubs),
        )

    @discord.ui.button(label="List hubs", style=discord.ButtonStyle.primary, row=0)
    async def list_hubs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=await self.cog.build_translation_embed(interaction.guild),
            view=TranslationHubConfigView(self.cog, self.author_id, self.guild_id),
        )

    @discord.ui.button(label="Create hub", style=discord.ButtonStyle.success, row=0)
    async def create_hub(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateHubModal(self.cog))

    @discord.ui.button(label="Add channel", style=discord.ButtonStyle.secondary, row=0)
    async def add_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_hub_picker(interaction, "add")

    @discord.ui.button(label="Remove channel", style=discord.ButtonStyle.danger, row=1)
    async def remove_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_hub_picker(interaction, "remove")

    @discord.ui.button(label="Delete hub", style=discord.ButtonStyle.danger, row=1)
    async def delete_hub(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_hub_picker(interaction, "delete")


class CreateHubModal(discord.ui.Modal):
    def __init__(self, cog: "ConfigPanelCog"):
        super().__init__(title="Create translation hub")
        self.cog = cog
        self.name_input = discord.ui.TextInput(
            label="Hub name",
            placeholder="global-chat",
            required=True,
            max_length=80,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        name = str(self.name_input.value).strip()
        if not name:
            return await interaction.response.send_message("Hub name cannot be empty.", ephemeral=True)

        try:
            hub_id = await create_translation_hub(interaction.guild.id, name)
        except Exception as exc:
            return await interaction.response.send_message(f"Error: {exc}", ephemeral=True)

        await interaction.response.send_message(
            f"Hub created: **{name}** (ID: {hub_id}). Use Add channel and pick it from the menu.",
            ephemeral=True,
        )


class HubPickerView(AdminConfigView):
    def __init__(
        self,
        cog: "ConfigPanelCog",
        author_id: int,
        guild_id: int,
        action: str,
        hubs: list[dict],
    ):
        super().__init__(cog, author_id, guild_id)
        self.add_item(HubSelect(action, hubs))
        self.add_item(BackToTranslationButton(row=1))


class HubSelect(discord.ui.Select):
    def __init__(self, action: str, hubs: list[dict]):
        self.action = action
        self.hubs_by_id = {int(hub["hub_id"]): hub for hub in hubs[:25]}
        super().__init__(
            placeholder="Choose a translation hub...",
            min_values=1,
            max_values=1,
            options=hub_options(hubs),
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        view: HubPickerView = self.view  # type: ignore
        hub = self.hubs_by_id[int(self.values[0])]

        if self.action == "add":
            next_view = AddHubChannelView(view.cog, view.author_id, view.guild_id, hub)
            return await interaction.response.edit_message(
                embed=next_view.build_embed(interaction.guild),
                view=next_view,
            )

        if self.action == "remove":
            if not hub["channels"]:
                return await interaction.response.send_message(
                    "This hub has no configured channels yet.",
                    ephemeral=True,
                )

            next_view = RemoveHubChannelView(view.cog, view.author_id, view.guild_id, interaction.guild, hub)
            return await interaction.response.edit_message(
                embed=next_view.build_embed(interaction.guild),
                view=next_view,
            )

        next_view = DeleteHubConfirmView(view.cog, view.author_id, view.guild_id, hub)
        await interaction.response.edit_message(
            embed=next_view.build_embed(),
            view=next_view,
        )


class AddHubChannelView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int, hub: dict):
        super().__init__(cog, author_id, guild_id)
        self.hub = hub
        self.selected_channel_id: int | None = None
        self.selected_channel_mention: str | None = None
        self.selected_language: str | None = None
        self.add_item(HubTextChannelSelect(row=0))
        self.add_item(HubLanguageSelect(row=1))
        self.add_item(SaveHubChannelButton(row=2))
        self.add_item(BackToTranslationButton(row=2))

    def build_embed(self, guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title=f"Add channel to {self.hub['hub_name']}",
            description="Choose a text channel and its language, then press Save.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Hub", value=self.hub["hub_name"], inline=False)
        embed.add_field(
            name="Channel",
            value=self.selected_channel_mention or "Not selected yet",
            inline=True,
        )
        embed.add_field(
            name="Language",
            value=LANG_NAMES.get(self.selected_language, self.selected_language or "Not selected yet"),
            inline=True,
        )
        return embed


class HubTextChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, row: int | None = None):
        super().__init__(
            placeholder="Choose a text channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AddHubChannelView = self.view  # type: ignore
        channel = selected_text_channel(interaction.guild, self.values[0])
        if channel is None:
            return await interaction.response.send_message("Choose a text channel.", ephemeral=True)

        view.selected_channel_id = channel.id
        view.selected_channel_mention = channel.mention
        await interaction.response.edit_message(
            embed=view.build_embed(interaction.guild),
            view=view,
        )


class HubLanguageSelect(discord.ui.Select):
    def __init__(self, row: int | None = None):
        super().__init__(
            placeholder="Choose this channel's language...",
            min_values=1,
            max_values=1,
            options=language_options(),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        view: AddHubChannelView = self.view  # type: ignore
        view.selected_language = self.values[0]
        await interaction.response.edit_message(
            embed=view.build_embed(interaction.guild),
            view=view,
        )


class SaveHubChannelButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Save", style=discord.ButtonStyle.success, row=row)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        view: AddHubChannelView = self.view  # type: ignore
        if view.selected_channel_id is None or view.selected_language is None:
            return await interaction.response.send_message(
                "Choose both a channel and a language first.",
                ephemeral=True,
            )

        channel = interaction.guild.get_channel(view.selected_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("Text channel not found.", ephemeral=True)

        try:
            await add_channel_to_hub(
                interaction.guild.id,
                int(view.hub["hub_id"]),
                channel.id,
                view.selected_language,
            )
            invalidate_translation_cache(interaction.client, interaction.guild.id)
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                return await interaction.response.send_message(
                    "This channel already belongs to another hub.",
                    ephemeral=True,
                )
            return await interaction.response.send_message(f"Error: {exc}", ephemeral=True)

        embed = await view.cog.build_translation_embed(interaction.guild)
        embed.add_field(
            name="Updated",
            value=f"{channel.mention} was added to {view.hub['hub_name']} as {LANG_NAMES[view.selected_language]}.",
            inline=False,
        )
        await interaction.response.edit_message(
            embed=embed,
            view=TranslationHubConfigView(view.cog, view.author_id, view.guild_id),
        )


class RemoveHubChannelView(AdminConfigView):
    def __init__(
        self,
        cog: "ConfigPanelCog",
        author_id: int,
        guild_id: int,
        guild: discord.Guild,
        hub: dict,
    ):
        super().__init__(cog, author_id, guild_id)
        self.hub = hub
        self.selected_channel_id: int | None = None
        self.add_item(ConfiguredHubChannelSelect(guild, hub, row=0))
        self.add_item(RemoveHubChannelButton(row=1))
        self.add_item(BackToTranslationButton(row=1))

    def build_embed(self, guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title=f"Remove channel from {self.hub['hub_name']}",
            description="Choose one configured channel and press Remove.",
            color=discord.Color.blue(),
        )
        value = f"<#{self.selected_channel_id}>" if self.selected_channel_id else "Not selected yet"
        embed.add_field(name="Channel", value=value, inline=False)
        return embed


class ConfiguredHubChannelSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild, hub: dict, row: int | None = None):
        self.hub = hub
        super().__init__(
            placeholder="Choose a configured channel...",
            min_values=1,
            max_values=1,
            options=configured_channel_options(guild, hub),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        view: RemoveHubChannelView = self.view  # type: ignore
        view.selected_channel_id = int(self.values[0])
        await interaction.response.edit_message(
            embed=view.build_embed(interaction.guild),
            view=view,
        )


class RemoveHubChannelButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Remove", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        view: RemoveHubChannelView = self.view  # type: ignore
        if view.selected_channel_id is None:
            return await interaction.response.send_message("Choose a channel first.", ephemeral=True)

        removed = await remove_channel_from_hub(
            interaction.guild.id,
            int(view.hub["hub_id"]),
            view.selected_channel_id,
        )
        invalidate_translation_cache(interaction.client, interaction.guild.id)

        embed = await view.cog.build_translation_embed(interaction.guild)
        if removed:
            embed.add_field(
                name="Updated",
                value=f"<#{view.selected_channel_id}> was removed from {view.hub['hub_name']}.",
                inline=False,
            )
        else:
            embed.add_field(
                name="Not changed",
                value="That channel was not in this hub.",
                inline=False,
            )

        await interaction.response.edit_message(
            embed=embed,
            view=TranslationHubConfigView(view.cog, view.author_id, view.guild_id),
        )


class DeleteHubConfirmView(AdminConfigView):
    def __init__(self, cog: "ConfigPanelCog", author_id: int, guild_id: int, hub: dict):
        super().__init__(cog, author_id, guild_id)
        self.hub = hub
        self.add_item(ConfirmDeleteHubButton(row=0))
        self.add_item(BackToTranslationButton(row=0))

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"Delete {self.hub['hub_name']}?",
            description="This removes the hub and every channel route inside it.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Configured channels", value=str(len(self.hub["channels"])), inline=True)
        return embed


class ConfirmDeleteHubButton(discord.ui.Button):
    def __init__(self, row: int | None = None):
        super().__init__(label="Delete hub", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        view: DeleteHubConfirmView = self.view  # type: ignore
        deleted = await delete_translation_hub(interaction.guild.id, int(view.hub["hub_id"]))
        invalidate_translation_cache(interaction.client, interaction.guild.id)

        embed = await view.cog.build_translation_embed(interaction.guild)
        if deleted:
            embed.add_field(
                name="Updated",
                value=f"{view.hub['hub_name']} was deleted.",
                inline=False,
            )
        else:
            embed.add_field(name="Not changed", value="Hub not found in this server.", inline=False)

        await interaction.response.edit_message(
            embed=embed,
            view=TranslationHubConfigView(view.cog, view.author_id, view.guild_id),
        )


class ConfigPanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def build_main_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Gerentiu Configuration",
            description="Choose a system below and configure it without memorizing every slash command.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Anti-Spam", value="Message flood and repeated link control.", inline=False)
        embed.add_field(name="Anti-Raid", value="Mass join alerts and lockdown control.", inline=False)
        embed.add_field(name="Translation Hubs", value="Translation channel routing.", inline=False)
        embed.add_field(name="Help", value="A quick guide for the buttons and risky actions in this panel.", inline=False)
        return embed

    def build_config_help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Configuration panel help",
            description="Use this panel when you want to change Gerentiu settings without memorizing slash commands.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Anti-Spam",
            value="Enable or disable spam protection and tune message limits, timing and the strongest punishment.",
            inline=False,
        )
        embed.add_field(
            name="Anti-Raid",
            value="Enable or disable raid detection, tune mass-join thresholds and choose alert channels from a menu.",
            inline=False,
        )
        embed.add_field(
            name="Translation Hubs",
            value="List hubs, create hubs, pick channels and languages, remove channels or delete an entire hub.",
            inline=False,
        )
        embed.add_field(
            name="Careful buttons",
            value="Deleting a hub removes all channel routes inside it. Anti-raid lockdown changes channel permissions.",
            inline=False,
        )
        return embed

    def build_antiraid_alert_channel_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Anti-Raid alert channel",
            description="Choose where raid alerts should be posted, or leave it automatic.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Automatic",
            value="Gerentiu will try to use the configured channel, the current channel or the first channel he can write in.",
            inline=False,
        )
        return embed

    def build_hub_picker_embed(self, action: str, hubs: list[dict]) -> discord.Embed:
        labels = {
            "add": ("Choose a hub", "Pick the hub that will receive a new translated channel."),
            "remove": ("Choose a hub", "Pick the hub you want to remove a channel from."),
            "delete": ("Choose a hub", "Pick the hub you want to delete."),
        }
        title, description = labels[action]
        embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        embed.add_field(name="Available hubs", value=str(min(len(hubs), 25)), inline=True)
        if len(hubs) > 25:
            embed.add_field(
                name="Limit",
                value="Discord menus show 25 options at a time. Showing the first 25 hubs.",
                inline=False,
            )
        return embed

    async def build_antispam_embed(self, guild: discord.Guild) -> discord.Embed:
        config = await get_antispam_config(guild.id)
        embed = discord.Embed(
            title="Anti-Spam configuration",
            color=discord.Color.green() if config["enabled"] else discord.Color.red(),
        )
        embed.add_field(name="Status", value="ACTIVE" if config["enabled"] else "INACTIVE", inline=True)
        embed.add_field(name="Max messages", value=str(config["max_messages"]), inline=True)
        embed.add_field(name="Interval", value=f"{config['interval_seconds']}s", inline=True)
        embed.add_field(name="Max punishment", value=config["max_punishment"], inline=True)
        embed.add_field(
            name="Cross-channel protection",
            value="Same links and repeated messages across channels.",
            inline=False,
        )
        return embed

    async def build_antiraid_embed(self, guild: discord.Guild) -> discord.Embed:
        config = await get_antiraid_config(guild.id)
        lockdown_rows = await list_antiraid_lockdown_channels(guild.id)
        antiraid_cog = self.bot.get_cog("AntiRaidCog")
        state = (
            antiraid_cog.detector.get_state(guild.id)
            if antiraid_cog is not None
            else {"state": "UNKNOWN", "score": 0}
        )

        embed = discord.Embed(
            title="Anti-Raid configuration",
            color=discord.Color.green() if config["enabled"] else discord.Color.red(),
        )
        embed.add_field(name="Status", value="ACTIVE" if config["enabled"] else "INACTIVE", inline=True)
        embed.add_field(name="State", value=state["state"], inline=True)
        embed.add_field(name="Score", value=str(state["score"]), inline=True)
        embed.add_field(name="Join threshold", value=str(config["join_threshold"]), inline=True)
        embed.add_field(name="Join window", value=f"{config['join_window_seconds']}s", inline=True)
        embed.add_field(name="Action", value=config["action"], inline=True)
        embed.add_field(name="Lockdown duration", value=f"{config['lockdown_duration_seconds']}s", inline=True)
        embed.add_field(
            name="Alert channel",
            value=f"<#{config['alert_channel_id']}>" if config["alert_channel_id"] else "Auto",
            inline=True,
        )
        embed.add_field(name="Locked channels", value=str(len(lockdown_rows)), inline=True)
        embed.add_field(
            name="New account rule",
            value=(
                f"<= {config['new_account_max_age_days']} days, "
                f"{int(config['new_account_ratio_threshold'] * 100)}% ratio"
            ),
            inline=False,
        )
        return embed

    async def build_translation_embed(self, guild: discord.Guild) -> discord.Embed:
        hubs = await list_translation_hubs(guild.id)
        embed = discord.Embed(
            title="Translation Hubs configuration",
            color=discord.Color.blue(),
        )

        if not hubs:
            embed.description = "No hubs created yet. Create one, add channels, assign languages, then let the webhook magic work."
            return embed

        lines = []
        for hub in hubs:
            lines.append(f"**{hub['hub_name']} (ID: {hub['hub_id']})**")
            if not hub["channels"]:
                lines.append("  no channels configured")
                continue

            for channel in hub["channels"]:
                language = LANG_NAMES.get(channel["language"], channel["language"])
                lines.append(f"  <#{channel['channel_id']}> - {language}")

        embed.description = "\n".join(lines)
        return embed

    @app_commands.command(name="config", description="Open Gerentiu's interactive configuration panel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config_panel(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used on servers.",
                ephemeral=True,
            )

        view = MainConfigView(self, interaction.user.id, interaction.guild.id)
        await interaction.response.send_message(
            embed=self.build_main_embed(),
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigPanelCog(bot))
