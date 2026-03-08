import asyncio
import discord
from discord.ext import commands
from argostranslate import translate
from gerentiu.db import get_translation_targets

class TranslationListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.content.strip():
            return
        routes = await get_translation_targets(message.guild.id, message.channel.id)
        if not routes:
            return
        for target_channel_id, src_lang, dst_lang in routes:
            text = message.content.strip()
            translated = await asyncio.to_thread(
                translate.translate,
                text,
                src_lang,
                dst_lang
                )
            target_channel = self.bot.get_channel(target_channel_id)
            if target_channel:
                await target_channel.send(f"🌐 **{message.author.display_name}**:\n{translated}")

async def setup(bot: commands.Bot):
    await bot.add_cog(TranslationListenerCog(bot))
