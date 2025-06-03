import discord
from discord.ext import commands
import asyncio
import yt_dlp
import os
from dotenv import load_dotenv
load_dotenv()


os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

queues = {}  # Guild-specific queues


def get_ffmpeg_options():
    return {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

@bot.event
async def on_ready():
    print(f'🎧 Bot connected as {bot.user}')


@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)
    else:
        await ctx.send("You're not in a voice channel.")


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queues.pop(ctx.guild.id, None)


@bot.command()
async def play(ctx, *, query):
    await ctx.invoke(bot.get_command('join'))  # Make sure we're in VC

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'outtmpl': 'song.%(ext)s',
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]  # Top result
            title = info.get('title')
            url = info.get('url')
            webpage_url = info.get('webpage_url')
    except Exception as e:
        await ctx.send(f"⚠️ Failed to find or load audio: {e}")
        return

    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = asyncio.Queue()
        ctx.bot.loop.create_task(player_loop(ctx))

    await queues[ctx.guild.id].put((title, url, ctx))
    await ctx.send(f"🔁 Queued: **{title}**\n🔗 {webpage_url}")


async def player_loop(ctx):
    while True:
        queue = queues[ctx.guild.id]
        title, url, ctx = await queue.get()

        try:
            source = await discord.FFmpegOpusAudio.from_probe(
                url, method='fallback', executable='ffmpeg', **get_ffmpeg_options()
            )

            vc = ctx.voice_client
            if not vc:
                break

            vc.play(source)
            await ctx.send(f'🎶 Now playing: **{title}**')

            while vc.is_playing() or vc.is_paused():
                await asyncio.sleep(1)

        except Exception as e:
            await ctx.send(f'⚠️ Error playing **{title}**: {str(e)}')


@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped current track.")


@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused.")


@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed.")


@bot.command()
async def volume(ctx, vol: int):
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = vol / 100
        await ctx.send(f"🔊 Volume set to {vol}%")
    else:
        await ctx.send("Nothing is playing.")


@bot.command()
async def queue(ctx):
    queue = queues.get(ctx.guild.id)
    if not queue or queue.empty():
        await ctx.send("🕳️ Queue is empty.")
    else:
        items = list(queue._queue)
        msg = "\n".join(f"{i+1}. {item[0]}" for i, item in enumerate(items))  # item[0] is the title
        await ctx.send(f"📜 **Current Queue:**\n{msg}")

bot.run(os.getenv("DISCORD_TOKEN"))