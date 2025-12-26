import os
import logging
import pymongo
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from telegram.error import BadRequest, Forbidden

# ================= LOGGING =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = [6335046711, 8552084416]

PUBLIC_CHANNEL = "-1003582278269"
MAIN_CHANNEL_LINK = "https://t.me/+_FVPR7qaQuRhYmY1"

# ================= MONGODB =================
MONGO_URL = "mongodb+srv://sanjublogscom_db_user:Mahakal456@cluster0.cwi48dt.mongodb.net/?appName=Cluster0"
client = pymongo.MongoClient(MONGO_URL)
db = client["botdb"]
files_collection = db["files"]

# ================= DB HELPERS =================
def save_data(media_id, files):
    files_collection.update_one(
        {"media_id": media_id},
        {"$set": {"media_id": media_id, "data": files}},
        upsert=True
    )

def get_data(media_id):
    r = files_collection.find_one({"media_id": media_id})
    return r["data"] if r else None

def delete_data(media_id):
    files_collection.delete_one({"media_id": media_id})

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    params = " ".join(context.args) if context.args else None

    if params:
        await handle_link_access(update, context, params)
        return

    if user.id in ADMIN_ID:
        await update.message.reply_text(
            "<b>📤 Admin Panel</b>\n\n"
            "/upload – Upload files\n"
            "/revoke &lt;media_id&gt; – Delete link\n",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "<b>Dude channel vali link use kar👇\n"
            "Channel: t.me/+_FVPR7qaQuRhYmY1</b>",
            parse_mode="HTML"
        )

# ================= LINK ACCESS =================
async def handle_link_access(update: Update, context: ContextTypes.DEFAULT_TYPE, media_id):
    user_id = update.effective_user.id

    # ----- FORCE JOIN -----
    try:
        member = await context.bot.get_chat_member(PUBLIC_CHANNEL, user_id)
        if member.status not in ("member", "administrator", "creator"):
            raise Exception
    except Exception:
        await update.message.reply_text(
            "🚫 Pehle channel join kar!",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "📢 Join Channel", "url": MAIN_CHANNEL_LINK}
                ]]
            }
        )
        return

    files = get_data(media_id)
    if not files:
        await update.message.reply_text("❌ No media found.")
        return

    sent_ids = []

    for f in files:
        m = None
        if f["type"] == "photo":
            m = await context.bot.send_photo(user_id, f["file_id"], caption=f.get("caption",""), protect_content=True)
        elif f["type"] == "video":
            m = await context.bot.send_video(user_id, f["file_id"], caption=f.get("caption",""), protect_content=True)
        elif f["type"] == "document":
            m = await context.bot.send_document(user_id, f["file_id"], protect_content=True)
        elif f["type"] == "audio":
            m = await context.bot.send_audio(user_id, f["file_id"], protect_content=True)
        elif f["type"] == "voice":
            m = await context.bot.send_voice(user_id, f["file_id"], protect_content=True)
        elif f["type"] == "animation":
            m = await context.bot.send_animation(user_id, f["file_id"], protect_content=True)
        elif f["type"] == "sticker":
            m = await context.bot.send_sticker(user_id, f["file_id"])

        if m:
            sent_ids.append(m.message_id)

    note = await update.message.reply_text("⚠️ Files 30 min baad delete ho jayengi.")
    sent_ids.append(note.message_id)

    # ⏱ AUTO DELETE (30 min)
    context.job_queue.run_once(
        delete_messages_job,
        1800,
        data={"user_id": user_id, "message_ids": sent_ids}
    )

# ================= DELETE JOB =================
async def delete_messages_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    user_id = data["user_id"]
    msg_ids = data["message_ids"]

    for mid in msg_ids:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=mid)
        except Forbidden:
            break
        except BadRequest:
            pass
        except Exception as e:
            logger.error(e)

# ================= UPLOAD =================
async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_ID:
        return

    import uuid
    media_id = str(uuid.uuid4())
    context.user_data["media_id"] = media_id
    context.user_data["files"] = []

    await update.message.reply_text(
        "Media bhejo. Finish ke liye ✅ likho.",
        reply_markup=ReplyKeyboardMarkup([["✅"]], resize_keyboard=True)
    )

# ================= HANDLE MEDIA =================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_ID:
        return

    media_id = context.user_data.get("media_id")
    files = context.user_data.get("files", [])

    if update.message.text == "✅":
        save_data(media_id, files)
        link = f"https://t.me/{(await context.bot.get_me()).username}?start={media_id}"
        await update.message.reply_text(
            f"✅ Done\n{link}",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return

    m = update.message
    entry = None

    if m.photo:
        entry = {"type": "photo", "file_id": m.photo[-1].file_id, "caption": m.caption}
    elif m.video:
        entry = {"type": "video", "file_id": m.video.file_id, "caption": m.caption}
    elif m.document:
        entry = {"type": "document", "file_id": m.document.file_id}
    elif m.audio:
        entry = {"type": "audio", "file_id": m.audio.file_id}
    elif m.voice:
        entry = {"type": "voice", "file_id": m.voice.file_id}
    elif m.animation:
        entry = {"type": "animation", "file_id": m.animation.file_id}
    elif m.sticker:
        entry = {"type": "sticker", "file_id": m.sticker.file_id}

    if entry:
        files.append(entry)
        context.user_data["files"] = files
        await update.message.reply_text("✅ Saved")

# ================= REVOKE =================
async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /revoke <media_id>")
        return

    delete_data(context.args[0])
    await update.message.reply_text("✅ Link revoked")

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upload", upload))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_media))

    app.run_polling()

if __name__ == "__main__":
    main()
