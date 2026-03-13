import discord
from discord import app_commands
from discord.ext import commands
from gerentiu.db import set_translation_pair, remove_translation_pair, list_translation_pairs


def _is_admin(interaction: discord.Interaction) -> bool:
# Requer permissão de gerenciar servidor ou Manage Channels
    if not interaction.guild:
        return False
    perms = interaction.user.guild_permissions  # type: ignore
    return perms.manage_guild


class TranslateRoutesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

# Adiciona uma rota de tradução entre dois canais

    @app_commands.command(name="tr_add", description="Adiciona um par de tradução automática entre os dois canais.")
    @app_commands.describe(
        channel_1="Canal 1 (Com seu idioma configurado)",
        channel_2="Canal 2 (Com o segundo idioma configurado)",
        lang_1="Idioma do canal 1 (ex: en, pt, es, fr)",
        lang_2="Idioma do canal 2 (ex: en, pt, es, fr)",
    )

# Filtra comandos do usuário que podem dar problema

    async def tr_add(self, interaction: discord.Interaction, channel_1: discord.TextChannel, channel_2: discord.TextChannel, lang_1: str, lang_2: str):
        if not interaction.guild:
            await interaction.response.send_message("Use em um servidor.", ephemeral=True)
            return
        if not _is_admin(interaction):
            await interaction.response.send_message("Sem permissão (requer **Gerenciar servidor**).", ephemeral=True)
            return
        if channel_1.id == channel_2.id:
            await interaction.response.send_message("Os canais não podem ser o mesmo canal.", ephemeral=True)
            return

# Cria a rota baseado no canal de origem e destino, junto dos idiomas de origem e destino
        lang_1 = lang_1.lower().strip()
        lang_2 = lang_2.lower().strip()

        await set_translation_pair(interaction.guild.id, channel_1.id, channel_2.id, lang_1, lang_2)
        await interaction.response.send_message(
            f"✅ Rota criada: {channel_1.mention} <-> {channel_2.mention} (lang_1: `{lang_1}` (lang_2: `{lang_2}`)",
            ephemeral=True,
        )

# Deleta a rota de tradução configurada da base de dados, primeiro verificando possíveis conflitos para isso

    @app_commands.command(name="tr_remove", description="Remove uma par de tradução automática (channel_1 <-> channel_2).")
    @app_commands.describe(
        channel_1="Canal 1",
        channel_2="Canal 2"
    )
    async def tr_remove(self, interaction: discord.Interaction, channel_1: discord.TextChannel, channel_2: discord.TextChannel):
        if not interaction.guild:
            await interaction.response.send_message("Use em um servidor.", ephemeral=True)
            return
        if not _is_admin(interaction):
            await interaction.response.send_message("Sem permissão (requer **Gerenciar servidor**).", ephemeral=True)
            return

        removed = await remove_translation_pair(interaction.guild.id, channel_1.id, channel_2.id)
        if removed:
            msg = f"🗑️ Par removida: {channel_1.mention} <-> {channel_2.mention}"
        else:
            msg = f"⚠️ Não achei esse par: {channel_1.mention} <-> {channel_2.mention}"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="tr_list", description="Lista os pares de tradução automática configuradas no servidor.")
    async def tr_list(self, interaction: discord.Interaction):

# Verifica se o comando foi usado em um servidor

        if not interaction.guild:
            await interaction.response.send_message("Use em um servidor.", ephemeral=True)
            return

# Verifica se existem rotas configuradas no servidor

        pairs = await list_translation_pairs(interaction.guild.id)
        if not pairs:
            await interaction.response.send_message("Nenhum par configurada ainda.", ephemeral=True)
            return

# Lista as rotas configuradas dentro do servidor

        lines = []
        for ch1_id, ch2_id, lang_1, lang_2 in pairs:
            lines.append(f"<#{ch1_id}> ({lang_1}) <-> <#{ch2_id}> ({lang_2})")

        embed = discord.Embed(title="🌐 Pares de tradução")
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TranslateRoutesCog(bot))
