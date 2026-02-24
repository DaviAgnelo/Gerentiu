# Gerentiu

Gerentiu is a Discord administrative bot designed to provide moderation tools and translation features (as of now...) for Discord servers.

This repository contains the current public development version (v0.3)

---

## Features

- Modular command structure (cogs)
- Moderation tools
- Server statistics
- Translation routing (WIP)
- SQLite database integration

---

## Current Project Structure

src/
└── gerentiu/
├── bot.py
├── db.py
└── cogs/

## To use Gerentiu (using Debian in this example)

1. Crete virtual environment
python -m venv .venv
source .venv/bin/activate

2. Install dependencies
pip install -r src/requirements.txt

3. Configure environment variables
Create a .env file based on .env.example -> DISCORD_TOKEN=your_token_here

4. Running the bot
python src/gerentiu/bot.py

## Security Notice
Never commit or publish your .env file or Discord token.

## Current Roadmap

- Local translation engine

- API translation fallback

- Webhooks for mirrored translation between channels

- Docker support

- Deployment automation

- Administrative tools

## Author

Developed by Davi Agnelo de Araujo Filho
