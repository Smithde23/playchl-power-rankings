# PlayCHL AI Game Recap Bot

An independent Discord service posting a full, fact-based game recap, a custom score-card PNG and an MP3 voiceover when a PlayCHL game goes Final. No gameplay footage is used.

## Source and factual safeguards

The PlayCHL schedule exposes dates, teams, scores, REG/Final/Forfeit. The bot uses exactly these facts plus team results calculated from other completed schedule games. It **does not claim goalscorers, assists, period scores, saves, turning points or three stars unless a verified per-game source becomes available**. Game recaps will be narrative summaries of the result, recent form and historical matchup outcomes. Forfeits are marked as administrative results, not described as on-ice gameplay.

Game final status is checked through Playwright. Records and post IDs are retained in a SQLite database on a Railway persistent volume. The first import **baselines** existing completed games to prevent flooding a channel with old recaps. New finals are auto-posted; a manual /recap_game command can post an already-finished game.

## Discord setup

Create a **new** Discord application and bot, install with bot + applications.commands scopes and View Channels, Send Messages, Embed Links, Attach Files, Read Message History permissions. Never reuse Power Rankings or Availability bot token.

## Railway service

This source lives in the existing GitHub repository under /recap-bot but must run as a **separate Railway service/project**, using the service root directory /recap-bot. Mount its own persistent volume at /data.

Set DISCORD_TOKEN, GUILD_ID, RECAP_CHANNEL_ID, DATABASE_PATH=/data/recaps.sqlite3. Optional: POLL_MINUTES=15, TTS_VOICE=en-US-GuyNeural, ENABLE_AUDIO=true.

Voice uses an external neural TTS endpoint via edge-tts, which may occasionally be unavailable; in that case a clear written recap and score graphic still post and the failure is logged. No OpenAI API key is required. Do not expect footage or player-specific claims.

## Commands
- /recap_recent — show latest 12 completed games and IDs
- /recap_game id:... — post a recap of one known completed game (requires Manage Server)
- /recap_status — count known games and successfully posted recaps
- /recap_refresh — force a scan for newly finished games (requires Manage Server)

New finals are polled automatically; deduplication ensures that repeated scans or restarts do not repost them.

## Limitations

Schedule HTML can change. A working schedule scraper does not guarantee period-by-period events or actual player statistics. Audio generation needs network access to the neural voice endpoint. Discord upload limits may vary.
