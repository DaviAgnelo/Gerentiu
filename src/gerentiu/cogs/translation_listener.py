import asyncio
import discord
from discord.ext import commands
from argostranslate import translate
from gerentiu.db import get_translation_pair_by_channel
from gerentiu.cogs.webhooks_utils import mirror_via_webhook

class TranslationListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    def has_translatable_text(self, text:str) -> bool:
        return any(ch.isalnum() for ch in text )

# Filtros básicos para evitar processamento desnecessário

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
#        print("{DEBUG} translation_listener on_message disparou")

        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.content.strip() and not message.attachments:
            return
        if message.webhook_id is not None:
            return
        pair = await get_translation_pair_by_channel(message.guild.id, message.channel.id)
#        print(f"[DEBUG] pair encontrado: {pair}")
        if pair is None:
            return

# Depois dos filtros, é feito a tradução baseado em quais idiomas são a fonte e destino, enviando o autor e a mensagem traduzida
# no canal de destino

        ch1, ch2, lang_1, lang_2 = pair

#        print(f"[DEBUG] message.channel.id={message.channel.id} ({type(message.channel.id)}")
#        print(f"[DEBUG] ch1={ch1} ({type(ch1)}) | ch2={ch2} ({type(ch2)})")

        if int(message.channel.id) == int(ch1):
            target_channel_id = ch2
            src_lang = lang_1
            dst_lang = lang_2
        elif int(message.channel.id) == int(ch2):
            target_channel_id = ch1
            src_lang = lang_2
            dst_lang = lang_1
        else:
#            print("[DEBUG] caiu no else: channel.id não bateu com ch1, nem ch2")
            return

#        print(f"[DEBUG] direção: {src_lang} -> {dst_lang} | target_channel_id={target_channel_id}")

        text = message.content or ""

#        translated = f"([DEBUG] {src_lang} <-> {dst_lang}) {text} "

        if not text.strip() and not message.attachments:
            return

        if self.has_translatable_text(text):
            translated = await asyncio.to_thread(
                translate.translate,
                text,
                src_lang,
                dst_lang
            )

            final_text = (translated or "").strip()

            if not final_text:
                final_text = text
        else:
            final_text = text

        target_channel = self.bot.get_channel(target_channel_id)

        target_channel = self.bot.get_channel(target_channel_id)
#        print(f"[DEBUG] target_channel resolvido: {target_channel}")
        if target_channel:
            await mirror_via_webhook(message, target_channel, final_text)

async def setup(bot: commands.Bot):
#    print("[DEBUG] carregando TranslationLiternerCog")
    await bot.add_cog(TranslationListenerCog(bot))
