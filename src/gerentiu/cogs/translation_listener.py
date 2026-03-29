import asyncio
import discord
import re
from discord.ext import commands
from argostranslate import translate
from gerentiu.db import get_translation_pair_by_channel
from gerentiu.cogs.webhooks_utils import mirror_via_webhook
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
URL_RE = re.compile(r'http?://\S+')
MENTION_RE = re.compile(r'<@!?\d+>|<@&\d+>|<#\d+>')
PLAIN_MENTION_RE = re.compile(r'(?<!\w)@(everyone|here)\b')

def protect_special_tokens(text: str):
    placeholders = []
    index = 0

    def make_replacer(prefix):
        def repl(match):
            nonlocal index
            token = f"ZXQ{prefix}{index}QXZ"
            placeholders.append((token, match.group(0)))
            index += 1
            return token
        return repl

    text = URL_RE.sub(make_replacer("URL"), text)
    text = MENTION_RE.sub(make_replacer("TAG"), text)
    text = PLAIN_MENTION_RE.sub(make_replacer("PING"), text)
    text = CUSTOM_EMOJI_RE.sub(make_replacer("EMJ"), text)
    text = UNICODE_EMOJI_RE.sub(make_replacer("EMJ"), text)

    return text, placeholders

def normalize_lang(code: str) -> str:
    if not code:
        return ""
    code = code.lower().strip().replace("_", "-")
    return code.split("-")[0]

def restore_special_tokens(text: str, placeholders):
    for token, original in placeholders:
        text = text.replace(token, original)
    return text

class TranslationListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_translatable_text(self, text:str) -> bool:
        return any(ch.isalnum() for ch in text )
    async def build_reply_context(self, message: discord.Message, src_lang: str, dst_lang: str) -> str:
        if message.reference is None or message.reference.message_id is None:
            return ""

        try:
            referenced = message.reference.resolved

            if referenced is None or not isinstance(referenced, discord.Message):
                ref_channel = message.channel
                if getattr(message.reference, "channel_id", None):
                    ref_channel = self.bot.get_channel(message.reference.channel_id) or message.channel

                referenced = await ref_channel.fetch_message(message.reference.message_id)

            raw_snippet = referenced.content.strip() if referenced.content else "[anexo|embed]"
            raw_snippet = raw_snippet[:120]

            protected_snippet, protected_map = protect_special_tokens(raw_snippet)

            src_lang = normalize_lang(src_lang)
            dst_lang = normalize_lang(dst_lang)

            translated_snippet = None

            translated_snippet = await asyncio.to_thread(
                translate.translate,
                protected_snippet,
                src_lang,
                dst_lang
            )

            snippet = restore_special_tokens(
                (translated_snippet or "").strip(),
                protected_map
            ) or raw_snippet

            return f"> **{referenced.author.display_name}**: {snippet}\n"

        except Exception as e:
            import traceback
            print(f"Erro em build_reply_context: {e!r}")
            traceback.print_exc()
            return ""

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

        reply_context = await self.build_reply_context(message, src_lang, dst_lang)

        text = message.content or ""
        protected_text, protected_map = protect_special_tokens(text)
        translated = None

#        translated = f"([DEBUG] {src_lang} <-> {dst_lang}) {text} "

        if not text.strip() and not message.attachments:
            return

#        print(f"[DEBUG] original={repr(text)}")

        if self.has_translatable_text(text):
#            try:
#                translated = await asyncio.to_thread(
#                    self.translator.translate,
#                    protected_text,
#                    src_lang,
#                    dst_lang
#                )

            src_lang = normalize_lang(src_lang)
            dst_lang = normalize_lang(dst_lang)

            try:
                translated = await asyncio.to_thread(
                    translate.translate,
                    protected_text,
                    src_lang,
                    dst_lang
                )
            except Exception as e:
                print(f"Erro na tradução: {e}")
                translated = None

        final_text = (translated or "").strip()
        final_text = restore_special_tokens(final_text, protected_map)

        if not final_text:
            final_text = text
        if reply_context:
            final_text = reply_context + final_text

#        print(f"[DEBUG] translated={(translated)}")
        target_channel = self.bot.get_channel(target_channel_id)

#        print(f"[DEBUG] target_channel resolvido: {target_channel}")
        if target_channel:
            await mirror_via_webhook(message, target_channel, final_text)

async def setup(bot: commands.Bot):
#    print("[DEBUG] carregando TranslationLiternerCog")
    await bot.add_cog(TranslationListenerCog(bot))

