import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import discord
from discord.ext import commands
from dotenv import load_dotenv
from gerentiu.db import init_db, increment_channel_count

#importa as bibliotecas 'os' e 'discord' para serem utilizadas no codigo

COGS = (
    "gerentiu.cogs.moderation",
    "gerentiu.cogs.anti_raid",
    "gerentiu.cogs.stats",
    "gerentiu.cogs.translation_hubs",
    "gerentiu.cogs.translation_listener",
    "gerentiu.cogs.config_panel",
    "gerentiu.cogs.help"
)

#modulos separados do bot (cogs). Sendo moderation e stats no momento. Eles sao carregados
#dinamicamente na inicializacao atraves de load_extension() dentro do setup_hook().

class GerentiuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True  # Server and channel state used by commands and hubs.
        intents.members = True  # Privileged: member join events used by anti-raid.
        intents.messages = True  # Message events used by stats, anti-spam and translation.
        intents.message_content = True  # Privileged: content, embeds and attachments.
        super().__init__(command_prefix="!", intents=intents)

#GerentiuBot e a classe criada, com os eventos que o bot quer receber do Discord
#quais eventos o bot pode receber. A parte do '_init_' e a parte que configura tudo e
#entrega para a classe mae, o 'commands.Bot' que foi substituido pelo 'GerentiuBot'

    async def setup_hook(self):
        await init_db()

#Inicializa o banco de dados e espera que a tarefa seja completada

        for ext in COGS:
            await self.load_extension(ext)

#Carrega dinamicamente cada cog listado em COGS
        await self.tree.sync()

#Sincroniza slash commands globalmente com a API do Discord

    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        await increment_channel_count(message.guild.id, message.channel.id)

        await self.process_commands(message)

#Quando recebe um evento do Gateway do Discord, filtra se for de bot ou
#uma mensagem que nao seja de servidor

def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN não encontrado no .env")

#Carrega o DISCORD_TOKEN do arquivo '.env' e verifica se ele est[a definido

    bot = GerentiuBot()
    bot.run(token)

#Inicializa o bot, com a instancia chamada de 'GerentiuBot',
# utilizando o token anteriormente deifinido

if __name__ == "__main__":
    main()

#Garante que o 'main()' seja executado apenas quando o arquivo for rodado diretamente
