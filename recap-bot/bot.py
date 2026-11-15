import asyncio,io,os,re,sqlite3,hashlib,logging
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import discord,edge_tts
from discord import app_commands
from discord.ext import commands,tasks
from playwright.async_api import async_playwright
from PIL import Image,ImageDraw,ImageFont
from dotenv import load_dotenv
load_dotenv();logging.basicConfig(level=logging.INFO);log=logging.getLogger("chl.recaps")
TEAMS={"ANA":"Anaheim","BUF":"Buffalo","CGY":"Calgary","DET":"Detroit","MIN":"Minnesota","SEA":"Seattle","SJS":"San Jose","UTAH":"Utah","VGK":"Vegas","WSH":"Washington"}
MON={m:i+1 for i,m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
ET=ZoneInfo("America/New_York")
PAT=re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+(\d{1,2}):(\d\d)\s*(AM|PM)\s+UTC\s+(?:(?:REG|PO|PRE|POST|PLAYOFF)\s+)?(ANA|BUF|CGY|DET|MIN|SEA|SJS|UTAH|VGK|WSH)\s+AWAY\s+(\d+)\s*[-–:]\s*(\d+)\s+(ANA|BUF|CGY|DET|MIN|SEA|SJS|UTAH|VGK|WSH)\s+HOME\s+(Final|Forfeit)\b",re.I)
TOKEN=os.getenv("DISCORD_TOKEN","")
GUILD=int(os.getenv("GUILD_ID","0"));CHANNEL=int(os.getenv("RECAP_CHANNEL_ID","0"))
DB=os.getenv("DATABASE_PATH","/data/recaps.sqlite3");PERIOD=max(5,int(os.getenv("POLL_MINUTES","15")))
AUDIO=os.getenv("ENABLE_AUDIO","true").lower()=="true"
VOICE=os.getenv("TTS_VOICE","en-US-GuyNeural")
bot=commands.Bot(command_prefix="!",intents=discord.Intents.default())
lock=asyncio.Lock()
def conn():
    Path(DB).parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    c.executescript("""CREATE TABLE IF NOT EXISTS games(id TEXT PRIMARY KEY,date TEXT,away TEXT,home TEXT,a INTEGER,h INTEGER,status TEXT,posted TEXT,post_id TEXT);
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);""")
    return c
def parse(text):
    now=datetime.now(timezone.utc);out=[]
    for m in PAT.finditer(text):
        mo,day,hr,minute,am,away,a,h,home,status=m.groups()
        hr=int(hr)%12+(12 if am.upper()=="PM" else 0)
        dates=[]
        for year in [now.year-1,now.year,now.year+1]:
            try:dates.append(datetime(year,MON[mo.title()],int(day),hr,int(minute),tzinfo=timezone.utc))
            except ValueError:pass
        if not dates:continue
        dt=min(dates,key=lambda x:abs((x-now).total_seconds()))
        if dt>now or away==home or a==h:continue
        fid=hashlib.sha256((dt.isoformat()+away+home).encode()).hexdigest()[:16]
        out.append(dict(id=fid,date=dt.isoformat(),away=away,home=home,a=int(a),h=int(h),status=status.title()))
    return out
async def scrape():
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=await b.new_page()
            await page.goto("https://playchl.com/schedule",wait_until="domcontentloaded",timeout=60000)
            try:await page.get_by_text("Final",exact=False).first.wait_for(timeout=16000)
            except Exception:pass
            await page.wait_for_timeout(2000)
            data=parse(await page.locator("body").inner_text(timeout=20000))
            if not data:raise RuntimeError("No completed games matched PlayCHL schedule")
            return data
        finally:await b.close()
def ingest(c,data):
    initial=c.execute("SELECT v FROM meta WHERE k='ready'").fetchone() is None
    n=0
    for g in data:
        old=c.execute("SELECT id,a,h,status FROM games WHERE id=?",(g["id"],)).fetchone()
        if old is None:
            n+=1
            c.execute("INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?)",(g["id"],g["date"],g["away"],g["home"],g["a"],g["h"],g["status"],"baseline" if initial else None,None))
        elif (old["a"],old["h"],old["status"])!=(g["a"],g["h"],g["status"]):
            log.warning("Score correction detected for %s; prior recaps are not silently overwritten",g["id"])
            c.execute("UPDATE games SET a=?,h=?,status=? WHERE id=?",(g["a"],g["h"],g["status"],g["id"]))
    if initial:c.execute("INSERT INTO meta VALUES('ready','yes')")
    c.commit()
    return n,initial
def facts(game,history):
    away,home=game["away"],game["home"]
    win=away if game["a"]>game["h"] else home;lose=home if win==away else away
    prior=[g for g in history if g["date"]<game["date"] and g["status"]=="Final"]
    def record(team):
        w=l=0
        for g in prior:
            if team not in (g["away"],g["home"]):continue
            score=g["a"] if g["away"]==team else g["h"]
            other=g["h"] if g["away"]==team else g["a"]
            w+=score>other;l+=score<other
        return w,l
    return win,lose,record(win),record(lose),sum({g["away"],g["home"]}=={win,lose} for g in prior)
def article(g,history):
    win,lose,wr,lr,h2h=facts(g,history);margin=abs(g["a"]-g["h"])
    when=datetime.fromisoformat(g["date"]).astimezone(ET).strftime("%B %d, %Y")
    if g["status"]=="Forfeit":
        opener=(TEAMS[win]+" received a "+str(max(g["a"],g["h"]))+"–"+str(min(g["a"],g["h"]))+
                " forfeit result against "+TEAMS[lose]+" on "+when+". This is an administrative outcome, not evidence of gameplay.")
    else:
        opener=(TEAMS[win]+" defeated "+TEAMS[lose]+" "+str(max(g["a"],g["h"]))+"–"+str(min(g["a"],g["h"]))+
                " in a completed Continental Hockey League game on "+when+". The "+str(margin)+"-goal margin tells the story of the final score without guessing at unverified in-game moments.")
    return (opener+"\n\n"+TEAMS[g["away"]]+" was listed as the away team and "+TEAMS[g["home"]]+" as the home team. The two clubs finished with "+
        str(g["a"])+" and "+str(g["h"])+" recorded goals, respectively.\n\n"+
        "Based only on earlier non-forfeit results currently collected from the PlayCHL schedule, "+
        TEAMS[win]+" entered at "+str(wr[0])+"–"+str(wr[1])+" and "+TEAMS[lose]+" at "+str(lr[0])+"–"+str(lr[1])+
        ". The imported schedule shows "+str(h2h)+" earlier verified meeting(s) between these clubs. "+
        "Those figures describe the games currently imported, not necessarily official full-season standings.\n\n"+
        "The result now becomes part of both teams' recorded schedules. Individual scorers, assists, period-by-period scoring, goaltending statistics and game-changing plays are not asserted because this schedule feed does not verify them.")
def script(g):
    win,lose,_,_,_=facts(g,[])
    x,y=max(g["a"],g["h"]),min(g["a"],g["h"])
    if g["status"]=="Forfeit":
        return "CHL scoreboard update. "+TEAMS[win]+" receives a "+str(x)+" to "+str(y)+" forfeit result against "+TEAMS[lose]+". This is an administrative decision, not a played-game highlight."
    return ("It's time for your CHL postgame report! "+TEAMS[win]+" takes the win over "+TEAMS[lose]+", "+
            str(x)+" to "+str(y)+"! A "+str(x-y)+"-goal margin at the final horn. That's the verified final score from PlayCHL. We'll see what both teams bring to the next matchup!")
def graphic(g):
    im=Image.new("RGB",(1200,675),"#081725");d=ImageDraw.Draw(im)
    f="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    big=ImageFont.truetype(f,88);medium=ImageFont.truetype(f,32);small=ImageFont.truetype(f,22)
    d.rectangle((0,0,1200,16),fill="#20c8ff")
    d.rounded_rectangle((55,120,1145,555),radius=35,fill="#142d42")
    d.text((65,60),"CHL  |  VERIFIED POSTGAME RECAP",font=medium,fill="#b7dbef")
    d.text((100,185),g["away"],font=big,fill="white")
    d.text((825,185),g["home"],font=big,fill="white")
    d.text((430,210),str(g["a"])+" – "+str(g["h"]),font=big,fill="#ffdca0")
    d.text((100,320),TEAMS[g["away"]].upper(),font=medium,fill="#a8d1e8")
    d.text((825,320),TEAMS[g["home"]].upper(),font=medium,fill="#a8d1e8")
    d.text((500,405),g["status"].upper(),font=medium,fill="white")
    d.text((65,604),datetime.fromisoformat(g["date"]).astimezone(ET).strftime("%b %d, %Y")+"   |   playchl.com",font=small,fill="#b7dbef")
    stream=io.BytesIO();im.save(stream,format="PNG");return stream.getvalue()
async def narrate(txt):
    if not AUDIO:return None
    chunks=[]
    async for chunk in edge_tts.Communicate(txt,voice=VOICE).stream():
        if chunk["type"]=="audio":chunks.append(chunk["data"])
    data=b"".join(chunks)
    return data if 400<len(data)<7_000_000 else None
async def post(gid):
    async with lock:
        with conn() as c:
            row=c.execute("SELECT * FROM games WHERE id=?",(gid,)).fetchone()
            if not row:return "Game not found."
            if row["post_id"]:return "Already posted."
            history=[dict(x) for x in c.execute("SELECT * FROM games ORDER BY date")]
        g=dict(row);body=article(g,history);audio=None
        try:audio=await asyncio.wait_for(narrate(script(g)),timeout=50)
        except Exception as exc:log.warning("Narration failed for %s: %s",gid,exc)
        channel=bot.get_channel(CHANNEL) or await bot.fetch_channel(CHANNEL)
        e=discord.Embed(title="CHL RECAP | "+g["away"]+" "+str(g["a"])+" – "+str(g["h"])+" "+g["home"],description=body,color=0x1698CE)
        e.set_image(url="attachment://recap.png")
        e.set_footer(text="PlayCHL result-based report • No invented statistics or play-by-play")
        attachments=[discord.File(io.BytesIO(graphic(g)),filename="recap.png")]
        if audio:attachments.append(discord.File(io.BytesIO(audio),filename="recap-narration.mp3"))
        elif AUDIO:e.add_field(name="Audio",value="Narration service unavailable; the written recap is provided above.")
        message=await channel.send(embed=e,files=attachments,allowed_mentions=discord.AllowedMentions.none())
        with conn() as c:
            c.execute("UPDATE games SET posted=?,post_id=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),str(message.id),gid));c.commit()
        return "Recap posted for "+g["away"]+" vs "+g["home"]
async def refresh():
    data=await scrape()
    with conn() as c:
        added,first=ingest(c,data)
        queue=[x["id"] for x in c.execute("SELECT id FROM games WHERE posted IS NULL ORDER BY date LIMIT 6")]
    done=0
    for gid in queue:
        try:await post(gid);done+=1
        except Exception:log.exception("Failed to post %s; will retry",gid)
    return dict(scanned=len(data),added=added,first=first,posted=done)
@bot.event
async def on_ready():
    if getattr(bot,"ready_done",False):return
    bot.ready_done=True
    if GUILD:
        guild=discord.Object(id=GUILD);bot.tree.copy_global_to(guild=guild)
        synced=await bot.tree.sync(guild=guild)
    else:synced=await bot.tree.sync()
    log.info("Connected as %s; synced %d recap commands",bot.user,len(synced))
    if not ticker.is_running():ticker.start()
@tasks.loop(minutes=PERIOD)
async def ticker():
    try:log.info("Scan %s",await refresh())
    except Exception:log.exception("Schedule scan failed")
@ticker.before_loop
async def before():await bot.wait_until_ready()
def admin(i):return bool(i.guild and i.user.guild_permissions.manage_guild)
@bot.tree.command(name="recap_recent",description="List recent completed CHL games and IDs")
async def recap_recent(i:discord.Interaction):
    with conn() as c:r=c.execute("SELECT * FROM games ORDER BY date DESC LIMIT 12").fetchall()
    lines=[str(datetime.fromisoformat(x["date"]).astimezone(ET).strftime("%m/%d"))+" "+x["away"]+" "+str(x["a"])+"–"+str(x["h"])+" "+x["home"]+" | ID "+x["id"] for x in r]
    await i.response.send_message("\n".join(lines) if lines else "No game results imported yet.",ephemeral=True)
@bot.tree.command(name="recap_status",description="Check recap history and pending games")
async def recap_status(i:discord.Interaction):
    with conn() as c:
        total=c.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        sent=c.execute("SELECT COUNT(*) FROM games WHERE post_id IS NOT NULL").fetchone()[0]
        queued=c.execute("SELECT COUNT(*) FROM games WHERE posted IS NULL").fetchone()[0]
    await i.response.send_message("Completed games: "+str(total)+" | Recaps posted: "+str(sent)+" | Pending: "+str(queued)+" | Poll: "+str(PERIOD)+" min",ephemeral=True)
@bot.tree.command(name="recap_refresh",description="Admin: refresh completed games and post new recaps")
async def recap_refresh(i:discord.Interaction):
    if not admin(i):return await i.response.send_message("Manage Server permission required.",ephemeral=True)
    await i.response.defer(ephemeral=True)
    try:msg=str(await refresh())
    except Exception as exc:msg="Scan failed: "+str(exc)[:300]
    await i.followup.send(msg,ephemeral=True)
@bot.tree.command(name="recap_game",description="Admin: publish the recap for a completed game ID")
@app_commands.describe(game_id="From /recap_recent")
async def recap_game(i:discord.Interaction,game_id:str):
    if not admin(i):return await i.response.send_message("Manage Server permission required.",ephemeral=True)
    await i.response.defer(ephemeral=True)
    try:result=await post(game_id)
    except Exception as exc:result="Recap failed: "+str(exc)[:300]
    await i.followup.send(result,ephemeral=True)
if __name__=="__main__":
    if not TOKEN:raise SystemExit("Set NEW DISCORD_TOKEN in Railway")
    if not CHANNEL:raise SystemExit("Set RECAP_CHANNEL_ID in Railway")
    with conn():pass
    bot.run(TOKEN)
