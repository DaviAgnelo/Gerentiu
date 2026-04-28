import asyncio
import discord
import re
from discord.ext import commands
from argostranslate import translate
from gerentiu.db import get_translation_hub_by_channel
from gerentiu.cogs.webhooks_utils import mirror_via_webhook
from collections import defaultdict
#from gerentiu.cogs.nllb_translator import NLLBTranslator

CUSTOM_EMOJI_RE = re.compile(r'<a?:\w+:\d+>')
UNICODE_EMOJI_RE = re.compile(
    r'['
    r'\U0001F300-\U0001F5FF'
    r'\U0001F600-\U0001F64F'
    r'\U0001F680-\U0001F6FF'
    r'\U0001F700-\U0001F77F'
    r'\U0001F780-\U0001F7FF'
    r'\U0001F800-\U0001F8FF'
    r'\U0001F900-\U0001F9FF'
    r'\U0001FA00-\U0001FA6F'
    r'\U0001FA70-\U0001FAFF'
    r'\u2600-\u26FF'
    r'\u2700-\u27BF'
    r']',
    flags=re.UNICODE
)
#Plese, don't touch any of this, these are the Unicodes for the most common emojis, if you change any of this... good luck
URL_RE = re.compile(r'http?://\S+')
MENTION_RE = re.compile(r'<@!?\d+>|<@&\d+>|<#\d+>')
PLAIN_MENTION_RE = re.compile(r'(?<!\w)@(everyone|here)\b')
#This here just recompiles the emojis back from Unicode, don't touch this or I will pull your leg while you sleep

def needs_special_token_protection(text: str) -> bool:
    return (
        "http://" in text
        or "https://" in text
        or "<@" in text
        or "<#" in text
        or "<:" in text
        or "<a:" in text
        or "@everyone" in text
        or "@here" in text
        or bool(UNICODE_EMOJI_RE.search(text))
    )
#If anything contains this, PROTECT IT

def sub_with_prefix(pattern, prefix, text, placeholders, counter):
    def repl(match):
        idx = counter[0]
        token = f"ZXQ{prefix}{idx}QXZ"
        placeholders.append((token, match.group(0)))
        counter[0] += 1
        return token
    return pattern.sub(repl, text)
#This function here protects the position of an emoji by placing a placeholder if it's place

def protect_special_tokens(text:str):
    placeholders = []
    counter = [0]

    text = sub_with_prefix(URL_RE, "URL", text, placeholders, counter)
    text = sub_with_prefix(MENTION_RE, "TAG", text, placeholders, counter)
    text = sub_with_prefix(PLAIN_MENTION_RE, "PING", text, placeholders, counter)
    text = sub_with_prefix(CUSTOM_EMOJI_RE, "EMJ", text, placeholders, counter)
    text = sub_with_prefix(UNICODE_EMOJI_RE, "EMJ", text, placeholders, counter)

    return text, placeholders
#This is the function called when needs_special_token_protection flags a message as containing special tokens

def normalize_lang(lang: str) -> str:
    return (lang or "").strip().lower()

def restore_special_tokens(text: str, placeholders):
    for token, original in reversed(placeholders):
        text = text.replace(token, original)
    return text
#Now retore the tokens that were protected

class TranslationListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.translation_hub_cache = {}
#Now comes the fun part

    async def get_cached_hub(self, guild_id: int, channel_id: int):
        key = (guild_id, channel_id)

        if key in self.translation_hub_cache:
            return self.translation_hub_cache[key]

        hub = await get_translation_hub_by_channel(guild_id, channel_id)

        if hub is not None:
            hub = {
                "hub_id": int(hub["hub_id"]),
                "hub_name": hub["hub_name"],
                "source_channel_id": int(hub["source_channel_id"]),
                "source_language": hub["source_language"],
                "targets": [
                    {
                        "channel_id": int(target["channel_id"]),
                        "language": target["language"],
                    }
                    for target in hub["targets"]
                ],
            }

        self.translation_hub_cache[key] = hub
        return hub
#This whole function's duty is to speed up translation by not needing to consult the DB every time someone sends
#a message, just be careful to remove it from cache if the pair was removed

    def invalidate_translation_hub_cache(self, guild_id: int, channel_ids: list[int] | None = None):
        if channel_ids is None:
            keys_to_remove = [
                key for key in self.translation_hub_cache
                if key[0] == guild_id
            ]
        else:
            channel_ids = set(channel_ids)
            keys_to_remove = [
                key for key in self.translation_hub_cache
                if key[0] == guild_id and key[1] in channel_ids
            ]
        for key in keys_to_remove:
            self.translation_hub_cache.pop(key, None)
#This is what I was talking about before, no bugs shall prevail today! (Only every day foward from tomorrow)

    def has_translatable_text(self, text:str) -> bool:
        return bool(text) and any(ch.isalnum() for ch in text)
#Does the message have text? No? don't try it then

    def format_reply_block(self, author_name: str, snippet: str) -> str:
        snippet = (snippet or "").strip()
        if not snippet:
            snippet = "[anexo/embed]"

        MAX_LINES = 5

        lines = snippet.splitlines()

        if len(lines) > MAX_LINES:
            lines = lines[:MAX_LINES]
            lines.append("...")

        quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in lines)
        return f"> **{author_name}**: {quoted}"
#This was a request made from some people that wanted replies on the mirroring channels, this is a very
#delicate function, don't touch it if you want to be sane... it shows what message the person is replying to

    def smart_trim(self, text: str, max_len: int = 120) -> str:
        text = text.strip()

        if max_len <= 3:
            return text[:max_len]

        if len(text) <= max_len:
            return text

        return text[:max_len - 3].rstrip() + "..."
#Smart. Clean cut. No gigantic reply here

    async def build_reply_context(self, message: discord.Message, src_lang: str, dst_lang: str) -> str:
        if message.reference is None or message.reference.message_id is None:
            return ""
#If the message is not a reply, don't bother with all of this

        try:
            referenced = message.reference.resolved

            if referenced is None or not isinstance(referenced, discord.Message):
                ref_channel = message.channel
                if getattr(message.reference, "channel_id", None):
                    ref_channel = self.bot.get_channel(message.reference.channel_id) or message.channel

                referenced = await ref_channel.fetch_message(message.reference.message_id)

            raw_snippet = referenced.content.strip() if referenced.content else "[anexo|embed]"
#If the message being replyed has text in it, show it, if not, show THE STRING
            raw_snippet = self.smart_trim(raw_snippet, 120)
#Still smart
            if not self.has_translatable_text(raw_snippet):
                return self.format_reply_block(referenced.author.display_name, raw_snippet)
#Don't consume CPU if you don't need to translate it
            if not src_lang or not dst_lang:
                return ""
#If there's no src_lang or dst_lang, CANCEL IT BEFORE IT EXPLODES
            if src_lang == dst_lang:
                return self.format_reply_block(referenced.author.display_name, raw_snippet)
#Just like above, if it does not need to be translate, don't consume my CPU
            translated_snippet = None

            try:
                translated_snippet = await asyncio.to_thread(
                    translate.translate,
                    raw_snippet,
                    src_lang,
                    dst_lang
                )
            except Exception:
                translated_snippet = None
#Ok, you can translate now
            snippet = translated_snippet

            return self.format_reply_block(referenced.author.display_name, snippet)
#Finally, the reply is ready and being shipped
        except Exception as e:
            import traceback
            print(f"Error in build_reply_context: {e!r}")
            traceback.print_exc()
            return ""
#I've never seen this being printed in log, if you see, congratulations

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.webhook_id:
            return
        if not message.guild:
            return

        content = message.content or ""
        attachments = message.attachments

        if not content and not attachments:
            return

        if not attachments and not self.has_translatable_text(content) and not needs_special_token_protection(content):
            return

        hub = await self.get_cached_hub(message.guild.id, message.channel.id)
        if hub is None:
            return

        source_channel_id = hub["source_channel_id"]
        source_language = normalize_lang(hub["source_language"])
        targets = hub["targets"]

        if message.channel.id != source_channel_id:
            return

        if not targets:
            return

        text = message.content or ""

        if needs_special_token_protection(text):
            protected_text, protected_map = protect_special_tokens(text)
        else:
            protected_text, protected_map = text, []

        targets_by_lang = defaultdict(list)

        for target in targets:
            lang = normalize_lang(target["language"])
            targets_by_lang[lang].append(int(target["channel_id"]))

        for dst_lang, channel_ids in targets_by_lang.items():
            reply_context = ""
            if message.reference and message.reference.message_id:
                reply_context = await self.build_reply_context(
                    message,
                    source_language,
                    dst_lang,
                )

            translated = None

            if self.has_translatable_text(text) and source_language and dst_lang and source_language != dst_lang:
                try:
                    translated = await asyncio.to_thread(
                        translate.translate,
                        protected_text,
                        source_language,
                        dst_lang
                    )
                except Exception as e:
                    print(f"Erro na tradução ({source_language} -> {dst_lang}): {e}")
                    translated = None

            final_text = (translated or "").strip()
            final_text = restore_special_tokens(final_text, protected_map)

            if not final_text:
                final_text = final_text or text

            if reply_context:
                if final_text:
                    final_text = f"{reply_context}\n{final_text}"
                else:
                    final_text = reply_context

            for target_channel_id in channel_ids:
                target_channel = self.bot.get_channel(target_channel_id)
                if target_channel is None:
                    continue

                await mirror_via_webhook(message, target_channel, final_text)
async def setup(bot: commands.Bot):
#    print("[DEBUG] carregando TranslationLiternerCog")
    await bot.add_cog(TranslationListenerCog(bot))
