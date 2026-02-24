import discord
from discord import app_commands
from discord.ext import commands

from gerentiu.db import get_guild_totals

class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Estatísticas básicas de mensagens por canal.")
    async def stats(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Use este comando em um servidor.", ephemeral=True)
            return

        total, per_channel = await get_guild_totals(interaction.guild.id)

        top = per_channel[:10]
        lines = []
        for channel_id, count in top:
            ch = interaction.guild.get_channel(channel_id)
            name = ch.mention if ch else f"<#{channel_id}>"
            lines.append(f"{name}: **{count}**")

        embed = discord.Embed(title="📊 Estatísticas do servidor")
        embed.add_field(name="Total (canais rastreados)", value=f"**{total}**", inline=False)
        embed.add_field(name="Top canais", value="\n".join(lines) if lines else "Sem dados ainda.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
