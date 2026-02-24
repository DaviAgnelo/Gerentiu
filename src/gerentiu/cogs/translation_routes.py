import discord
from discord import app_commands
from discord.ext import commands

from gerentiu.db import set_translation_route, remove_translation_route, list_translation_routes


def _is_admin(interaction: discord.Interaction) -> bool:
    # Requer permissão de gerenciar servidor (você pode trocar por Manage Channels se preferir)
    if not interaction.guild:
        return False
    perms = interaction.user.guild_permissions  # type: ignore
    return perms.manage_guild


class TranslateRoutesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="tr_add", description="Adiciona uma rota de tradução automática: source -> target (lang).")
    @app_commands.describe(
        source="Canal de origem (onde as mensagens serão lidas)",
        target="Canal de destino (onde o eco/tradução será enviado)",
        lang="Idioma de destino (ex: en, pt, es, fr)"
    )
    async def tr_add(self, interaction: discord.Interaction, source: discord.TextChannel, target: discord.TextChannel, lang: str):
        if not interaction.guild:
            await interaction.response.send_message("Use em um servidor.", ephemeral=True)
            return
        if not _is_admin(interaction):
            await interaction.response.send_message("Sem permissão (requer **Gerenciar servidor**).", ephemeral=True)
            return
        if source.id == target.id:
            await interaction.response.send_message("Source e target não podem ser o mesmo canal.", ephemeral=True)
            return

        await set_translation_route(interaction.guild.id, source.id, target.id, lang)
        await interaction.response.send_message(
            f"✅ Rota criada: {source.mention} → {target.mention} (lang: `{lang.lower().strip()}`)",
            ephemeral=True,
        )

    @app_commands.command(name="tr_remove", description="Remove uma rota de tradução automática (source -> target).")
    @app_commands.describe(
        source="Canal de origem",
        target="Canal de destino"
    )
    async def tr_remove(self, interaction: discord.Interaction, source: discord.TextChannel, target: discord.TextChannel):
        if not interaction.guild:
            await interaction.response.send_message("Use em um servidor.", ephemeral=True)
            return
        if not _is_admin(interaction):
            await interaction.response.send_message("Sem permissão (requer **Gerenciar servidor**).", ephemeral=True)
            return

        removed = await remove_translation_route(interaction.guild.id, source.id, target.id)
        if removed:
            msg = f"🗑️ Rota removida: {source.mention} → {target.mention}"
        else:
            msg = f"⚠️ Não achei essa rota: {source.mention} → {target.mention}"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="tr_list", description="Lista as rotas de tradução automática configuradas no servidor.")
    async def tr_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Use em um servidor.", ephemeral=True)
            return

        routes = await list_translation_routes(interaction.guild.id)
        if not routes:
            await interaction.response.send_message("Nenhuma rota configurada ainda.", ephemeral=True)
            return

        lines = []
        for src_id, tgt_id, lang in routes:
            lines.append(f"<#{src_id}> → <#{tgt_id}> (`{lang}`)")

        embed = discord.Embed(title="🌐 Rotas de tradução")
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TranslateRoutesCog(bot))
