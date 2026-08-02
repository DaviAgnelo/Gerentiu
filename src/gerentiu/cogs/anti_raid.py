import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from gerentiu.cogs.raid_detector import DEFAULT_RAID_CONFIG, RaidDetector
from gerentiu.permission_policy import missing_antiraid_permissions
from gerentiu.db import (
    clear_antiraid_lockdown_channel,
    get_antiraid_config,
    list_all_antiraid_lockdown_channels,
    list_antiraid_lockdown_channels,
    save_antiraid_lockdown_channel,
    set_antiraid_action,
    set_antiraid_alert_channel,
    set_antiraid_enabled,
    set_antiraid_join_threshold,
    set_antiraid_join_window_seconds,
    set_antiraid_lockdown_duration_seconds,
    set_antiraid_new_account_max_age_days,
    set_antiraid_new_account_ratio_threshold,
)


ANTIRAID_ACTIONS = {"alert", "lockdown"}


def _is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False

    perms = interaction.user.guild_permissions  # type: ignore
    return perms.manage_guild


class AntiRaidCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.detector = RaidDetector()
        self.unlock_tasks: dict[int, asyncio.Task] = {}
        self.resume_task: asyncio.Task | None = None

    async def cog_load(self):
        self.resume_task = asyncio.create_task(self.resume_lockdowns())

    def cog_unload(self):
        if self.resume_task is not None:
            self.resume_task.cancel()

        for task in self.unlock_tasks.values():
            task.cancel()

    antiraid_group = app_commands.Group(
        name="antiraid",
        description="Anti-raid configuration system."
    )

    @staticmethod
    def build_detector_config(config: dict) -> dict:
        detector_config = dict(DEFAULT_RAID_CONFIG)
        detector_config["join_threshold"] = config["join_threshold"]
        detector_config["join_window_sec"] = config["join_window_seconds"]
        detector_config["new_account_max_age_days"] = config["new_account_max_age_days"]
        detector_config["new_account_ratio_threshold"] = config["new_account_ratio_threshold"]
        return detector_config

    @staticmethod
    def get_missing_antiraid_permissions(guild: discord.Guild, action: str) -> list[str]:
        me = guild.me
        if me is None:
            return ["Could not resolve bot member."]

        return missing_antiraid_permissions(me.guild_permissions, action)

    async def resolve_alert_channel(
        self,
        guild: discord.Guild,
        config: dict,
        fallback: discord.abc.Messageable | None = None,
    ) -> discord.TextChannel | None:
        if guild.me is None:
            return None

        candidates = []
        alert_channel_id = config.get("alert_channel_id")

        if alert_channel_id is not None:
            candidates.append(guild.get_channel(alert_channel_id))

        if isinstance(fallback, discord.TextChannel):
            candidates.append(fallback)

        if guild.system_channel is not None:
            candidates.append(guild.system_channel)

        candidates.extend(guild.text_channels)

        seen = set()
        for channel in candidates:
            if not isinstance(channel, discord.TextChannel):
                continue
            if channel.id in seen:
                continue

            seen.add(channel.id)
            permissions = channel.permissions_for(guild.me)
            if permissions.view_channel and permissions.send_messages:
                return channel

        return None

    async def send_raid_alert(
        self,
        guild: discord.Guild,
        config: dict,
        result: dict,
        reason: str,
        fallback: discord.abc.Messageable | None = None,
    ) -> discord.TextChannel | None:
        channel = await self.resolve_alert_channel(guild, config, fallback)
        if channel is None:
            return None

        state = result["new_state"]
        color = discord.Color.orange() if state == "SUSPECTED" else discord.Color.red()
        embed = discord.Embed(
            title=f"Anti-Raid: {state}",
            description=reason,
            color=color,
        )
        embed.add_field(name="Join count", value=str(result["join_count"]), inline=True)
        embed.add_field(
            name="Suspicious messages",
            value=str(result["suspicious_message_count"]),
            inline=True
        )
        embed.add_field(name="Score", value=str(result["score"]), inline=True)
        embed.add_field(name="Configured action", value=config["action"], inline=True)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            return None

        return channel

    async def send_action_summary(
        self,
        channel: discord.TextChannel | None,
        title: str,
        description: str,
        color: discord.Color,
    ):
        if channel is None:
            return

        embed = discord.Embed(title=title, description=description, color=color)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    def schedule_unlock(self, guild_id: int, locked_until: int):
        existing = self.unlock_tasks.pop(guild_id, None)
        if existing is not None:
            existing.cancel()

        delay = max(0, locked_until - int(time.time()))
        self.unlock_tasks[guild_id] = asyncio.create_task(
            self.unlock_after_delay(guild_id, delay)
        )

    async def unlock_after_delay(self, guild_id: int, delay: int):
        try:
            await asyncio.sleep(delay)
            guild = self.bot.get_guild(guild_id)
            if guild is not None:
                await self.restore_lockdown(guild, "Anti-raid lockdown expired")
        finally:
            self.unlock_tasks.pop(guild_id, None)

    async def resume_lockdowns(self):
        await self.bot.wait_until_ready()

        rows = await list_all_antiraid_lockdown_channels()
        guild_ids = {
            row["guild_id"]
            for row in rows
        }

        now = int(time.time())
        for guild_id in guild_ids:
            guild_rows = [
                row
                for row in rows
                if row["guild_id"] == guild_id
            ]
            locked_until = max(row["locked_until"] for row in guild_rows)
            guild = self.bot.get_guild(guild_id)

            if guild is None:
                continue

            if locked_until <= now:
                await self.restore_lockdown(guild, "Anti-raid lockdown expired while bot was offline")
            else:
                self.schedule_unlock(guild_id, locked_until)

    async def apply_lockdown(self, guild: discord.Guild, duration_seconds: int) -> tuple[int, int]:
        if guild.me is None:
            return 0, 0

        locked_until = int(time.time()) + duration_seconds
        existing_rows = await list_antiraid_lockdown_channels(guild.id)
        existing = {
            row["channel_id"]: row
            for row in existing_rows
        }

        locked = 0
        failed = 0

        for channel in guild.text_channels:
            permissions = channel.permissions_for(guild.me)
            if not permissions.manage_channels:
                failed += 1
                continue

            if channel.id in existing:
                row = existing[channel.id]
                await save_antiraid_lockdown_channel(
                    guild.id,
                    channel.id,
                    row["previous_send_messages"],
                    locked_until,
                )
                locked += 1
                continue

            overwrite = channel.overwrites_for(guild.default_role)
            previous_send_messages = overwrite.send_messages

            if previous_send_messages is False:
                continue

            await save_antiraid_lockdown_channel(
                guild.id,
                channel.id,
                previous_send_messages,
                locked_until,
            )

            overwrite.send_messages = False

            try:
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason="Anti-raid lockdown triggered",
                )
            except discord.HTTPException:
                failed += 1
                await clear_antiraid_lockdown_channel(guild.id, channel.id)
                continue

            locked += 1

        self.schedule_unlock(guild.id, locked_until)
        return locked, failed

    async def restore_lockdown(self, guild: discord.Guild, reason: str) -> tuple[int, int]:
        if guild.me is None:
            return 0, 0

        rows = await list_antiraid_lockdown_channels(guild.id)
        restored = 0
        failed = 0

        for row in rows:
            channel = guild.get_channel(row["channel_id"])

            if not isinstance(channel, discord.TextChannel):
                await clear_antiraid_lockdown_channel(guild.id, row["channel_id"])
                continue

            permissions = channel.permissions_for(guild.me)
            if not permissions.manage_channels:
                failed += 1
                continue

            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = row["previous_send_messages"]

            try:
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=reason,
                )
            except discord.HTTPException:
                failed += 1
                continue

            await clear_antiraid_lockdown_channel(guild.id, channel.id)
            restored += 1

        return restored, failed

    async def handle_raid_result(
        self,
        guild: discord.Guild,
        config: dict,
        result: dict | None,
        reason: str,
        fallback: discord.abc.Messageable | None = None,
    ):
        if result is None or not result.get("changed"):
            return

        state = result["new_state"]
        if state == "NORMAL":
            return

        alert_channel = await self.send_raid_alert(guild, config, result, reason, fallback)

        if state != "UNDER_RAID":
            return

        action = config["action"]
        if action not in ANTIRAID_ACTIONS:
            action = "lockdown"

        missing = self.get_missing_antiraid_permissions(guild, action)
        if missing:
            await self.send_action_summary(
                alert_channel,
                "Anti-Raid action blocked",
                "Missing permissions: " + ", ".join(missing),
                discord.Color.red(),
            )
            return

        if action == "alert":
            return

        locked, failed = await self.apply_lockdown(
            guild,
            config["lockdown_duration_seconds"],
        )
        await self.send_action_summary(
            alert_channel,
            "Anti-Raid lockdown applied",
            f"Locked channels: {locked}\nFailed channels: {failed}",
            discord.Color.red(),
        )

    @antiraid_group.command(name="enable", description="Activates anti-raid on this server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_enable(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used on servers.",
                ephemeral=True,
            )

        if not _is_admin(interaction):
            return await interaction.response.send_message("No permission.", ephemeral=True)

        config = await get_antiraid_config(interaction.guild.id)
        missing = self.get_missing_antiraid_permissions(interaction.guild, config["action"])
        if missing:
            return await interaction.response.send_message(
                "Gerentiu is missing the following permissions: " + ", ".join(missing),
                ephemeral=True,
            )

        if config["alert_channel_id"] is None and isinstance(interaction.channel, discord.TextChannel):
            await set_antiraid_alert_channel(interaction.guild.id, interaction.channel.id)

        await set_antiraid_enabled(interaction.guild.id, True)
        self.detector.reset_guild(interaction.guild.id)

        await interaction.response.send_message(
            "Anti-raid successfully activated.",
            ephemeral=True,
        )

    @antiraid_group.command(name="disable", description="Deactivates anti-raid on this server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_disable(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used on servers.",
                ephemeral=True,
            )

        if not _is_admin(interaction):
            return await interaction.response.send_message("No permission.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await set_antiraid_enabled(interaction.guild.id, False)
        self.detector.reset_guild(interaction.guild.id)
        restored, failed = await self.restore_lockdown(
            interaction.guild,
            "Anti-raid disabled by administrator",
        )

        await interaction.followup.send(
            f"Anti-raid disabled. Restored channels: {restored}. Failed restores: {failed}.",
            ephemeral=True,
        )

    @antiraid_group.command(name="status", description="Displays the current anti-raid status.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_status(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used on servers.",
                ephemeral=True,
            )

        config = await get_antiraid_config(interaction.guild.id)
        state = self.detector.get_state(interaction.guild.id)
        lockdown_rows = await list_antiraid_lockdown_channels(interaction.guild.id)

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
        embed.add_field(
            name="Lockdown duration",
            value=f"{config['lockdown_duration_seconds']}s",
            inline=True,
        )
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @antiraid_group.command(name="join_threshold", description="Sets how many joins trigger raid suspicion.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_join_threshold(self, interaction: discord.Interaction, value: int):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        if value < 2 or value > 100:
            return await interaction.response.send_message("Value must be between 2 and 100.", ephemeral=True)

        await set_antiraid_join_threshold(interaction.guild.id, value)
        self.detector.reset_guild(interaction.guild.id)
        await interaction.response.send_message(f"Anti-raid join threshold set to {value}.", ephemeral=True)

    @antiraid_group.command(name="join_window", description="Sets the join detection window in seconds.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_join_window(self, interaction: discord.Interaction, seconds: int):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        if seconds < 5 or seconds > 300:
            return await interaction.response.send_message("Value must be between 5 and 300 seconds.", ephemeral=True)

        await set_antiraid_join_window_seconds(interaction.guild.id, seconds)
        self.detector.reset_guild(interaction.guild.id)
        await interaction.response.send_message(f"Anti-raid join window set to {seconds}s.", ephemeral=True)

    @antiraid_group.command(name="action", description="Sets what Gerentiu does when a raid is confirmed.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(value=[
        app_commands.Choice(name="Alert only", value="alert"),
        app_commands.Choice(name="Lockdown text channels", value="lockdown"),
    ])
    async def antiraid_action(self, interaction: discord.Interaction, value: app_commands.Choice[str]):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        if value.value not in ANTIRAID_ACTIONS:
            return await interaction.response.send_message("Invalid action.", ephemeral=True)

        missing = self.get_missing_antiraid_permissions(interaction.guild, value.value)
        if missing:
            return await interaction.response.send_message(
                "Gerentiu is missing the following permissions: " + ", ".join(missing),
                ephemeral=True,
            )

        await set_antiraid_action(interaction.guild.id, value.value)
        await interaction.response.send_message(f"Anti-raid action set to {value.value}.", ephemeral=True)

    @antiraid_group.command(name="lockdown_duration", description="Sets lockdown duration in seconds.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_lockdown_duration(self, interaction: discord.Interaction, seconds: int):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        if seconds < 60 or seconds > 86400:
            return await interaction.response.send_message("Value must be between 60 and 86400 seconds.", ephemeral=True)

        await set_antiraid_lockdown_duration_seconds(interaction.guild.id, seconds)
        await interaction.response.send_message(f"Anti-raid lockdown duration set to {seconds}s.", ephemeral=True)

    @antiraid_group.command(name="alert_channel", description="Sets the anti-raid alert channel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_alert_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        await set_antiraid_alert_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"Anti-raid alert channel set to {channel.mention}.", ephemeral=True)

    @antiraid_group.command(name="new_account_days", description="Sets what counts as a new account.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_new_account_days(self, interaction: discord.Interaction, days: int):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        if days < 0 or days > 365:
            return await interaction.response.send_message("Value must be between 0 and 365 days.", ephemeral=True)

        await set_antiraid_new_account_max_age_days(interaction.guild.id, days)
        self.detector.reset_guild(interaction.guild.id)
        await interaction.response.send_message(f"New account window set to {days} days.", ephemeral=True)

    @antiraid_group.command(name="new_account_ratio", description="Sets the new-account ratio needed for raid suspicion.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_new_account_ratio(self, interaction: discord.Interaction, percent: int):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        if percent < 0 or percent > 100:
            return await interaction.response.send_message("Value must be between 0 and 100.", ephemeral=True)

        await set_antiraid_new_account_ratio_threshold(interaction.guild.id, percent / 100)
        self.detector.reset_guild(interaction.guild.id)
        await interaction.response.send_message(f"New account ratio set to {percent}%.", ephemeral=True)

    @antiraid_group.command(name="unlock", description="Manually restores channels locked by anti-raid.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_unlock(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use on a server.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        restored, failed = await self.restore_lockdown(
            interaction.guild,
            "Anti-raid manually unlocked by administrator",
        )

        task = self.unlock_tasks.pop(interaction.guild.id, None)
        if task is not None:
            task.cancel()

        await interaction.followup.send(
            f"Restored channels: {restored}. Failed restores: {failed}.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = await get_antiraid_config(member.guild.id)
        if not config["enabled"]:
            return

        result = self.detector.register_join(
            member,
            self.build_detector_config(config),
        )
        await self.handle_raid_result(
            member.guild,
            config,
            result,
            f"Mass join pattern detected after {member.mention} joined.",
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        config = await get_antiraid_config(message.guild.id)
        if not config["enabled"]:
            return

        result = self.detector.register_message(
            message,
            self.build_detector_config(config),
        )
        await self.handle_raid_result(
            message.guild,
            config,
            result,
            "Suspicious messages from recently joined members increased the raid score.",
            message.channel,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaidCog(bot))
