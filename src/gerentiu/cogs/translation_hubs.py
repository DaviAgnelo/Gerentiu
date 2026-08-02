import discord
from discord import app_commands
from discord.ext import commands
from gerentiu.db import (
    create_translation_hub,
    delete_translation_hub,
    add_channel_to_hub,
    remove_channel_from_hub,
    list_translation_hubs,
)

LANG_NAMES = {
    "pt": "Português BR",
    "en": "English US",
    "fr": "French FR",
    "de": "German DE",
    "ko": "Korean KR",
    "es": "Spanish ES",
    "zh": "Chinese CN",
    "ja": "Japanese JP",
    "ru": "Russian RU",
    "it": "Italian IT",
    "hi": "Hindi IN",
}

def _is_admin(interaction: discord.Interaction) -> bool:
# Requer permissão de gerenciar servidor ou Manage Channels
    if not interaction.guild:
        return False
    perms = interaction.user.guild_permissions  # type: ignore
    return perms.manage_guild


class TranslateHubsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

# Adiciona uma rota de tradução entre dois canais

    @app_commands.command(name="hub_create", description="Cria um hub de tradução.")
    @app_commands.describe(name="Nome do hub")
    async def hub_create(self, interaction: discord.Interaction, name: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use em um servidor.", ephemeral=True)

        if not _is_admin(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        try:
            hub_id = await create_translation_hub(interaction.guild.id, name)
        except Exception as e:
            return await interaction.response.send_message(f"Erro: {e}", ephemeral=True)

        await interaction.response.send_message(
            f"✅ Hub criado: **{name}** (ID: {hub_id})",
            ephemeral=True
        )

    @app_commands.command(name="hub_add", description="Adiciona um canal ao hub.")
    @app_commands.describe(
        hub_id="ID do hub",
        channel="Canal",
        language="Idioma do canal"
    )
    @app_commands.choices(
        language=[
            app_commands.Choice(name="Portuguese", value="pt"),
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="French", value="fr"),
            app_commands.Choice(name="German", value="de"),
            app_commands.Choice(name="Korean", value="ko"),
            app_commands.Choice(name="Spanish", value="es"),
            app_commands.Choice(name="Chinese", value="zh"),
            app_commands.Choice(name="Japanese", value="ja"),
            app_commands.Choice(name="Russian", value="ru"),
            app_commands.Choice(name="Italian", value="it"),
            app_commands.Choice(name="Hindi", value="hi"),
        ]
    )
    async def hub_add(self, interaction: discord.Interaction, hub_id: int, channel: discord.TextChannel, language: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use em um servidor.", ephemeral=True)

        if not _is_admin(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        try:
            await add_channel_to_hub(interaction.guild.id, hub_id, channel.id, language)
            listener = self.bot.get_cog("TranslationListenerCog")
            if listener is not None:
                listener.invalidate_translation_hub_cache(interaction.guild.id)
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return await interaction.response.send_message(
                    "Esse canal já pertence a outro hub.",
                    ephemeral=True
                )
            return await interaction.response.send_message(
                f"Erro: {e}",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ {channel.mention} adicionado ao hub {hub_id} ({LANG_NAMES.get(language, language)})",
            ephemeral=True
        )

    @app_commands.command(name="hub_remove", description="Remove canal do hub.")
    async def hub_remove(self, interaction: discord.Interaction, hub_id: int, channel: discord.TextChannel):
        if not interaction.guild:
            return await interaction.response.send_message("Use em um servidor.", ephemeral=True)

        if not _is_admin(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        removed = await remove_channel_from_hub(interaction.guild.id, hub_id, channel.id)
        listener = self.bot.get_cog("TranslationListenerCog")
        if listener is not None:
            listener.invalidate_translation_hub_cache(interaction.guild.id)

        if removed:
            msg = f"🗑️ {channel.mention} removido do hub {hub_id}"
        else:
            msg = f"⚠️ Canal não estava no hub"

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="hub_delete", description="Deleta um hub de tradução inteiro.")
    async def hub_delete(self, interaction: discord.Interaction, hub_id: int):
        if not interaction.guild:
            return await interaction.response.send_message("Use em um servidor.", ephemeral=True)

        if not _is_admin(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        deleted = await delete_translation_hub(interaction.guild.id, hub_id)
        listener = self.bot.get_cog("TranslationListenerCog")
        if listener is not None:
            listener.invalidate_translation_hub_cache(interaction.guild.id)

        if deleted:
            msg = f"🗑️ Hub {hub_id} deletado. Todos os canais configurados nele foram removidos."
        else:
            msg = "⚠️ Hub não encontrado nesse servidor."

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="hub_list", description="Lista os hubs.")
    async def hub_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Use em um servidor.", ephemeral=True)

        hubs = await list_translation_hubs(interaction.guild.id)

        if not hubs:
            return await interaction.response.send_message("Nenhum hub criado.", ephemeral=True)

        lines = []
        for hub in hubs:
            lines.append(f"**{hub['hub_name']} (ID: {hub['hub_id']})**")

            for ch in hub["channels"]:
                lines.append(f"  └ <#{ch['channel_id']}> ({ch['language']})")

        embed = discord.Embed(title="🌐 Translation Hubs")
        embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TranslateHubsCog(bot))
