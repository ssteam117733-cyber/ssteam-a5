import os
import requests
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL")

OWNER_ID = 6374332180  # apni telegram id

# DATABASE
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS serial_logs (user_id INTEGER, serial TEXT)")
conn.commit()


# HELP / PANEL
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    await update.message.reply_text(
"""
⚙️ ADMIN PANEL

Approve User:
/approve_user USERID

Remove User:
/remove_user USERID

Ban User:
/ban_user USERID

Unban User:
/unban_user USERID

Show Logs:
/logs

Total Users:
/users
"""
    )


# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    banned = cursor.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,)).fetchone()

    if banned:
        await update.message.reply_text("🚫 You are banned.")
        return

    approved = cursor.execute("SELECT * FROM approved_users WHERE user_id=?", (user_id,)).fetchone()

    if approved:
        await update.message.reply_text(
"""✅ ACCESS GRANTED

Send Serial Number directly to register."""
        )
        return

    await update.message.reply_text(
"""⏳ ACCESS PENDING

Your account needs approval.

Contact owner:
@ilcapo_7"""
    )

    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"""
NEW USER REQUEST

User: @{username}
ID: {user_id}

/approve_user {user_id}
"""
        )
    except:
        pass


# SERIAL REGISTER
async def serial_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    serial = update.message.text.strip()

    banned = cursor.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,)).fetchone()

    if banned:
        await update.message.reply_text("🚫 You are banned.")
        return

    approved = cursor.execute("SELECT * FROM approved_users WHERE user_id=?", (user_id,)).fetchone()

    if not approved:
        await update.message.reply_text(
"""⛔ ACCESS DENIED

Approval required.

Owner:
@ilcapo_7"""
        )
        return

    try:

        response = requests.post(
            f"{API_URL}/api/register",
            json={
                "serial": serial,
                "telegram_id": user_id
            },
            timeout=20
        )

        if response.status_code == 200:

            cursor.execute("INSERT INTO serial_logs VALUES (?,?)", (user_id, serial))
            conn.commit()

            await update.message.reply_text(
f"""✅ SERIAL REGISTERED

Serial:
{serial}"""
            )

            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"📜 SERIAL LOG\nUser:{user_id}\nSerial:{serial}"
                )
            except:
                pass

        elif response.status_code == 400:

            await update.message.reply_text(
f"""⚠️ DUPLICATE SERIAL

{serial}"""
            )

        else:

            await update.message.reply_text("❌ Registration failed")

    except:
        await update.message.reply_text("⚠️ Server error")


# APPROVE USER
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    user_id = int(context.args[0])

    cursor.execute("INSERT INTO approved_users VALUES (?)", (user_id,))
    conn.commit()

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 You are approved. Send serial to register."
        )
    except:
        pass

    await update.message.reply_text("✅ User Approved")


# REMOVE USER
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    user_id = int(context.args[0])

    cursor.execute("DELETE FROM approved_users WHERE user_id=?", (user_id,))
    conn.commit()

    await update.message.reply_text("User removed")


# BAN USER
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    user_id = int(context.args[0])

    cursor.execute("INSERT INTO banned_users VALUES (?)", (user_id,))
    conn.commit()

    await update.message.reply_text("🚫 User banned")


# UNBAN USER
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    user_id = int(context.args[0])

    cursor.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
    conn.commit()

    await update.message.reply_text("User unbanned")


# LOGS
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    data = cursor.execute("SELECT * FROM serial_logs ORDER BY rowid DESC LIMIT 10").fetchall()

    text = "📜 LAST SERIAL LOGS\n\n"

    for row in data:
        text += f"User:{row[0]}\nSerial:{row[1]}\n\n"

    await update.message.reply_text(text)


# USERS COUNT
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    total = cursor.execute("SELECT COUNT(*) FROM approved_users").fetchone()[0]

    await update.message.reply_text(f"👥 Approved Users: {total}")


# BOT
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("panel", panel))

app.add_handler(CommandHandler("approve_user", approve_user))
app.add_handler(CommandHandler("remove_user", remove_user))
app.add_handler(CommandHandler("ban_user", ban_user))
app.add_handler(CommandHandler("unban_user", unban_user))
app.add_handler(CommandHandler("logs", logs))
app.add_handler(CommandHandler("users", users))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, serial_handler))

app.run_polling(drop_pending_updates=True, timeout=60)
