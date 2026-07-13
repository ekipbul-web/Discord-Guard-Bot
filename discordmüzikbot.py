import discord
from discord.ext import commands
import wavelink
import os
import random
from flask import Flask
from threading import Thread

app = Flask(__name__)
@app.route('/')
def home(): return "OK"
def run_flask(): app.run(host='0.0.0.0', port=8080)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"🎵 {bot.user} hazır!")
    node = wavelink.Node(
        uri="lavalink.oops.wtf:443",
        password="www.freelavalink.ga",
        secure=True,
        inactive_player_timeout=300
    )
    await wavelink.Pool.connect(client=bot, nodes=[node])
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!yardim | !oynat"))
    print("✅ Lavalink bağlandı!")

@bot.event
async def on_wavelink_track_start(payload):
    player = payload.player
    track = payload.track
    channel = player.home
    if channel:
        embed = discord.Embed(title="🎶 Şimdi Çalıyor", description=f"**[{track.title}]({track.uri})**", color=0x1DB954)
        embed.add_field(name="👤 Sanatçı", value=track.author, inline=True)
        if track.length:
            m, s = divmod(track.length // 1000, 60)
            embed.add_field(name="⏱️ Süre", value=f"{int(m)}:{int(s):02d}", inline=True)
        if track.artwork: embed.set_thumbnail(url=track.artwork)
        await channel.send(embed=embed)

@bot.event
async def on_wavelink_track_end(payload):
    player = payload.player
    if not player.queue.is_empty:
        await player.play(player.queue.get())

@bot.command(name='gir')
async def join(ctx):
    if not ctx.author.voice: return await ctx.send("❌ Ses kanalında değilsin!")
    ch = ctx.author.voice.channel
    if ctx.voice_client: await ctx.voice_client.move_to(ch)
    else: await ch.connect(cls=wavelink.Player)
    await ctx.send(f"🔊 **{ch.name}** kanalına katıldım!")

@bot.command(name='cik')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Görüşürüz!")
    else:
        await ctx.send("❌ Zaten kanalda değilim!")

@bot.command(name='oynat', aliases=['p', 'play'])
async def play(ctx, *, query: str):
    if not ctx.author.voice: return await ctx.send("❌ Ses kanalında değilsin!")
    
    ch = ctx.author.voice.channel
    if not ctx.voice_client: await ch.connect(cls=wavelink.Player)
    elif ctx.voice_client.channel != ch: await ctx.voice_client.move_to(ch)
    
    msg = await ctx.send("🔍 **Aranıyor...**")
    
    try:
        tracks = await wavelink.Playable.search(query)
        if not tracks: return await msg.edit(content="❌ **Sonuç bulunamadı!**")
        
        track = tracks[0]
        player = ctx.voice_client
        
        if player.playing:
            player.queue.put(track)
            embed = discord.Embed(title="🎵 Sıraya Eklendi", description=f"**[{track.title}]({track.uri})**", color=0x57F287)
            embed.add_field(name="👤 Sanatçı", value=track.author, inline=True)
            embed.add_field(name="📋 Sıra", value=f"#{player.queue.count}", inline=True)
            if track.artwork: embed.set_thumbnail(url=track.artwork)
            await msg.edit(content=None, embed=embed)
        else:
            await player.play(track)
            await msg.delete()
    except Exception as e:
        await msg.edit(content=f"❌ **Hata:** {str(e)[:100]}")

@bot.command(name='atla', aliases=['skip', 's'])
async def skip(ctx):
    player = ctx.voice_client
    if player and player.playing:
        await player.stop()
        await ctx.send("⏭️ **Atlandı!**")
    else:
        await ctx.send("❌ Müzik çalmıyor!")

@bot.command(name='durdur', aliases=['pause'])
async def pause(ctx):
    player = ctx.voice_client
    if player and player.playing:
        await player.pause(True)
        await ctx.send("⏸️ **Durduruldu!**")
    else:
        await ctx.send("❌ Müzik çalmıyor!")

@bot.command(name='devam', aliases=['resume'])
async def resume(ctx):
    player = ctx.voice_client
    if player and player.paused:
        await player.pause(False)
        await ctx.send("▶️ **Devam ediyor!**")
    else:
        await ctx.send("❌ Duraklatılmamış!")

@bot.command(name='ses', aliases=['volume', 'v'])
async def volume(ctx, vol: int = None):
    player = ctx.voice_client
    if not player: return await ctx.send("❌ Bağlı değilim!")
    
    if vol is None: return await ctx.send(f"🔊 Ses: **%{player.volume}**")
    
    if 0 <= vol <= 200:
        await player.set_volume(vol)
        await ctx.send(f"🔊 Ses: **%{vol}**")
    else:
        await ctx.send("❌ 0-200 arası olmalı!")

@bot.command(name='sira', aliases=['queue', 'q'])
async def show_queue(ctx):
    player = ctx.voice_client
    if not player or (not player.playing and player.queue.is_empty):
        return await ctx.send("📋 Sıra boş!")
    
    embed = discord.Embed(title="📋 Şarkı Sırası", color=0x9B59B6)
    
    if player.current:
        embed.add_field(name="🎶 Çalıyor", value=f"**[{player.current.title}]({player.current.uri})** - {player.current.author}", inline=False)
    
    queue_list = list(player.queue)
    for i, track in enumerate(queue_list[:10], 1):
        embed.add_field(name=f"#{i}", value=f"**[{track.title}]({track.uri})** - {track.author}", inline=False)
    
    if len(queue_list) > 10: embed.set_footer(text=f"Ve {len(queue_list) - 10} şarkı daha...")
    await ctx.send(embed=embed)

@bot.command(name='dongu', aliases=['loop', 'l'])
async def loop(ctx, mode: str = None):
    player = ctx.voice_client
    if not player: return await ctx.send("❌ Bağlı değilim!")
    
    if mode is None:
        modes = ['off', 'one', 'all']
        current = modes.index(str(player.queue.mode).split('.')[-1]) if player.queue.mode else 0
        player.queue.mode = modes[(current + 1) % 3]
    elif mode.lower() in ['off', 'kapat']: player.queue.mode = wavelink.QueueMode.normal
    elif mode.lower() in ['one', 'tek']: player.queue.mode = wavelink.QueueMode.loop
    elif mode.lower() in ['all', 'tum']: player.queue.mode = wavelink.QueueMode.loop_all
    else: return await ctx.send("❌ `off`, `one` veya `all`")
    
    names = {'normal': '➡️ Kapalı', 'loop': '🔂 Tek Şarkı', 'loop_all': '🔁 Tüm Liste'}
    mode_str = str(player.queue.mode).split('.')[-1]
    await ctx.send(f"🔄 **{names.get(mode_str, mode_str)}**")

@bot.command(name='karistir', aliases=['shuffle'])
async def shuffle(ctx):
    player = ctx.voice_client
    if not player or player.queue.is_empty: return await ctx.send("❌ Sıra boş!")
    
    queue_list = list(player.queue)
    random.shuffle(queue_list)
    player.queue.clear()
    for track in queue_list: player.queue.put(track)
    await ctx.send("🔀 **Karıştırıldı!**")

@bot.command(name='stop')
async def stop(ctx):
    player = ctx.voice_client
    if player:
        player.queue.clear()
        await player.stop()
        await ctx.send("⏹️ **Durduruldu, sıra temizlendi!**")

@bot.command(name='np', aliases=['now', 'calan'])
async def now_playing(ctx):
    player = ctx.voice_client
    if not player or not player.current: return await ctx.send("❌ Şu anda müzik çalmıyor!")
    
    track = player.current
    embed = discord.Embed(title="🎶 Şimdi Çalıyor", description=f"**[{track.title}]({track.uri})**", color=0x1DB954)
    embed.add_field(name="👤 Sanatçı", value=track.author, inline=True)
    if track.length:
        m, s = divmod(track.length // 1000, 60)
        embed.add_field(name="⏱️ Süre", value=f"{int(m)}:{int(s):02d}", inline=True)
    embed.add_field(name="🔊 Ses", value=f"%{player.volume}", inline=True)
    if track.artwork: embed.set_thumbnail(url=track.artwork)
    await ctx.send(embed=embed)

@bot.command(name='yardim', aliases=['h', 'help', 'komutlar'])
async def help_cmd(ctx):
    embed = discord.Embed(title="🎵 KROSS MÜZİK BOT", description="YouTube, Spotify, SoundCloud desteği!", color=0x5865F2)
    embed.add_field(name="🎤 Temel", value="`!gir` - Kanala katıl\n`!cik` - Kanaldan çık", inline=False)
    embed.add_field(name="🎵 Müzik", value="`!oynat <şarkı/link>` - Şarkı çal\n`!atla` - Sonraki\n`!durdur` - Duraklat\n`!devam` - Devam et", inline=False)
    embed.add_field(name="📋 Sıra", value="`!sira` - Sırayı gör\n`!karistir` - Karıştır\n`!dongu <off/one/all>` - Döngü\n`!stop` - Durdur", inline=False)
    embed.add_field(name="⚙️ Diğer", value="`!ses <0-200>` - Ses\n`!np` - Çalan şarkı\n`!yardim` - Bu menü", inline=False)
    embed.set_footer(text="Kross Müzik Bot © 2026 • Wavelink")
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    print(f"Hata: {error}")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("🎵 Kross Müzik Bot başlatılıyor...")
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN: bot.run(TOKEN)
    else: print("❌ Token bulunamadı!")
