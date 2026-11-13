# PlayCHL Power Rankings — Standalone Discord Bot

This separate CHL Discord bot tracks completed games in a SQLite database, calculates weekly and season-weighted rankings, provides NHL analyst-style team write-ups, and publishes Saturdays at noon Eastern by default.

## Data source
PlayCHL's schedule is dynamically rendered. The Playwright parser is best-effort and has not yet been verified on Railway. Use /powerrefresh to test. If it fails, configure GAMES_JSON_URL to an HTTPS JSON feed or import verified historical results with /powerimport using games.example.json. Never invent missing scores.

## Formula
- 40% weekly win percentage
- 20% season win percentage
- 15% weekly goal differential per game
- 15% strength of schedule
- 10% recent weekly momentum

Week: Sunday through Saturday, America/New_York. OT losses count for half-points. Forfeits count in win/loss but not scoring totals. Idle teams incur a 12-point penalty. Game records persist between weeks.

## Discord setup
Create a NEW application in https://discord.com/developers/applications for this separate bot. Do not reuse your stats or availability bot token. Install it into your league server with bot and applications.commands scopes and View Channels, Send Messages, Embed Links, Read Message History permissions.

## Railway setup
Deploy this GitHub repository as a separate Railway service. The Dockerfile installs Python packages and Chromium; no HTTP domain is needed. Mount a persistent volume at /data and use a single replica.
Set Railway variables:
- DISCORD_TOKEN: your new bot's secret token (never commit)
- GUILD_ID: Discord server ID
- RANKINGS_CHANNEL_ID: channel for Saturday public posts
- DATABASE_PATH=/data/power_rankings.sqlite3
- PUBLISH_DAY=Saturday
- PUBLISH_HOUR=12
- PUBLISH_MINUTE=0
- POLL_MINUTES=30
- OPENAI_API_KEY: optional, for AI-generated write-ups (may incur API costs)
- OPENAI_MODEL=gpt-4.1-mini: optional; check account availability
- GAMES_JSON_URL: optional HTTPS feed if PlayCHL scraping fails
- ADMIN_ROLE_ID: optional

## Commands
| Command | Purpose |
|---|---|
| /powerrankings | Latest published list or a preview |
| /powerteam WSH | Team report |
| /powercompare WSH BUF | Compare teams |
| /powermovers | Movers up and down |
| /powerhistory | Past published rankings |
| /powerrefresh | Admin: fetch completed PlayCHL games |
| /powerimport | Admin: import completed game JSON attachment |
| /powerpublish | Admin: manually publish this week once |

Admin permissions require Manage Server or ADMIN_ROLE_ID.

## Missing history
Import an array of games following games.example.json. Each game needs a UTC date, teams, scores, Final or Forfeit status; stable unique IDs help avoid duplicates. Only import genuine results. Historical game data is preserved even if no longer on the website.

## Local tests
1. python -m pip install -r requirements.txt
2. python -m playwright install chromium
3. python -m unittest discover -s tests -v
4. Configure .env from .env.example (do not commit secrets)
5. python bot.py

## Limitations
The PlayCHL browser parser may need updates. Published snapshots are frozen and cannot automatically be overwritten; a partially failed post may require manual review to prevent duplicate posting. Rankings are calculated from saved results, never invented by AI. If the AI key is absent, factual template write-ups are used.
