import discord
from discord import app_commands
from discord.ext import commands

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

# Cria a classe Moderation para montar o cog "Moderation"

    @app_commands.command(name="ping", description="Teste rápido do Gerentiu.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong ✅", ephemeral=True)

# Comando teste para verificar se o bot está respondendo

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))

# Inicializa o cog de Moderation
