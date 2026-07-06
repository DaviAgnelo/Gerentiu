# Gerentiu

Gerentiu is a Discord administrative bot designed to provide moderation tools and translation features for Discord servers.

This repository contains the current public development version (v1.0)

---

## Features

- Modular command structure (cogs)
- Moderation tools
- Server statistics
- Translation routing
- SQLite database integration
- Local simmetric translation relaying with ArgosTranslate
- Webhooks integration for mirroring channels
- Antispam system for server moderation
- Antiraid system
- Configuration Panel for ease of use

---

## Current Project Structure
```
src/
└── gerentiu/
├── bot.py
├── db.py
└── cogs/
    └── stats.py
    ├── moderation.py
    ├── translation_pais.py
    ├── translation_listener.py
    ├── webhooks_utils.py
    ├── translation_listener.py
    ├── antispam.py
    ├── config_panel.py
    ├── help.py
    ├── raid_detector.py
    └── anti_raid.py
```
## To use Gerentiu (using Debian in this example)

1. Create virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```
3. Install dependencies
```bash
pip install -r requirements.txt
```
3. Configure environment variables
```bash
Create a .env file based on .env.example -> DISCORD_TOKEN=your_token_here
```
4. Running the bot
```bash
python src/gerentiu/bot.py
```
## Security Notice
Never commit or publish your .env file or Discord token.

```markdown
## Current Roadmap

- [x] Local translation engine
- [ ] API translation fallback
- [x] Webhooks for mirrored translation between channels
- [ ] Docker support
- [ ] Deployment automation
- [x] Expanded administrative tools
```

## Author

Developed by Davi Agnelo de Araujo Filho
