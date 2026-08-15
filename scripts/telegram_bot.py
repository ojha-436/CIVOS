"""CIVOS Telegram bot — citizen intake via text, voice note and photo.

Proves the "messaging apps" requirement from PS-01 in five minutes.
Telegram is chosen over WhatsApp because it doesn't require Meta business
verification (plan.md §3.7 cut list). A documented WhatsAppAdapter stub is
in core/interfaces/channel_adapter.py.

Usage:
    TELEGRAM_BOT_TOKEN=<token> uv run python scripts/telegram_bot.py

Get a token: talk to @BotFather on Telegram and run /newbot.

Privacy:
  - Audio is transcribed by Gemini and then dropped.
  - Photos are analysed and the original dropped.
  - EXIF GPS resolves the district and is discarded.
  - Nothing identifying is stored (SPEC §11).
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Ensure the repo root is importable when run from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from api.extraction import extract
from api.geo import parse_exif_gps, resolve_district

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _format_result(result, district_name: str | None, geo_confidence: str) -> str:
    """Build the citizen-facing confirmation message."""
    sector_label = (result.sector or "unclassified").replace("_", " ").title()
    severity_dots = "●" * (result.severity or 0) + "○" * (5 - (result.severity or 0))
    lines = [
        "✓ *Received and structured.*",
        "",
    ]
    if result.raw_text:
        lines.append(f"*In your words:* {result.raw_text[:200]}")
    if result.translation and result.translation != result.raw_text:
        lines.append(f"*English:* {result.translation[:200]}")
    lines += [
        "",
        f"*Sector:* {sector_label}",
        f"*Severity:* {severity_dots}",
    ]
    if result.asset_type:
        flags = ", ".join(f.replace("_", " ") for f in result.condition_flags) if result.condition_flags else ""
        lines.append(f"*Asset:* {result.asset_type.replace('_', ' ')}" + (f" — {flags}" if flags else ""))
    if result.visual_description:
        lines.append(f"*Seen:* {result.visual_description[:200]}")

    loc = district_name or result.geo_hint or "unknown"
    lines.append(f"*Registered in:* {loc} _(geo: {geo_confidence})_")
    lines += [
        "",
        "_Your audio/photo has been analysed and deleted. No image or recording is stored._",
        "_If GPS was present, it was used once to find your district and then discarded._",
    ]
    return "\n".join(lines)


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *CIVOS citizen intake*\n\n"
        "Tell me what your area needs — by voice note, photo, or text.\n\n"
        "No form, no department jargon required. Just say what is wrong.",
        parse_mode="Markdown",
    )


async def handle_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Processing…", parse_mode="Markdown")
    try:
        result = extract(text=update.message.text)
        reply = _format_result(result, None, "inferred")
    except Exception as exc:
        reply = f"⚠️ Could not process: {exc}"
    await update.message.reply_text(reply, parse_mode="Markdown")


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Transcribing your voice note…", parse_mode="Markdown")
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    file = await ctx.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
        await file.download_to_drive(custom_path=tmp.name)
        audio_bytes = Path(tmp.name).read_bytes()
    try:
        result = extract(audio_bytes=audio_bytes, audio_mime="audio/ogg")
        reply = _format_result(result, None, "inferred")
    except Exception as exc:
        reply = f"⚠️ Could not process audio: {exc}"
    await update.message.reply_text(reply, parse_mode="Markdown")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Analysing your photo…", parse_mode="Markdown")
    photo = update.message.photo[-1]  # largest available
    file = await ctx.bot.get_file(photo.file_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        await file.download_to_drive(custom_path=tmp.name)
        image_bytes = Path(tmp.name).read_bytes()

    # EXIF GPS path (SPEC P0-6)
    district_name: str | None = None
    geo_confidence = "inferred"
    gps = parse_exif_gps(image_bytes)
    if gps:
        lat, lon = gps
        geo_result = resolve_district(lat, lon)
        if geo_result:
            district_name = f"{geo_result.name}, {geo_result.state}"
            geo_confidence = "high"

    caption = update.message.caption or ""
    try:
        result = extract(image_bytes=image_bytes, text=caption or None)
        reply = _format_result(result, district_name, geo_confidence)
    except Exception as exc:
        reply = f"⚠️ Could not process photo: {exc}"
    await update.message.reply_text(reply, parse_mode="Markdown")


def main() -> None:
    if not TOKEN:
        print("Set TELEGRAM_BOT_TOKEN environment variable first.")
        print("Get a token from @BotFather on Telegram: /newbot")
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("CIVOS Telegram bot running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
