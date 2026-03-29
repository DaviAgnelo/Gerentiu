from gerentiu.db import get_antispam_config
import discord
from discord.ext import commands
from collections import defaultdict, deque
import time

class AntispamCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_message_history = defaultdict(lambda: deque(maxlen=15))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        config = await get_antispam_config(message.guild.id)
        if not config["enabled"]:
            return
        await self.verify_spam(message, config)

    async def verify_spam(self, message: discord.Message, config: dict):
        guild_id = message.guild.id
        user_id = message.author.id
        key = (guild_id, user_id)

        interval_seconds = config["interval_seconds"]
        max_messages = config["max_messages"]

        now = time.time()
        history = self.user_message_history[key]
        history.append(now)

        recent_messages = [ts for ts in history if now - ts <= interval_seconds]

        if len(recent_messages) >= max_messages:
            await message.channel.send(
                f"{message.author.mention}, stop flooding the channel. This is a warning: {config['action']}"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(AntispamCog(bot))
