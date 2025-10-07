import os
import asyncio
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Bot Token - Replace with your token from BotFather
BOT_TOKEN = "8253478677:AAFpE5gMFLzyfedSklFv048qabUNEc-AAnQ"

# Temporary directory for processing files
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# Store user states
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_text = (
        "🎬 **Welcome to MKV Rename Bot!**\n\n"
        "📤 Send me any video file (MP4, AVI, MOV, etc.)\n"
        "✏️ Then send the new name (without extension)\n"
        "🔄 I'll convert it to MKV format\n"
        "📥 And send it back as a document\n\n"
        "⚠️ **Limits:**\n"
        "• Max file size: 2GB\n"
        "• Original quality preserved\n\n"
        "Send a video to get started! 🚀"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video file uploads"""
    user_id = update.effective_user.id
    
    # Get video file
    if update.message.video:
        file = update.message.video
        file_type = "video"
    elif update.message.document:
        file = update.message.document
        file_type = "document"
    else:
        return
    
    # Check file size (2GB limit)
    file_size_mb = file.file_size / (1024 * 1024)
    if file.file_size > 2 * 1024 * 1024 * 1024:  # 2GB
        await update.message.reply_text(
            "❌ File too large! Maximum size is 2GB.\n"
            f"Your file: {file_size_mb:.2f} MB"
        )
        return
    
    # Check if it's a video file
    file_name = file.file_name if hasattr(file, 'file_name') else "video"
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp']
    
    if not any(file_name.lower().endswith(ext) for ext in video_extensions):
        await update.message.reply_text("❌ Please send a valid video file!")
        return
    
    # Store file info
    user_data[user_id] = {
        'file_id': file.file_id,
        'file_name': file_name,
        'file_size': file.file_size
    }
    
    await update.message.reply_text(
        f"✅ Video received: `{file_name}`\n"
        f"📦 Size: {file_size_mb:.2f} MB\n\n"
        f"✏️ Now send me the new name (without .mkv extension)",
        parse_mode='Markdown'
    )

async def handle_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rename text input"""
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await update.message.reply_text(
            "⚠️ Please send a video file first!\n"
            "Use /start to see instructions."
        )
        return
    
    new_name = update.message.text.strip()
    
    # Remove .mkv if user added it
    if new_name.lower().endswith('.mkv'):
        new_name = new_name[:-4]
    
    # Validate filename
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    if any(char in new_name for char in invalid_chars):
        await update.message.reply_text(
            "❌ Invalid filename! Please avoid these characters:\n"
            "/ \\ : * ? \" < > |"
        )
        return
    
    # Start processing
    file_data = user_data[user_id]
    await update.message.reply_text("🔄 Processing... Please wait!")
    
    # Download and convert
    try:
        await process_video(update, context, file_data, new_name)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        # Clean up user data
        if user_id in user_data:
            del user_data[user_id]

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE, file_data, new_name):
    """Download, convert, and upload video"""
    user_id = update.effective_user.id
    
    # File paths
    original_path = os.path.join(TEMP_DIR, f"{user_id}_original_{file_data['file_name']}")
    output_path = os.path.join(TEMP_DIR, f"{user_id}_{new_name}.mkv")
    
    try:
        # Download file with progress
        progress_msg = await update.message.reply_text("📥 Downloading... 0%")
        
        file = await context.bot.get_file(file_data['file_id'])
        await file.download_to_drive(original_path)
        
        # Update progress
        file_size_mb = file_data['file_size'] / (1024 * 1024)
        download_progress = min(99, int((file_size_mb / 10)))
        await progress_msg.edit_text(f"📥 Downloaded! ({file_size_mb:.2f} MB)")
        
        # Convert to MKV
        await progress_msg.edit_text("🔄 Converting to MKV... This may take a while...")
        
        # FFmpeg command - copy streams without re-encoding for speed and quality
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', original_path,
            '-c', 'copy',  # Copy all streams without re-encoding
            '-y',  # Overwrite output file
            output_path
        ]
        
        # Run FFmpeg
        process = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if process.returncode != 0:
            raise Exception(f"FFmpeg conversion failed: {process.stderr}")
        
        # Check output file
        if not os.path.exists(output_path):
            raise Exception("Conversion failed - output file not created")
        
        output_size = os.path.getsize(output_path)
        output_size_mb = output_size / (1024 * 1024)
        
        # Upload as document with progress
        await progress_msg.edit_text(f"📤 Uploading... 0%")
        
        with open(output_path, 'rb') as video_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=video_file,
                filename=f"{new_name}.mkv",
                caption=f"✅ **Converted to MKV**\n\n"
                        f"📁 Name: `{new_name}.mkv`\n"
                        f"📦 Size: {output_size_mb:.2f} MB",
                parse_mode='Markdown'
            )
        
        await progress_msg.edit_text("✅ Done! Send another video to convert.")
        
    finally:
        # Clean up temp files
        if os.path.exists(original_path):
            os.remove(original_path)
        if os.path.exists(output_path):
            os.remove(output_path)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
        await update.message.reply_text("❌ Operation cancelled. Send a new video to start again.")
    else:
        await update.message.reply_text("ℹ️ No active operation to cancel.")

def main():
    """Start the bot"""
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rename))
    
    # Start bot
    print("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()