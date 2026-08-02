# Discord permissions

Gerentiu follows a least-privilege model. The bot must never require or be granted Discord's `Administrator` permission.

## Gateway intents

Enable these privileged intents in **Discord Developer Portal -> Bot -> Privileged Gateway Intents**:

- **Server Members Intent**: required by the anti-raid member-join listener.
- **Message Content Intent**: required by anti-spam and translation mirroring.

Presence Intent is not used.

## OAuth scopes

Use both scopes when installing the bot:

- `bot`
- `applications.commands`

Members who invoke slash commands also need **Use Application Commands** in the relevant channel.

## Bot permissions by feature

| Feature | Required bot permissions |
| --- | --- |
| Commands, help, statistics and alerts | View Channels, Send Messages, Embed Links, Read Message History |
| Translation source channels | View Channels, Read Message History |
| Translation target channels | View Channels, Manage Webhooks; Attach Files when attachments are mirrored |
| Anti-spam with `warn` or `delete` maximum | Manage Messages |
| Anti-spam with `timeout` maximum | Manage Messages, Moderate Members |
| Anti-spam with `kick` maximum | Manage Messages, Moderate Members, Kick Members |
| Anti-spam with `ban` maximum | Manage Messages, Moderate Members, Kick Members, Ban Members |
| Anti-raid in `alert` mode | Base message permissions only |
| Anti-raid in `lockdown` mode | Manage Channels, plus base message permissions in the alert channel |

Anti-spam punishments are progressive. For example, a `ban` maximum can pass through timeout and kick on earlier strikes, so the permissions for those actions are also required.

## Administrator-facing permissions

People who change Gerentiu settings through `/config`, `/antispam`, `/antiraid` or translation-hub management need **Manage Server**. They do not need Discord's `Administrator` permission.

## Role hierarchy and channel overrides

- Place Gerentiu's highest role above the members it may time out, kick or ban.
- Keep trusted administrator roles above Gerentiu.
- Check channel overrides: an explicit denial can prevent messages, webhook management or lockdown changes even when the server role grants them.
- Grant **Manage Webhooks** only in translation target channels when tighter channel-level control is desired.
- Grant **Manage Channels** only when anti-raid lockdown is enabled.

This behavior is intentional: without `Administrator`, Discord permission boundaries remain effective and a server owner controls exactly where Gerentiu can operate.
