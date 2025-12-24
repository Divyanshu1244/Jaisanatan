import os
import logging
import pymongo
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest  # Import for specific error handling

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = [6335046711, 8552084416]
PUBLIC_CHANNEL = "-1003582278269"
PRIVATE_CHANNEL = "-1003440235355"
PRIVATE_INVITE_LINK = "https://t.me/+FkReusMf7r44Nzhl"
MAIN_CHANNEL_LINK = "https://t.me/+_FVPR7qaQuRhYmY1"

# MongoDB connection
MONGO_URL = "mongodb+srv://sanjublogscom_db_user:Mahakal456@cluster0.cwi48dt.mongodb.net/?appName=Cluster0"
client = pymongo.MongoClient(MONGO_URL)
db = client['botdb']
files_collection = db['files']

# Global var for testing (stores last media_id for /testdelete)
last_media_id = None

# DB functions
def save_data(media_id, files):
    files_collection.update_one(
        {'media_id': media_id},
        {'$set': {'media_id': media_id, 'data': files}},
        upsert=True
    )

def get_data(media_id):
    result = files_collection.find_one({'media_id': media_id})
    return result['data'] if result else None

def delete_data(media_id):
    files_collection.delete_one({'media_id': media_id})

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    params = ' '.join(context.args) if context.args else None
    if params and params != "None" and not params.startswith("joined_"):
        await handle_link_access(update, context, params)
    elif params and params.startswith("joined_"):
        media_id = params.split("_")[1]
        await handle_link_access(update, context, media_id)
    else:
        if user.id in ADMIN_ID:
            await update.message.reply_text(
                "<b>📤 Welcome to Multi File Sharing Bot!</b>\n\nUse /upload to add files.\nUse /revoke <media_id> to delete a link.\nUse /testdelete to manually trigger deletion (for testing).",
                parse_mode="html",
                reply_markup={
                    "inline_keyboard": [[{"text": "📤 Start Uploading", "callback_data": "upload"}]]
                }
            )
        else:
            await update.message.reply_text(
                "<b>Dude channel vali link use kar video ke liye👇\nChannel:- t.me/+_FVPR7qaQuRhYmY1\n<code>Join bhi karliyo bhai 😄</code></b>",
                parse_mode="HTML"
            )

async def handle_link_access(update: Update, context: ContextTypes.DEFAULT_TYPE, media_id):
    global last_media_id
    user = update.effective_user
    user_id = user.id
    last_media_id = media_id  # Store for testing
    try:
        # Check membership with error handling
        is_member = False
        try:
            pub_member = await context.bot.get_chat_member(PUBLIC_CHANNEL, user_id)
            priv_member = await context.bot.get_chat_member(PRIVATE_CHANNEL, user_id)
            if pub_member.status in ['member', 'administrator', 'creator'] and priv_member.status in ['member', 'administrator', 'creator', 'left']:
                is_member = True
        except BadRequest as e:
            logger.error(f"Membership check failed (likely bot not admin): {e}. Treating user as not a member.")
            is_member = False  # Fallback: assume not a member
        except Exception as e:
            logger.error(f"Unexpected error in membership check: {e}. Treating user as not a member.")
            is_member = False

        if is_member:
            files = get_data(media_id)
            if not files:
                await update.message.reply_text("❌ No media found for this link.")
                return
            username = f"@{user.username}" if user.username else "No username"
            await context.bot.send_message(
                chat_id=6335046711,
                text=f"🔗 Link opened\n{user.first_name}\n👤 {user_id}\n{username}"
            )
            sent_msgs = []
            for f in files:
                m = None
                if f["type"] == "photo":
                    m = await context.bot.send_photo(chat_id=user.id, photo=f["file_id"], caption=f.get("caption", ""), protect_content=True)
                elif f["type"] == "video":
                    m = await context.bot.send_video(chat_id=user.id, video=f["file_id"], caption=f.get("caption", ""), protect_content=True)
                elif f["type"] == "audio":
                    m = await context.bot.send_audio(chat_id=user.id, audio=f["file_id"], protect_content=True)
                elif f["type"] == "voice":
                    m = await context.bot.send_voice(chat_id=user.id, voice=f["file_id"], protect_content=True)
                elif f["type"] == "document":
                    m = await context.bot.send_document(chat_id=user.id, document=f["file_id"], protect_content=True)
                elif f["type"] == "animation":
                    m = await context.bot.send_animation(chat_id=user.id, animation=f["file_id"], protect_content=True)
                elif f["type"] == "sticker":
                    m = await context.bot.send_sticker(chat_id=user.id, sticker=f["file_id"], protect_content=True)
                if m and hasattr(m, 'message_id'):
                    sent_msgs.append(m.message_id)
            note = await update.message.reply_text("⚠️ Note: Files will be deleted after 30 minutes.", parse_mode=None)
            sent_msgs.append(note.message_id)
            # TEMP: Set to 10 seconds for testing; change to 1800 for production
            job = context.job_queue.run_once(delete_messages_job, 10, data={"user_id": user.id, "message_ids": sent_msgs, "media_id": media_id})
            if job:
                logger.info(f"Job scheduled successfully for user {user_id}, media_id {media_id}, messages: {sent_msgs}")
            else:
                logger.error(f"Failed to schedule job for user {user_id}, media_id {media_id}")
        else:
            await update.message.reply_text(
                "🚫 Phele channel Join to karle babu!\n\nFriends ko bhi refer kar diyo 😋",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "📢 Join Channel", "url": MAIN_CHANNEL_LINK}],
                        [{"text": "📢 Join Channel ", "url": PRIVATE_INVITE_LINK}],
                        [{"text": "🌹 I Joined", "url": f"https://t.me/{(await context.bot.get_me()).username}?start=joined_{media_id}"}]
                    ]
                }
            )
    except Exception as e:
        logger.error(f"Unexpected error in handle_link_access: {e}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

# /testdelete command (admin only, for testing)
async def testdelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return
    global last_media_id
    if not last_media_id:
        await update.message.reply_text("❌ No recent media_id to test. Access a link first.")
        return
    # Simulate deletion data (you'd need to store sent_msgs properly for real testing)
    # For now, this just logs; replace with actual data if needed
    logger.info(f"Manual testdelete triggered for media_id {last_media_id}")
    await update.message.reply_text(f"✅ Manual deletion test logged for {last_media_id}. Check logs.")

# /upload command
async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
    else:
        keyboard = ReplyKeyboardMarkup([["✅"]], resize_keyboard=True)
        import uuid
        media_id = str(uuid.uuid4())
        context.user_data['upload_media_id'] = media_id
        context.user_data['upload_files'] = []
        await update.message.reply_text("👉 Send me the media you want to upload. When you are done, type ✅.", reply_markup=keyboard)

# /revoke command
async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
    else:
        if context.args:
            media_id = context.args[0]
            delete_data(media_id)
            await update.message.reply_text(f"✅ Link revoked! Media ID {media_id} deleted from database.")
        else:
            await update.message.reply_text("❌ Usage: /revoke <media_id>")

# Callback handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "upload":
        await upload(update, context)

# Handle media
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_ID:
        return
    media_id = context.user_data.get('upload_media_id')
    files = context.user_data.get('upload_files', [])
    if not media_id:
        await update.message.reply_text("❌ This command is internal. Use /upload to start.")
    else:
        keyboard = ReplyKeyboardRemove()
        if update.message.text == "✅":
            if files:
                shareable_link = f"https://t.me/{(await context.bot.get_me()).username}?start={media_id}"
                await update.message.reply_text(f"✅ Upload complete!\nShare this link:\n{shareable_link}", reply_markup=keyboard)
                save_data(media_id, files)
                context.user_data.clear()
            else:
                await update.message.reply_text("❌ No media was uploaded.")
        else:
            media_entry = None
            message = update.message
            if message.photo:
                media_entry = {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
            elif message.video:
                media_entry = {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
            elif message.audio:
                media_entry = {"type": "audio", "file_id": message.audio.file_id}
            elif message.voice:
                media_entry = {"type": "voice", "file_id": message.voice.file_id}
            elif message.document:
                media_entry = {"type": "document", "file_id": message.document.file_id}
            elif message.animation:
                media_entry = {"type": "animation", "file_id": message.animation.file_id}
            elif message.sticker:
                media_entry = {"type": "sticker", "file_id": message.sticker.file_id}
            if media_entry:
                files.append(media_entry)
                context.user_data['upload_files'] = files
                await update.message.reply_text("✅ Media saved. Send more or type ✅ to finish.")
            else:
                await update.message.reply_text("❌ Unsupported input. Please send media files only.")

# Delete messages job
async def delete_messages_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    user_id = data.get("user_id")
    msg_ids = data.get("message_ids", [])
    media_id = data.get("media_id")
    logger.info(f"Starting deletion for user {user_id}, media_id {media_id}, messages to delete: {msg_ids}")
    if not msg_ids:
        logger.warning(f"No messages to delete for user {user_id}")
        return
    for mid in msg_ids:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=mid)
            logger.info(f"Successfully deleted message {mid} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete message {mid} for user {user_id}: {e}")
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="Join our backup channel 💔",
            reply_markup={
                "inline_keyboard": [[{"text": "📢 Join Backup Channel", "url": PRIVATE_INVITE_LINK}]]
            }
        )
        logger.info(f"Sent follow-up message to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send follow-up to user {user_id}: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("revoke", revoke))
    application.add_handler(CommandHandler("testdelete", testdelete))  # New command
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_media))
    application.run_polling()

if __name__ == '__main__':
    main()
