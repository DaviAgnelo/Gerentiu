import discord
from io import BytesIO

WEBHOOK_CACHE: dict[int, discord.Webhook] = {}

async def get_or_create_webhook(channel: discord.TextChannel) -> discord.Webhook:
    cached = WEBHOOK_CACHE.get(channel.id)
    if cached is not None:
        return cached

    try:
        hooks = await channel.webhooks()
    except discord.Forbidden:
        raise RuntimeError(f"Sem permissão para listar webhooks no canal {channel.id}")

    for hook in hooks:
        if hook.name == "Gerentiu Mirror":
            WEBHOOK_CACHE[channel.id] = hook
            return hook
    try:
        webhook = await channel.create_webhook(name="Gerentiu Mirror")
    except discord.Forbidden:
        raise RuntimeError(f"Sem permissão para criar webhook no canal {channel.id}")
    WEBHOOK_CACHE[channel.id] = webhook
    return webhook

def safe_webhook_username(user: discord.abc.User | discord.Member) -> str:
    name = getattr(user, "display_name", None) or user.name
    name = name.strip()
    return (name[:80] if len(name) > 80 else name) or "Usuário"

async def build_files_from_attachments(message: discord.Message) -> list[discord.File]:
    files = []

    for attachment in message.attachments[:10]:
        data = await attachment.read()
        fp = BytesIO(data)
        files.append(discord.File(fp, filename=attachment.filename))

    return files

async def mirror_via_webhook(
    source_message: discord.Message,
    target_channel: discord.TextChannel,
    translated_text: str
) -> None:
    webhook = await get_or_create_webhook(target_channel)
    files = await build_files_from_attachments(source_message)

    final_content = translated_text

    send_kwargs = {
        "content": final_content or None,
        "username": safe_webhook_username(source_message.author),
        "avatar_url": source_message.author.display_avatar.url,
        "allowed_mentions": discord.AllowedMentions.none(),
    }

    if source_message.embeds:
        send_kwargs["embeds"] = source_message.embeds
    if files:
        send_kwargs["files"] = files
    if not final_content and not files and not source_message.embeds:
        return
    try:
        await webhook.send(**send_kwargs)
    except discord.HTTPException:
        WEBHOOK_CACHE.pop(target_channel.id, None)

        webhook = await get_or_create_webhook(target_channel)
        send_kwargs.pop("embeds", None)
        await webhook.send(**send_kwargs)
