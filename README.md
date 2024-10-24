# TelegramVideoBot
Basic bot for Telegram that downloads and uploads videos (powered by ffmpeg and yt-dlp)

## Usage
Replace the API key in your code with the API key of your bot (provided by BotFather).
Run the bot using `python3 bot.py`.

Download a video using `/download_video <video_url>`.
Download audio using `/download_audio <video_url>`.

## Issues
- Files are saved as `audio` or `video`, due to the bot not being able to parse titles with special characters,
- Processing long audio files takes a long time,
- Sometimes uploading the first segment of split audio/video fails (works on the 2nd try).
