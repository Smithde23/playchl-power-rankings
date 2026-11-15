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
from stats import discover_schedule_links,fetch_box,noteworthy
from video import render as render_video
from chelhead import fetch_fallback
load_dotenv();logging.basicConfig(level=logging.INFO);log=logging.getLogger("chl.recaps")
TEAMS={"ANA":"Anaheim","BUF":"Buffalo","CGY":"Calgary","DET":"Detroit","MIN":"Minnesota","SEA":"Seattle","SJS":"San Jose","UTAH":"Utah","VGK":"Vegas","WSH":"Washington"}
MON={m:i+1 for i,m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
ET=ZoneInfo("America/New_York")
FOCUS_TEAM="WSH"
def is_focus_game(game):
    return FOCUS_TEAM in (game["away"],game["home"])
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
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);
    CREATE TABLE IF NOT EXISTS box_cache(game_id TEXT PRIMARY KEY,game_url TEXT,box_json TEXT,updated_at TEXT);""")
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
            links=await discover_schedule_links(page,data)
            for g in data:
                if g["id"] in links:g["game_url"]=links[g["id"]]
            log.info("Matched %d Washington game detail links",len(links))
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
        if g.get("game_url"):
            c.execute("INSERT OR IGNORE INTO box_cache(game_id,game_url,box_json,updated_at) VALUES(?,?,NULL,NULL)",(g["id"],g["game_url"]))
            c.execute("UPDATE box_cache SET game_url=? WHERE game_id=?",(g["game_url"],g["id"]))
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
def article(g,history,box=None):
    win,lose,wr,lr,h2h=facts(g,history);margin=abs(g["a"]-g["h"])
    when=datetime.fromisoformat(g["date"]).astimezone(ET).strftime("%B %d, %Y")
    if g["status"]=="Forfeit":
        opener=(TEAMS[win]+" received a "+str(max(g["a"],g["h"]))+"–"+str(min(g["a"],g["h"]))+
                " forfeit result against "+TEAMS[lose]+" on "+when+". This is an administrative outcome, not evidence of gameplay.")
    else:
        opener=(TEAMS[win]+" defeated "+TEAMS[lose]+" "+str(max(g["a"],g["h"]))+"–"+str(min(g["a"],g["h"]))+
                " in a completed Continental Hockey League game on "+when+". The "+str(margin)+"-goal margin tells the story of the final score without guessing at unverified in-game moments.")
    base=(opener+"\n\n"+TEAMS[g["away"]]+" was listed as the away team and "+TEAMS[g["home"]]+" as the home team. The two clubs finished with "+
        str(g["a"])+" and "+str(g["h"])+" recorded goals, respectively.\n\n"+
        "Based only on earlier non-forfeit results currently collected from the PlayCHL schedule, "+
        TEAMS[win]+" entered at "+str(wr[0])+"–"+str(wr[1])+" and "+TEAMS[lose]+" at "+str(lr[0])+"–"+str(lr[1])+
        ". The imported schedule shows "+str(h2h)+" earlier verified meeting(s) between these clubs. "+
        "Those figures describe the games currently imported, not necessarily official full-season standings.\n\n"+
        "The result now becomes part of both teams\' recorded schedules.")
    return cinematic(g,box,base)

def cinematic(g,box,base):
    """Cinematic structure with verifiable tension; no fabricated shifts, goals or sequences."""
    aw=TEAMS[g["away"]];ho=TEAMS[g["home"]]
    cap_won=(g["away"]=="WSH" and g["a"]>g["h"]) or (g["home"]=="WSH" and g["h"]>g["a"])
    foe=ho if g["away"]=="WSH" else aw
    lead=("THE CAPITALS ANSWER THE CALL" if cap_won else "A NIGHT OF HARD LESSONS FOR WASHINGTON")
    margin=abs(g["a"]-g["h"])
    intro=(f"**{lead}**\n\nUnder the CHL spotlight, Washington met {foe} with another result on the line. "
           f"By the final horn, the scoreboard read {g['away']} {g['a']} – {g['h']} {g['home']}. "
           +("Washington owned the final result. " if cap_won else "Washington was on the wrong side of the final score. ")
           +("Only one goal separated the teams." if margin==1 else f"The final margin was {margin} goals."))
    if g["status"]=="Forfeit":
        return ("**OFFICIAL RESULT — FORFEIT**\n\n"+base+
                "\n\nThis outcome reflects an administrative result, not a verified on-ice contest.")
    if not box:
        return (intro+"\n\n**THE SCOREBOARD**\n"+base+
                "\n\n**BEYOND THE FINAL HORN**\nThis is the confirmed result. No player names or plays are attributed to this game because its individual box score could not be verified.")
    match=box.get("match",{})
    metrics=[]
    for metric in ("Shots","Hits","TOA","Faceoffs%","Blocks","Takeaways","Giveaways"):
        vals=match.get(metric)
        if vals and len(vals)==2:metrics.append(metric+": "+str(vals[0])+" / "+str(vals[1]))
    stats=("\n".join(metrics) if metrics else "No validated team comparison available.")
    players=[]
    for team in (g["away"],g["home"]):
        chosen=noteworthy(box,team)
        for p in chosen[:3]:
            s=p["stats"]
            fragments=[]
            for k,v in (("G","goals"),("A","assists"),("P","points"),("SH","shots"),("HIT","hits"),("SV","saves"),("SV%","save rate")):
                if k in s:fragments.append(str(s[k])+" "+v)
            if fragments:players.append("**"+p["name"]+" ("+team+")** — "+", ".join(fragments))
    names="\n".join(players) if players else "Individual box-score entries not independently validated."
    story=[]
    for team in (g["away"],g["home"]):
        top=noteworthy(box,team)
        if not top:continue
        p=top[0];s=p["stats"]
        if s.get("P") and s["P"]!="0":
            story.append(p["name"]+" supplied "+s["P"]+" recorded point(s) for "+TEAMS[team]+".")
        elif s.get("SV"):story.append(p["name"]+" logged "+s["SV"]+" saves for "+TEAMS[team]+".")
    narrative=" ".join(story)
    return (intro+"\n\n**THE NAMES BEHIND THE NUMBERS**\n"+narrative+
            "\n\n**PLAYER BOX SCORE**\n"+names+
            "\n\n**GAME BY THE NUMBERS**\n"+stats+
            "\n\n**THE FINAL CHAPTER**\n"+base+
            "\n\nSource: "+box["url"]+
            "\n\n*The recap describes verified totals, not an invented scoring timeline or play-by-play.*")

def voice_story(g,box):
    """An original postgame narrative. Every named performance comes from one matched boxscore."""
    if g["status"]=="Forfeit":return script(g)
    rival=g["home"] if g["away"]=="WSH" else g["away"]
    opponent=TEAMS[rival]
    capscore=g["a"] if g["away"]=="WSH" else g["h"]
    oppscore=g["h"] if g["away"]=="WSH" else g["a"]
    won=capscore>oppscore
    margin=abs(capscore-oppscore)
    if won:
        opening=(f"Under the lights of the Continental Hockey League, Washington makes a statement. "
                 f"The Capitals take down {opponent}, {capscore} to {oppscore}.")
    else:
        opening=(f"Some nights leave a mark. In a high-stakes Continental Hockey League matchup, "
                 f"Washington falls to {opponent}, {capscore} to {oppscore}.")
    tone=("One goal made the difference on the final scoreboard. "
          if margin==1 else f"The final score shows a margin of {margin} goals. ")
    if not box:
        return (opening+" "+tone+"The scoreboard is confirmed, but player performances have not been "
                "verified for this match. The Capitals' next chapter is still unwritten.")
    caps=noteworthy(box,"WSH")
    rivals=noteworthy(box,rival)
    speech=[opening,tone]
    def describe(p):
        name=p["name"];s=p["stats"]
        if p.get("pos")=="G" and "SV" in s:
            return f"{name} is credited with {s['SV']} saves for this game."
        gval=s.get("G");aval=s.get("A");points=s.get("P")
        if not points:return None
        if gval and aval:
            return f"{name} delivers {points} points: {gval} goals and {aval} assists."
        return f"{name} records {points} points."
    for i,p in enumerate(caps[:3]):
        line=describe(p)
        if line:
            if i==0:speech.append("For Washington, one name rises off the score sheet.")
            speech.append(line)
    for i,p in enumerate(rivals[:2]):
        line=describe(p)
        if line:
            if i==0:speech.append("Across the ice, "+opponent+" has a story of its own.")
            speech.append(line)
    stats=box.get("match",{})
    if "Shots" in stats and len(stats["Shots"])==2:
        speech.append("The verified team comparison lists "+str(stats["Shots"][0])+
                      " shots for one club and "+str(stats["Shots"][1])+" for the other.")
    if won:
        speech.append("When the score is settled, the Capitals own the result. The numbers stay on the record. The season moves forward.")
    else:
        speech.append("For Washington, the defeat is part of the record, but not the end of the story. The next game waits. And so does the response.")
    return " ".join(speech)

def script(g,box=None):
    win,lose,_,_,_=facts(g,[])
    x,y=max(g["a"],g["h"]),min(g["a"],g["h"])
    if g["status"]=="Forfeit":
        return "CHL scoreboard update. "+TEAMS[win]+" receives a "+str(x)+" to "+str(y)+" forfeit result against "+TEAMS[lose]+". This is an administrative decision, not a played-game highlight."
    return ("It's time for your CHL postgame report! "+TEAMS[win]+" takes the win over "+TEAMS[lose]+", "+
            str(x)+" to "+str(y)+"! A "+str(x-y)+"-goal margin at the final horn. That's the verified final score from PlayCHL. We'll see what both teams bring to the next matchup!")
def graphic(g,box=None):
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
    if box:
        top=noteworthy(box,"WSH")
        if top:
            p=top[0];s=p["stats"]
            description=p["name"]+"  |  "+s.get("G","0")+" G  "+s.get("A","0")+" A  "+s.get("P","0")+" P"
            d.rounded_rectangle((90,480,1110,544),radius=13,fill="#264a67")
            d.text((115,496),"CAPITALS SPOTLIGHT: "+description[:64],font=small,fill="#fff3d2")
    d.text((65,604),datetime.fromisoformat(g["date"]).astimezone(ET).strftime("%b %d, %Y")+"   |   playchl.com",font=small,fill="#b7dbef")
    stream=io.BytesIO();im.save(stream,format="PNG");return stream.getvalue()
async def narrate(txt):
    if not AUDIO:return None
    chunks=[]
    async for chunk in edge_tts.Communicate(txt,voice=VOICE).stream():
        if chunk["type"]=="audio":chunks.append(chunk["data"])
    data=b"".join(chunks)
    return data if 400<len(data)<7_000_000 else None
async def post(gid,force=False):
    async with lock:
        with conn() as c:
            row=c.execute("SELECT * FROM games WHERE id=?",(gid,)).fetchone()
            if not row:return "Game not found."
            if not is_focus_game(row):return "Only Washington Capitals (WSH) games are eligible for recaps."
            if row["post_id"] and not force:return "Already posted. Use /recap_redo to regenerate."
            history=[dict(x) for x in c.execute("SELECT * FROM games ORDER BY date")]
        g=dict(row)
        box=None
        if g["status"]!="Forfeit":
            with conn() as c:
                cached=c.execute("SELECT game_url,box_json FROM box_cache WHERE game_id=?",(gid,)).fetchone()
            if cached:
                if cached["box_json"]:
                    try:box=__import__("json").loads(cached["box_json"])
                    except Exception:pass
                elif cached["game_url"]:
                    try:
                        async with async_playwright() as p:
                            browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
                            try:box=await fetch_box(browser,cached["game_url"],g["away"],g["home"],g["a"],g["h"])
                            finally:await browser.close()
                        if box:
                            with conn() as c:
                                c.execute("UPDATE box_cache SET box_json=?,updated_at=? WHERE game_id=?",(__import__("json").dumps(box),datetime.now(timezone.utc).isoformat(),gid));c.commit()
                    except Exception as exc:log.warning("Boxscore fetch failed: %s",exc)
        if box is None and g["status"]=="Final":
            try:
                box=await asyncio.wait_for(fetch_fallback(g),timeout=65)
                if box:
                    with conn() as c:
                        c.execute("INSERT OR REPLACE INTO box_cache(game_id,game_url,box_json,updated_at) VALUES(?,?,?,?)",
                                  (gid,box["url"],__import__("json").dumps(box),datetime.now(timezone.utc).isoformat()))
                        c.commit()
            except Exception as exc:log.warning("CHEL HEAD fallback failed for %s: %s",gid,exc)
        body=article(g,history,box);audio=None
        try:audio=await asyncio.wait_for(narrate(voice_story(g,box)),timeout=50)
        except Exception as exc:log.warning("Narration failed for %s: %s",gid,exc)
        channel=bot.get_channel(CHANNEL) or await bot.fetch_channel(CHANNEL)
        e=discord.Embed(title="CHL RECAP | "+g["away"]+" "+str(g["a"])+" – "+str(g["h"])+" "+g["home"],description=body,color=0x1698CE)
        e.set_image(url="attachment://recap.png")
        if box and box.get("url"):
            provider="CHEL HEAD" if box.get("source")=="chelhead" else "PlayCHL"
            e.add_field(name="Verified player statistics",value="[View "+provider+" source]("+box["url"]+")",inline=False)
        e.set_footer(text="PlayCHL result-based report • No invented statistics or play-by-play")
        attachments=[discord.File(io.BytesIO(graphic(g,box)),filename="recap.png")]
        motion=await render_video(g,box,audio)
        if motion:attachments.append(discord.File(io.BytesIO(motion),filename="capitals-cinematic-recap.mp4"))
        if audio and not motion:attachments.append(discord.File(io.BytesIO(audio),filename="recap-narration.mp3"))
        elif not audio and AUDIO:e.add_field(name="Audio",value="Narration service unavailable; the written recap is provided above.")
        message=await channel.send(embed=e,files=attachments,allowed_mentions=discord.AllowedMentions.none())
        with conn() as c:
            c.execute("UPDATE games SET posted=?,post_id=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),str(message.id),gid));c.commit()
        return "Recap posted for "+g["away"]+" vs "+g["home"]
async def refresh():
    data=await scrape()
    with conn() as c:
        added,first=ingest(c,data)
        queue=[x["id"] for x in c.execute("SELECT id FROM games WHERE posted IS NULL AND (away=? OR home=?) ORDER BY date LIMIT 6",(FOCUS_TEAM,FOCUS_TEAM))]
    done=0
    for gid in queue:
        try:await post(gid);done+=1
        except Exception:log.exception("Failed to post %s; will retry",gid)
    if not getattr(bot,"chel_probe_done",False):
        bot.chel_probe_done=True
        with conn() as dbc:
            recent=[dict(x) for x in dbc.execute(
                "SELECT * FROM games WHERE (away='WSH' OR home='WSH') AND status='Final' ORDER BY date DESC LIMIT 10")]
        now=datetime.now(timezone.utc)
        candidates=[g for g in recent if 0<=(now-datetime.fromisoformat(g["date"])).total_seconds()<2*86400]
        if candidates:
            try:
                sample=candidates[0]
                probe=await asyncio.wait_for(fetch_fallback(sample),timeout=65)
                log.info("CHELHEAD self-check game=%s opponent=%s score=%s-%s players=%s",
                         sample["id"],sample["home"] if sample["away"]=="WSH" else sample["away"],
                         sample["a"],sample["h"],len(probe["players"]) if probe else "unverified")
            except Exception:log.exception("CHELHEAD self-check failed")
        else:log.info("CHELHEAD self-check: no recent eligible Capitals games within 48h")
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
@bot.tree.command(name="recap_recent",description="List recent Washington Capitals games and IDs")
async def recap_recent(i:discord.Interaction):
    with conn() as c:r=c.execute("SELECT * FROM games WHERE away=? OR home=? ORDER BY date DESC LIMIT 12",(FOCUS_TEAM,FOCUS_TEAM)).fetchall()
    lines=[str(datetime.fromisoformat(x["date"]).astimezone(ET).strftime("%m/%d"))+" "+x["away"]+" "+str(x["a"])+"–"+str(x["h"])+" "+x["home"]+" | ID "+x["id"] for x in r]
    await i.response.send_message("\n".join(lines) if lines else "No game results imported yet.",ephemeral=True)
@bot.tree.command(name="recap_status",description="Check Washington Capitals recap history and pending games")
async def recap_status(i:discord.Interaction):
    with conn() as c:
        total=c.execute("SELECT COUNT(*) FROM games WHERE away=? OR home=?",(FOCUS_TEAM,FOCUS_TEAM)).fetchone()[0]
        sent=c.execute("SELECT COUNT(*) FROM games WHERE post_id IS NOT NULL AND (away=? OR home=?)",(FOCUS_TEAM,FOCUS_TEAM)).fetchone()[0]
        queued=c.execute("SELECT COUNT(*) FROM games WHERE posted IS NULL AND (away=? OR home=?)",(FOCUS_TEAM,FOCUS_TEAM)).fetchone()[0]
    await i.response.send_message("Completed games: "+str(total)+" | Recaps posted: "+str(sent)+" | Pending: "+str(queued)+" | Poll: "+str(PERIOD)+" min",ephemeral=True)
@bot.tree.command(name="recap_refresh",description="Admin: refresh completed games and post new recaps")
async def recap_refresh(i:discord.Interaction):
    if not admin(i):return await i.response.send_message("Manage Server permission required.",ephemeral=True)
    await i.response.defer(ephemeral=True)
    try:msg=str(await refresh())
    except Exception as exc:msg="Scan failed: "+str(exc)[:300]
    await i.followup.send(msg,ephemeral=True)
@bot.tree.command(name="recap_cheltest",description="Admin: test CHEL HEAD stats matching for a Capitals game")
@app_commands.describe(game_id="Copy a Washington game ID from /recap_recent")
async def recap_cheltest(i:discord.Interaction,game_id:str):
    if not admin(i):return await i.response.send_message("Manage Server permission required.",ephemeral=True)
    await i.response.defer(ephemeral=True)
    with conn() as c:
        row=c.execute("SELECT * FROM games WHERE id=? AND (away='WSH' OR home='WSH')",(game_id,)).fetchone()
    if not row:return await i.followup.send("Unknown Capitals game ID.",ephemeral=True)
    g=dict(row)
    try:
        box=await asyncio.wait_for(fetch_fallback(g),timeout=65)
        if not box:
            msg="CHEL HEAD did not verify a unique matching club report for this game. No player stats will be invented."
        else:
            members=[x for x in box["players"] if x["team"]=="WSH"]
            parts=[]
            for x in members[:10]:
                stats=x["stats"]
                parts.append(x["name"]+": "+", ".join(k+"="+str(stats[k]) for k in ("G","A","P","SV") if k in stats))
            msg=("Verified CHEL HEAD popup: "+str(len(box["players"]))+" total players ("
                 +str(len(members))+" Capitals).\n"+"\n".join(parts))
    except Exception as exc:msg="CHEL HEAD test failed: "+str(exc)[:250]
    await i.followup.send(msg[:1900],ephemeral=True)

@bot.tree.command(name="recap_redo",description="Admin: regenerate a Washington game as an updated cinematic recap")
@app_commands.describe(game_id="Copy the game's ID from /recap_recent")
async def recap_redo(i:discord.Interaction,game_id:str):
    if not admin(i):return await i.response.send_message("Manage Server permission required.",ephemeral=True)
    await i.response.defer(ephemeral=True)
    with conn() as con:
        game=con.execute("SELECT id FROM games WHERE id=? AND (away='WSH' OR home='WSH')",(game_id,)).fetchone()
    if not game:return await i.followup.send("Unknown Capitals game ID.",ephemeral=True)
    try:result=await post(game_id,force=True)
    except Exception as exc:result="Could not regenerate: "+str(exc)[:350]
    await i.followup.send(result+"\nThe earlier recap is preserved; this posts an updated copy.",ephemeral=True)

@bot.tree.command(name="recap_game",description="Admin: publish a Washington Capitals game recap")
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
