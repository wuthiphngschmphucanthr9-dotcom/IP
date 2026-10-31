import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from aiohttp import web

TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
PORT = int(os.environ.get("PORT", 8080))
COOLDOWN = 60

TZ = ZoneInfo("Asia/Bangkok")
last_seen = {}
history = []


def now_str():
    return datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")


class VisitorBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        app = web.Application()
        app.add_routes([web.get("/", self.health), web.post("/visit", self.visit)])
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()

    async def on_ready(self):
        print(f"บอทออนไลน์: {self.user}")
        try:
            ch = self.get_channel(CHANNEL_ID) or await self.fetch_channel(CHANNEL_ID)
            self.tree.copy_global_to(guild=ch.guild)
            await self.tree.sync(guild=ch.guild)
        except Exception as e:
            print("sync ไม่สำเร็จ:", e)

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
        history.append({"ip": ip, "time": now_str()})

        ch = self.get_channel(CHANNEL_ID) or await self.fetch_channel(CHANNEL_ID)
        e = discord.Embed(title="🔔 มีคนเข้าเว็บ", color=0x5865F2)
        e.add_field(name="IP", value=f"`{ip}`", inline=True)
        e.add_field(name="เวลา", value=now_str(), inline=True)
        e.add_field(name="หน้าเว็บ", value=page, inline=False)
        e.add_field(name="อุปกรณ์", value=ua, inline=False)
        await ch.send(embed=e)
        return web.Response(status=204)


bot = VisitorBot()


@bot.tree.command(name="ping", description="เช็กว่าบอทออนไลน์")
async def ping(i: discord.Interaction):
    await i.response.send_message("🏓 ออนไลน์!", ephemeral=True)


@bot.tree.command(name="stats", description="ดูสถิติผู้เข้าเว็บ")
async def stats(i: discord.Interaction):
    uniq = len({h["ip"] for h in history})
    await i.response.send_message(
        f"📊 เข้าชม **{len(history)}** ครั้ง | IP ไม่ซ้ำ **{uniq}**", ephemeral=True)


@bot.tree.command(name="last", description="ดู 5 คนล่าสุด")
async def last(i: discord.Interaction):
    if not history:
        return await i.response.send_message("ยังไม่มีคนเข้าเว็บ", ephemeral=True)
    rows = [f"`{h['ip']}` — {h['time']}" for h in history[-5:][::-1]]
    await i.response.send_message("🕒 ล่าสุด:\n" + "\n".join(rows), ephemeral=True)


bot.run(TOKEN)
