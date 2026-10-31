# รัน: python bot_local.py   |   ติดตั้ง: pip install discord.py aiohttp
# อย่าอัปไฟล์นี้ขึ้น GitHub หลังใส่ TOKEN แล้ว!

# ====== ใส่ค่าตรงนี้ ======
TOKEN = "ใส่_TOKEN_ของบอท"
CHANNEL_ID = 123456789012345678   # ID ห้องที่ให้แจ้งเตือน
PORT = 8080
COOLDOWN = 60                     # วินาที กัน IP เดิมยิงซ้ำ
USE_TUNNEL = False                # True = เปิด Cloudflare Tunnel อัตโนมัติ (ต้องมี cloudflared)
# ==========================

import asyncio
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from aiohttp import web

TZ = ZoneInfo("Asia/Bangkok")
intents = discord.Intents.default()
last_seen = {}
history = []  # เก็บประวัติในหน่วยความจำ (หายเมื่อรีสตาร์ท)


def now_str():
    return datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")


class VisitorBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        app = web.Application()
        app.add_routes([web.get("/", self.health), web.post("/visit", self.visit)])
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()
        print(f"API รันที่พอร์ต {PORT}")
        if USE_TUNNEL:
            asyncio.create_task(self.start_tunnel())

    async def start_tunnel(self):
        try:
            proc = await asyncio.create_subprocess_exec(
                "cloudflared", "tunnel", "--url", f"http://localhost:{PORT}",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        except FileNotFoundError:
            print("ไม่พบ cloudflared")
            return
        async for line in proc.stderr:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line.decode())
            if m:
                print(f'\nconst API_URL = "{m.group(0)}/visit";\n')

    async def on_ready(self):
        print(f"บอทออนไลน์: {self.user}")
        try:
            ch = self.get_channel(CHANNEL_ID) or await self.fetch_channel(CHANNEL_ID)
            self.tree.copy_global_to(guild=ch.guild)
            await self.tree.sync(guild=ch.guild)
            print("ลงทะเบียนคำสั่งแล้ว")
        except Exception as e:
            print("sync คำสั่งไม่สำเร็จ:", e)

    async def health(self, request):
        return web.Response(text="ok")

    async def visit(self, request):
        fwd = request.headers.get("X-Forwarded-For", "")
        ip = fwd.split(",")[0].strip() or request.remote
        ua = request.headers.get("User-Agent", "ไม่ทราบ")[:200]
        page = request.headers.get("Referer", "ไม่ทราบ")

        t = time.time()
        if t - last_seen.get(ip, 0) < COOLDOWN:
            return web.Response(status=204)
        last_seen[ip] = t
        history.append({"ip": ip, "time": now_str(), "ua": ua})

        ch = self.get_channel(CHANNEL_ID) or await self.fetch_channel(CHANNEL_ID)
        e = discord.Embed(title="🔔 มีคนเข้าเว็บ", color=0x5865F2)
        e.add_field(name="IP", value=f"`{ip}`", inline=True)
        e.add_field(name="เวลา", value=now_str(), inline=True)
        e.add_field(name="หน้าเว็บ", value=page, inline=False)
        e.add_field(name="อุปกรณ์", value=ua, inline=False)
        await ch.send(embed=e)
        return web.Response(status=204)


bot = VisitorBot()


@bot.tree.command(name="ping", description="เช็กว่าบอทออนไลน์อยู่ไหม")
async def ping(i: discord.Interaction):
    await i.response.send_message(f"🏓 ออนไลน์! ({round(bot.latency * 1000)} ms)", ephemeral=True)


@bot.tree.command(name="stats", description="ดูสถิติผู้เข้าเว็บ")
async def stats(i: discord.Interaction):
    uniq = len({h["ip"] for h in history})
    await i.response.send_message(
        f"📊 เข้าชมทั้งหมด **{len(history)}** ครั้ง | IP ไม่ซ้ำ **{uniq}** รายการ", ephemeral=True)


@bot.tree.command(name="last", description="ดู 5 คนล่าสุดที่เข้าเว็บ")
async def last(i: discord.Interaction):
    if not history:
        return await i.response.send_message("ยังไม่มีคนเข้าเว็บ", ephemeral=True)
    rows = [f"`{h['ip']}` — {h['time']}" for h in history[-5:][::-1]]
    await i.response.send_message("🕒 ล่าสุด:\n" + "\n".join(rows), ephemeral=True)


@bot.tree.command(name="clear", description="ล้างประวัติผู้เข้าชม (เฉพาะแอดมิน)")
@app_commands.default_permissions(administrator=True)
async def clear(i: discord.Interaction):
    history.clear()
    last_seen.clear()
    await i.response.send_message("🧹 ล้างประวัติแล้ว", ephemeral=True)


bot.run(TOKEN)
