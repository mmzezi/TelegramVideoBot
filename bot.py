import os
import yt_dlp
import logging
import subprocess
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from dotenv import load_dotenv

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Download folder
DOWNLOAD_FOLDER = './downloads/'

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Maximum upload size for Telegram (50MB)
TELEGRAM_UPLOAD_LIMIT = 50 * 1024 * 1024  # 50MB

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Send me a YouTube link, and I'll download the video or audio for you!")

async def download_video(update: Update, context: CallbackContext) -> None:
    logger.info("download_video called")
    message = update.message.text

    command_prefix = "/download_video"
    if message.startswith(command_prefix):
        message = message[len(command_prefix):].strip()
    else:
        await update.message.reply_text("Please use the correct command format: /download_video <video_url>")
        return

    if not message:
        await update.message.reply_text("Please provide a valid video URL.")
        logger.error("Invalid input. No URL provided.")
        return

    video_url = message
    logger.info(f"Downloading video from: {video_url}")

    ydl_opts = {
        'format': 'bestvideo[height<=480]+bestaudio[abr<=128]/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'outtmpl': f'{DOWNLOAD_FOLDER}%(title)s.%(ext)s',
        'http_chunk_size': 1048576,
        'socket_timeout': 120,
        'verbose': True,
    }

    logger.info(f"yt-dlp options: {ydl_opts}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Downloading video... Please wait.")
            info_dict = ydl.extract_info(video_url, download=True)
            logger.info(f"Successfully downloaded {video_url}")

            title = info_dict.get('title', 'video')
            output_file = f'{DOWNLOAD_FOLDER}{title}.mp4'

            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)

                # If the file is larger than Telegram's 50MB limit, split the video
                if file_size > TELEGRAM_UPLOAD_LIMIT:
                    await update.message.reply_text("Video is larger than 50MB. Splitting the video into parts...")
                    await split_and_upload_video(output_file, update, context)
                else:
                    # If it's smaller than 50MB, upload the video directly
                    await upload_video(output_file, update, context)
            else:
                await update.message.reply_text("Failed to find the downloaded video file.")
                logger.error("Failed to find the downloaded video file.")
                os.remove(output_file)
    except Exception as e:
        logger.error(f"Failed to download video: {str(e)}")
        await update.message.reply_text(f"Failed to download the video: {str(e)}")

async def upload_video(output_file, update: Update, context: CallbackContext):
    """Uploads a video file directly."""
    with open(output_file, 'rb') as video:
        await context.bot.send_video(chat_id=update.effective_chat.id, video=video)
    os.remove(output_file)
    logger.info(f"Deleted video file: {output_file}")

async def split_and_upload_video(filepath, update: Update, context: CallbackContext):
    """Splits the video into parts and uploads them."""
    logger.info(f"Splitting video: {filepath}")

    # Create output format for split files
    base_filename = os.path.splitext(filepath)[0]
    split_output_format = f"{base_filename}_part_%03d.mp4"

    try:
        # Split video using ffmpeg
        command = [
            'ffmpeg', '-i', filepath, '-c', 'copy', '-map', '0',
            '-f', 'segment', '-segment_time', '600',  # Split into 1-minute segments
            '-reset_timestamps', '1', split_output_format
        ]
        subprocess.run(command, check=True)
        logger.info("Video splitting completed.")

        # Upload each part sequentially
        part_number = 0
        while True:
            part_file = split_output_format % part_number
            if os.path.exists(part_file):
                retries = 0
                while retries < 3:
                    try:
                        await upload_video(part_file, update, context)
                        break  # Exit the retry loop on success
                    except Exception as e:
                        retries += 1
                        logger.warning(f"Error uploading {part_file}: {str(e)}, retrying ({retries}/3)...")
                        await asyncio.sleep(2)  # Wait before retrying
                if retries == 3:
                    logger.error(f"Failed to upload {part_file} after 3 retries. Deleting...")
                    os.remove(part_file)  # Delete the part file after 3 failed attempts
                    await update.message.reply_text(f"Failed to upload {part_file} after 3 retries, deleting the file.")
                part_number += 1
            else:
                break

        # Delete the original file after splitting and uploading
        os.remove(filepath)
        logger.info(f"Deleted original video file: {filepath}")
    except Exception as e:
        logger.error(f"Failed to split and upload video: {str(e)}")
        await update.message.reply_text(f"Failed to split the video: {str(e)}")

async def download_audio(update: Update, context: CallbackContext) -> None:
    logger.info("download_audio called")
    message = update.message.text

    command_prefix = "/download_audio"
    if message.startswith(command_prefix):
        message = message[len(command_prefix):].strip()
    else:
        await update.message.reply_text("Please use the correct command format: /download_audio <audio_url>")
        return

    if not message:
        await update.message.reply_text("Please provide a valid audio URL.")
        logger.error("Invalid input. No URL provided.")
        return

    audio_url = message
    logger.info(f"Downloading audio from: {audio_url}")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f'{DOWNLOAD_FOLDER}%(title)s.%(ext)s',
        'verbose': True,
    }

    logger.info(f"yt-dlp options: {ydl_opts}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Downloading audio... Please wait.")
            info_dict = ydl.extract_info(audio_url, download=True)
            logger.info(f"Successfully downloaded {audio_url}")

            title = info_dict.get('title', 'audio')
            output_file = f'{DOWNLOAD_FOLDER}{title}.mp3'

            if os.path.exists(output_file):
                with open(output_file, 'rb') as audio:
                    await context.bot.send_audio(chat_id=update.effective_chat.id, audio=audio)
                os.remove(output_file)
                logger.info(f"Deleted audio file: {output_file}")
            else:
                await update.message.reply_text("Failed to find the downloaded audio file.")
                logger.error("Failed to find the downloaded audio file.")
                os.remove(output_file)
    except Exception as e:
        logger.error(f"Failed to download audio: {str(e)}")
        await update.message.reply_text(f"Failed to download the audio: {str(e)}")
        os.remove(output_file)

def main():
    load_dotenv()
    api_key = os.getenv('API_KEY')
    TOKEN = api_key  # Replace with your actual bot token
    print(TOKEN)
    application = Application.builder().token(TOKEN).read_timeout(300).write_timeout(300).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("download_video", download_video))
    application.add_handler(CommandHandler("download_audio", download_audio))
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
