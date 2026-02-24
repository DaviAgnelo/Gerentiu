import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from gerentiu.db import init_db, increment_channel_count, get_translation_targets

#importa as bibliotecas 'os' e 'discord' para serem utilizadas no codigo

COGS = (
    "gerentiu.cogs.moderation",
    "gerentiu.cogs.stats",
    "gerentiu.cogs.translation_routes",
)

#modulos separados do bot (cogs). Sendo moderation e stats no momento. Eles sao carregados
#dinamicamente na inicializacao atraves de load_extension() dentro do setup_hook().

class GerentiuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True #Recebe eventos em servidores
        intents.messages = True #Recebe eventos de mensagens (on_message, message_delete, etc.)
        intents.message_content = True #Nao le o conteudo das mensagens que recebe
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

        targets = await get_translation_targets(message.guild.id, message.channel.id)
        if targets:
            for target_channel_id, target_lang in targets:
                target_channel = message.guild.get_channel(target_channel_id)

                if target_channel:
                    await target_channel.send(
                        f"[FAKE -> {target_lang.upper()}] {message.content}"
                )

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
