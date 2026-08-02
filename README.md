# Gerentiu

Gerentiu is a Discord administration bot focused on moderation, multilingual communities and a guided server-management experience. Version 1.0 combines progressive anti-spam, configurable anti-raid protection and webhook-based translation hubs without requiring the Discord `Administrator` permission.

## Highlights

- Interactive `/config` panel with selectors and presets instead of manual IDs.
- Progressive anti-spam detection across one or multiple channels.
- Anti-raid detection based on mass joins, new accounts and suspicious messages.
- Reversible text-channel lockdown with the previous permission state stored in SQLite.
- Symmetric translation hubs that preserve display names, avatars, replies, embeds and attachments.
- Local translation through Argos Translate, with a safe MyMemory fallback when a pair is unavailable.
- Forced fallback for Spanish to English (`es -> en`) because of the known Argos issue for that pair.
- Explicit translation-route logs showing whether Argos or the fallback handled each message.
- Message statistics per server and channel.

## Project structure

```text
Gerentiu/
├── .github/workflows/ci.yml
├── docs/permissions.md
├── tests/
│   ├── test_permission_policy.py
│   └── test_raid_detector.py
├── .env.example
├── README.md
└── src/
    ├── requirements.txt
    └── gerentiu/
        ├── bot.py
        ├── db.py
        ├── permission_policy.py
        ├── scripts/
        │   └── install_langpacks.py
        └── cogs/
            ├── anti_raid.py
            ├── config_panel.py
            ├── help.py
            ├── moderation.py
            ├── raid_detector.py
            ├── stats.py
            ├── translation_hubs.py
            ├── translation_listener.py
            └── webhooks_utils.py
```

## Requirements

- Python 3.10 or newer.
- A Discord application with a bot token.
- The **Server Members Intent** and **Message Content Intent** enabled in the Discord Developer Portal.
- Internet access when the MyMemory fallback is needed.

Presence Intent is not used. Gerentiu follows a least-privilege model and must not receive the `Administrator` permission. See [the permission guide](docs/permissions.md) for the permissions required by each feature.

## Installation

```bash
git clone https://github.com/DaviAgnelo/Gerentiu.git
cd Gerentiu
python -m venv .venv
```

Activate the virtual environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install -r src/requirements.txt
```

Create `.env` from the example and replace the placeholder token:

```bash
# Linux/macOS
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Optional: install the Argos language packs listed by the project. This downloads multiple language models and can take some time.

```bash
python src/gerentiu/scripts/install_langpacks.py
```

Run Gerentiu:

```bash
python src/gerentiu/bot.py
```

## Configuration

The recommended administration entrypoint is `/config`. The panel manages:

- Anti-spam status, message thresholds, detection window and maximum punishment.
- Anti-raid status, mass-join thresholds, alert channel, action and lockdown duration.
- Translation hub creation, channel/language assignment, channel removal and hub deletion.

Administrators using configuration commands need Discord's **Manage Server** permission. This is separate from `Administrator` and does not need to be granted to the bot.

Translation fallback settings are optional:

```dotenv
GERENTIU_TRANSLATION_FALLBACK_URL=https://api.mymemory.translated.net/get
GERENTIU_TRANSLATION_FALLBACK_EMAIL=your-email@example.com
```

If the URL is omitted, the MyMemory endpoint above is used automatically. The email is optional and is sent only as MyMemory's `de` parameter.

## Validation

The repository includes a lightweight CI workflow. Run the same checks locally with:

```bash
python -m compileall -q src
python -m unittest discover -s tests -v
```

These checks validate Python syntax and the core anti-raid state transitions. A real Discord-server smoke test is still recommended before production deployment.

## Security and privacy

- Never commit `.env`, bot tokens or the runtime SQLite database.
- Keep the Gerentiu role below trusted administration roles and above only the members it must moderate.
- Grant channel permissions only where the corresponding feature is used.
- Translation fallback sends the text being translated to the configured external API when Argos cannot handle the pair.

## Status

- [x] Local Argos translation engine
- [x] Safe API translation fallback
- [x] Webhook-based translation hubs
- [x] Progressive anti-spam
- [x] Anti-raid alerts and reversible lockdown
- [x] Guided administration panel
- [x] Lightweight continuous integration
- [ ] Container image and Docker Compose
- [ ] Automated deployment

## Author

Developed by Davi Agnelo de Araujo Filho.
