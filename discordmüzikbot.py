import discord
from discord.ext import commands
import wavelink
import os
from flask import Flask
from threading import Thread

# Flask (Render için)
app = Flask(__name__)

@app.route('/')
def home():
    return "Kross Music Bot - Aktif"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# -------------------- WAVELINK --------------------

@bot.event
async def on_ready():
    print(f"🎵 {bot.user} hazır!")
    
    # Lavalink sunucusuna bağlan
    node = wavelink.Node(
        uri="lavalink.oops.wtf:443",
        password="www.freelavalink.ga",
        secure=True,
        inactive_player_timeout=300
    )
    await wavelink.Pool.connect(client=bot, nodes=[node])
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!yardim | !oynat"
        )
    )
    print("✅ Lavalink bağlandı!")

@bot.event
async def on_wavelink_track_start(payload):
    """Şarkı başladığında"""
    player = payload.player
    track = payload.track
    
    embed = discord.Embed(
        title="🎶 Şimdi Çalıyor",
        description=f"**[{track.title}]({track.uri})**",
        color=0x1DB954
    )
    embed.add_field(name="👤 Sanatçı", value=track.author, inline=True)
    if track.length:
        m, s = divmod(track.length // 1000, 60)
        embed.add_field(name="⏱️ Süre", value=f"{int(m)}:{int(s):02d}", inline=True)
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    
    channel = player.home
    if channel:
        await channel.send(embed=embed)

@bot.event
async def on_wavelink_track_end(payload):
    """Şarkı bittiğinde"""
    player = payload.player
    if player.queue:
        await player.play(player.queue.get())

# -------------------- KOMUTLAR --------------------

@bot.command(name='gir')
async def join(ctx):
    """Ses kanalına katılır"""
    if not ctx.author.voice:
        return await ctx.send("❌ Ses kanalında değilsin!")
    
    channel = ctx.author.voice.channel
    player = ctx.voice_client
    
    if player:
        await player.move_to(channel)
    else:
        player = await channel.connect(cls=wavelink.Player)
    
    await ctx.send(f"🔊 **{channel.name}** kanalına katıldım!")

@bot.command(name='cik')
async def leave(ctx):
    """Ses kanalından ayrılır"""
    player = ctx.voice_client
    
    if player:
        await player.disconnect()
        await ctx.send("👋 Görüşürüz!")
    else:
        await ctx.send("❌ Zaten kanalda değilim!")

@bot.command(name='oynat', aliases=['p', 'play'])
async def play(ctx, *, query: str):
    """Şarkı arar ve çalar (YouTube + Spotify)"""
    if not ctx.author.voice:
        return await ctx.send("❌ Ses kanalında değilsin!")
    
    channel = ctx.author.voice.channel
    player = ctx.voice_client
    
    if not player:
        player = await channel.connect(cls=wavelink.Player)
    elif player.channel != channel:
        await player.move_to(channel)
    
    msg = await ctx.send("🔍 **Aranıyor...**")
    
    try:
        # YouTube'da ara
        tracks = await wavelink.Playable.search(query)
        
        if not tracks:
            return await msg.edit(content="❌ **Sonuç bulunamadı!**")
        
        track = tracks[0]
        
        if player.playing:
            player.queue.put(track)
            
            embed = discord.Embed(
                title="🎵 Sıraya Eklendi",
                description=f"**[{track.title}]({track.uri})**",
                color=0x57F287
            )
            embed.add_field(name="👤 Sanatçı", value=track.author, inline=True)
            embed.add_field(name="📋 Sıra", value=f"#{player.queue.count + 1}", inline=True)
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            
            await msg.edit(content=None, embed=embed)
        else:
            await player.play(track)
            await msg.delete()
            
    except Exception as e:
        await msg.edit(content=f"❌ **Hata:** {str(e)[:100]}")

@bot.command(name='atla', aliases=['skip', 's'])
async def skip(ctx):
    """Şarkıyı atlar"""
    player = ctx.voice_client
    
    if player and player.playing:
        await player.stop()
        await ctx.send("⏭️ **Atlandı!**")
    else:
        await ctx.send("❌ Müzik çalmıyor!")

@bot.command(name='durdur', aliases=['pause'])
async def pause(ctx):
    """Müziği duraklatır"""
    player = ctx.voice_client
    
    if player and player.playing:
        await player.pause(True)
        await ctx.send("⏸️ **Durduruldu!**")
    else:
        await ctx.send("❌ Müzik çalmıyor!")

@bot.command(name='devam', aliases=['resume'])
async def resume(ctx):
    """Müziği devam ettirir"""
    player = ctx.voice_client
    
    if player and player.paused:
        await player.pause(False)
        await ctx.send("▶️ **Devam ediyor!**")
    else:
        await ctx.send("❌ Duraklatılmamış!")

@bot.command(name='ses', aliases=['volume', 'v'])
async def volume(ctx, volume: int = None):
    """Ses seviyesini ayarlar (0-200)"""
    player = ctx.voice_client
    
    if not player:
        return await ctx.send("❌ Bağlı değilim!")
    
    if volume is None:
        return await ctx.send(f"🔊 Ses: **%{player.volume}**")
    
    if 0 <= volume <= 200:
        await player.set_volume(volume)
        await ctx.send(f"🔊 Ses: **%{volume}**")
    else:
        await ctx.send("❌ 0-200 arası olmalı!")

@bot.command(name='sira', aliases=['queue', 'q'])
async def show_queue(ctx):
    """Şarkı sırasını gösterir"""
    player = ctx.voice_client
    
    if not player or (not player.playing and player.queue.is_empty):
        return await ctx.send("📋 Sıra boş!")
    
    embed = discord.Embed(title="📋 Şarkı Sırası", color=0x9B59B6)
    
    if player.current:
        embed.add_field(
            name="🎶 Çalıyor",
            value=f"**[{player.current.title}]({player.current.uri})** - {player.current.author}",
            inline=False
        )
    
    queue_list = list(player.queue)
    for i, track in enumerate(queue_list[:10], 1):
        embed.add_field(
            name=f"#{i}",
            value=f"**[{track.title}]({track.uri})** - {track.author}",
            inline=False
        )
    
    if len(queue_list) > 10:
        embed.set_footer(text=f"Ve {len(queue_list) - 10} şarkı daha...")
    
    await ctx.send(embed=embed)

@bot.command(name='dongu', aliases=['loop', 'l'])
async def loop(ctx, mode: str = None):
    """Döngü modu: off / one / all"""
    player = ctx.voice_client
    
    if not player:
        return await ctx.send("❌ Bağlı değilim!")
    
    if mode is None:
        modes = ['off', 'one', 'all']
        current = modes.index(player.queue.mode)
        player.queue.mode = modes[(current + 1) % 3]
    elif mode.lower() in ['off', 'kapat']:
        player.queue.mode = 'off'
    elif mode.lower() in ['one', 'tek', '1']:
        player.queue.mode = 'one'
    elif mode.lower() in ['all', 'tum', 'hepsi']:
        player.queue.mode = 'all'
    else:
        return await ctx.send("❌ `off`, `one` veya `all`")
    
    names = {'off': '➡️ Kapalı', 'one': '🔂 Tek Şarkı', 'all': '🔁 Tüm Liste'}
    await ctx.send(f"🔄 **{names[player.queue.mode]}**")

@bot.command(name='karistir', aliases=['shuffle'])
async def shuffle(ctx):
    """Sırayı karıştırır"""
    player = ctx.voice_client
    
    if not player or player.queue.is_empty:
        return await ctx.send("❌ Sıra boş!")
    
    import random
    queue_list = list(player.queue)
    random.shuffle(queue_list)
    player.queue.clear()
    for track in queue_list:
        player.queue.put(track)
    
    await ctx.send("🔀 **Karıştırıldı!**")

@bot.command(name='stop')
async def stop(ctx):
    """Müziği durdurur ve sırayı temizler"""
    player = ctx.voice_client
    
    if player:
        player.queue.clear()
        await player.stop()
        await ctx.send("⏹️ **Durduruldu, sıra temizlendi!**")

@bot.command(name='np', aliases=['now', 'calan'])
async def now_playing(ctx):
    """Çalan şarkıyı gösterir"""
    player = ctx.voice_client
    
    if not player or not player.current:
        return await ctx.send("❌ Şu anda müzik çalmıyor!")
    
    track = player.current
    embed = discord.Embed(
        title="🎶 Şimdi Çalıyor",
        description=f"**[{track.title}]({track.uri})**",
        color=0x1DB954
    )
    embed.add_field(name="👤 Sanatçı", value=track.author, inline=True)
    if track.length:
        m, s = divmod(track.length // 1000, 60)
        embed.add_field(name="⏱️ Süre", value=f"{int(m)}:{int(s):02d}", inline=True)
    embed.add_field(name="🔊 Ses", value=f"%{player.volume}", inline=True)
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    
    await ctx.send(embed=embed)

@bot.command(name='yardim', aliases=['h', 'help', 'komutlar'])
async def help_cmd(ctx):
    """Tüm komutları gösterir"""
    embed = discord.Embed(
        title="🎵 KROSS MÜZİK BOT",
        description="YouTube, Spotify, SoundCloud ve daha fazlası!\nWavelink + Lavalink ile çalışır.",
        color=0x5865F2
    )
    embed.add_field(name="🎤 **Temel**", value="`!gir` - Kanala katıl\n`!cik` - Kanaldan çık", inline=False)
    embed.add_field(name="🎵 **Müzik**", value="`!oynat <şarkı>` - Şarkı çal\n`!atla` - Sonraki\n`!durdur` - Duraklat\n`!devam` - Devam et", inline=False)
    embed.add_field(name="📋 **Sıra**", value="`!sira` - Sırayı gör\n`!karistir` - Karıştır\n`!dongu` - Döngü\n`!stop` - Durdur", inline=False)
    embed.add_field(name="⚙️ **Diğer**", value="`!ses <0-200>` - Ses\n`!np` - Çalan şarkı\n`!yardim` - Bu menü", inline=False)
    embed.set_footer(text="Kross Müzik Bot © 2026 • Wavelink")
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Hata: {error}")

# -------------------- BAŞLAT --------------------
if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("🎵 Kross Müzik Bot başlatılıyor...")
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Token bulunamadı!")
