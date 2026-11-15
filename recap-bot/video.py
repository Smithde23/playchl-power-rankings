"""Original sports-news studio presentation for CHL Capitals postgame videos.

The presenters and rink visuals are GRAPHIC ILLUSTRATIONS, not real interviews,
licensed broadcast footage, or a reconstruction of game-winning plays. All
named players and statistics are sourced only from matched game box scores.
"""
import asyncio, json, math, random, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W,H=1280,720
NAVY=(7,18,36);MID=(15,36,62);WHITE=(240,248,255)
RED=(208,38,57);CYAN=(56,187,244);GOLD=(247,196,102)
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(size):return ImageFont.truetype(FONT,size)
def fit(d,text,max_size,max_width,min_size=15):
    text=str(text)
    for z in range(max_size,min_size-1,-1):
        face=font(z)
        if d.textbbox((0,0),text,font=face)[2]<=max_width:return face
    return font(min_size)
def txt(d,xy,value,size=30,color=WHITE,width=None):
    val=str(value)
    d.text(xy,val,font=fit(d,val,size,width) if width else font(size),fill=color)
def rounded(d,box,r=15,fill=MID,outline=None):
    d.rounded_rectangle(box,radius=r,fill=fill,outline=outline,width=2)

def person(d,cx,cy,female=False,active=False):
    """Original illustrated desk host; visuals intentionally not a real individual."""
    suit=(24,79,116) if not female else (65,45,100)
    hair=(27,23,32)
    skin=(174,122,94) if female else (204,155,123)
    glow=CYAN if active else (52,79,111)
    d.ellipse((cx-92,cy-166,cx+92,cy+94),fill=(13,27,48),outline=glow,width=4)
    # Neck and torso behind the desk.
    d.polygon([(cx-18,cy-24),(cx+19,cy-24),(cx+27,cy+19),(cx-26,cy+19)],fill=skin)
    d.polygon([(cx-83,cy+23),(cx-39,cy-10),(cx-1,cy+17),(cx+38,cy-10),(cx+84,cy+23),
               (cx+94,cy+120),(cx-94,cy+120)],fill=suit)
    d.polygon([(cx-26,cy-7),(cx,cy+25),(cx+23,cy-7),(cx+4,cy+66),(cx-3,cy+66)],fill=(222,228,238))
    d.ellipse((cx-36,cy-93,cx+36,cy-9),fill=skin)
    if female:
        d.ellipse((cx-42,cy-110,cx+42,cy-56),fill=hair)
        d.polygon([(cx-42,cy-80),(cx-51,cy+4),(cx-27,cy-8),(cx-29,cy-63)],fill=hair)
        d.polygon([(cx+30,cy-72),(cx+48,cy+9),(cx+28,cy-12)],fill=hair)
        d.arc((cx-17,cy-45,cx+18,cy-26),0,150,fill=(93,37,58),width=2)
    else:
        d.pieslice((cx-38,cy-103,cx+38,cy-42),180,360,fill=hair)
    d.ellipse((cx-18,cy-52,cx-12,cy-48),fill=(27,29,35))
    d.ellipse((cx+13,cy-52,cx+19,cy-48),fill=(27,29,35))
    d.arc((cx-13,cy-41,cx+13,cy-30),0,180,fill=(97,57,55),width=2)
    # Headset and desk microphone.
    d.arc((cx-40,cy-91,cx+40,cy-18),170,355,fill=(136,157,181),width=5)
    d.line((cx+37,cy-53,cx+62,cy-35),fill=(134,155,177),width=4)
    d.ellipse((cx+58,cy-38,cx+67,cy-28),fill=(232,235,244))
    rounded(d,(cx-91,cy+65,cx+91,cy+100),8,(7,21,38))
    txt(d,(cx-78,cy+73),"PLAY BY PLAY" if not female else "COLOR ANALYST",15,GOLD,154)

def studio_base(scene_number,highlight_speaker,female_analyst,game,box,card):
    im=Image.new("RGB",(W,H),NAVY);d=ImageDraw.Draw(im)
    # Original red/cyan sports studio, perspective ceiling lights and glass walls.
    for x in range(0,W,70):
        d.line((x,0,x+140,475),fill=(13,40,68),width=1)
    for y in range(100,500,70):d.line((0,y,W,y),fill=(20,52,82),width=2)
    d.polygon([(0,0),(W,0),(W,94),(0,119)],fill=(10,29,54))
    d.rectangle((0,0,W,12),fill=RED)
    d.rectangle((0,12,W,17),fill=CYAN)
    txt(d,(38,32),"CHL  |  CAPITALS POSTGAME LIVE",30,WHITE,760)
    txt(d,(1030,38),"STUDIO 27",22,GOLD,220)
    rounded(d,(37,128,1243,504),24,(9,25,46),outline=(39,96,131))
    # Back wall monitor, clearly labeled as statistics rather than game footage.
    rounded(d,(372,146,1176,439),10,(9,18,30),outline=CYAN)
    d.rectangle((384,158,1164,197),fill=(176,38,57))
    txt(d,(402,167),card["header"],23,WHITE,715)
    # Abstract on-screen rink simulation.
    d.rectangle((389,208,1159,429),fill=(18,67,92))
    for yy in (224,411):
        d.line((398,yy,1149,yy),fill=(172,207,221),width=3)
    d.ellipse((712,253,843,383),outline=(130,206,219),width=4)
    d.line((778,218,778,418),fill=(210,76,88),width=4)
    d.ellipse((515,272,600,358),outline=(191,225,235),width=3)
    d.ellipse((961,272,1045,358),outline=(191,225,235),width=3)
    # Animated highlight feel via slide-to-slide spotlight moving across rink.
    rng=random.Random(scene_number*811)
    x=530+(scene_number*109)%450
    y=277+((scene_number*41)%65)
    for k in range(5):
        d.ellipse((x-k*10-10,y-k*5-10,x-k*10+10,y-k*5+10),
                  fill=(225,205,127) if k==0 else (40+25*k,105+17*k,137+8*k))
    d.line((x-80,y-48,x+80,y+48),fill=(158,209,233),width=3)
    # Large dynamic stat graphics within the monitor.
    rounded(d,(419,262,1116,371),15,(5,22,39),outline=(49,133,166))
    txt(d,(435,271),card["title"],43,WHITE,655)
    txt(d,(435,328),card["detail"],23,GOLD,659)
    txt(d,(418,387),"ILLUSTRATED STATS REEL  •  NOT GAMEPLAY FOOTAGE",14,(201,222,234),700)
    # Presenter station below the monitor.
    person(d,175,408,female=False,active=highlight_speaker=="play")
    person(d,314,408,female=female_analyst,active=highlight_speaker=="analyst")
    d.polygon([(16,481),(560,481),(528,598),(0,598)],fill=(9,26,48))
    d.rectangle((0,598,W,641),fill=(170,34,52))
    d.rectangle((0,641,W,720),fill=(7,19,37))
    txt(d,(32,608),"CAPITALS POSTGAME  •  VERIFIED PLAYER BREAKDOWN",23,WHITE,1000)
    away=game["away"];home=game["home"]
    txt(d,(35,657),f"{away}  {game['a']}    —    {game['h']}  {home}",35,GOLD,720)
    txt(d,(1002,671),f"SCENE {scene_number+1:02d}",17,CYAN,200)
    return im

def cards(game,box):
    rival=game["home"] if game["away"]=="WSH" else game["away"]
    ca=game["a"] if game["away"]=="WSH" else game["h"]
    op=game["h"] if game["away"]=="WSH" else game["a"]
    items=[
        {"header":"POSTGAME HEADLINES","title":"THE FINAL HORN","detail":f"WASHINGTON {ca}  |  {rival} {op}"},
        {"header":"THE CAPITALS FILES","title":"TWO VOICES. ONE GAME.","detail":"Play-by-play + color commentary"},
    ]
    players=[p for p in (box or {}).get("players",[]) if p.get("team")=="WSH" and p.get("pos")!="G"]
    opponents=[p for p in (box or {}).get("players",[]) if p.get("team")==rival and p.get("pos")!="G"]
    def pts(p):
        try:return int(float(p.get("stats",{}).get("P",0)))
        except (TypeError,ValueError):return 0
    players.sort(key=pts,reverse=True);opponents.sort(key=pts,reverse=True)
    for p in players[:3]:
        s=p.get("stats",{})
        items.append({"header":"CAPITALS PLAYER SPOTLIGHT","title":p["name"][:30],
                      "detail":f"{s.get('G','—')} GOALS  ·  {s.get('A','—')} ASSISTS  ·  {s.get('P','—')} POINTS"})
    if opponents:
        p=opponents[0];s=p.get("stats",{})
        items.append({"header":"OPPOSITION STANDOUT","title":p["name"][:30],
                      "detail":f"{s.get('G','—')} GOALS  ·  {s.get('A','—')} ASSISTS  ·  {s.get('P','—')} POINTS"})
    goalie=[p for p in (box or {}).get("players",[]) if p.get("team")=="WSH" and p.get("pos")=="G"]
    if goalie:
        p=goalie[0];s=p["stats"]
        items.append({"header":"BETWEEN THE PIPES","title":p["name"][:30],
                      "detail":f"{s.get('SV','—')} SAVES  ·  {s.get('SV%','—')} SAVE %"})
    while len(items)<8:
        items.append({"header":"HIGHLIGHT-STYLE ANALYSIS","title":"MORE THAN A SCORE","detail":"Verified stats  •  No invented game events"})
    items.append({"header":"POSTGAME SIGN-OFF","title":"UNTIL NEXT GAME","detail":"Washington Capitals  ·  CHL 27"})
    return items

def scenes(game,box):
    spots=cards(game,box)
    is_female=random.choice((False,True))
    return [studio_base(i,"play" if i%2==0 else "analyst",is_female,game,box,item)
            for i,item in enumerate(spots)]

def seconds(path):
    result=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                          "-of","json",str(path)],capture_output=True,text=True,check=True,timeout=10)
    return float(json.loads(result.stdout)["format"]["duration"])

async def render(game,box,audio):
    if not audio:return None
    def work():
        with tempfile.TemporaryDirectory(prefix="chl-studio-") as td:
            root=Path(td)
            images=scenes(game,box)
            for i,img in enumerate(images):img.save(root/f"{i}.png")
            voice=root/"voice.mp3";voice.write_bytes(audio)
            duration=seconds(voice)
            n=len(images)
            hold=max(4,math.ceil((duration+0.7)/n))
            args=[];filters=[]
            for i in range(n):
                args+=["-loop","1","-framerate","16","-t",str(hold),"-i",str(root/f"{i}.png")]
                z="min(zoom+0.00025,1.07)"
                x="iw/2-(iw/zoom/2)"
                y="ih/2-(ih/zoom/2)"
                filters.append(f"[{i}:v]scale=1440:810,zoompan=z='{z}':x='{x}':y='{y}':d=1:s=960x540:fps=16,trim=duration={hold},setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.18,fade=t=out:st={hold-0.22}:d=0.22,format=yuv420p[v{i}]")
            filters.append("".join(f"[v{i}]" for i in range(n))+f"concat=n={n}:v=1:a=0[outv]")
            filters.append(f"aevalsrc='0.005*sin(2*PI*55*t)+0.003*sin(2*PI*82*t)':s=44100:d={duration+1}[bed]")
            filters.append(f"[{n}:a]aresample=44100,volume=1.0[voice]")
            filters.append("[voice][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[outa]")
            cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y"]+args+[
                "-i",str(voice),"-filter_complex",";".join(filters),
                "-map","[outv]","-map","[outa]","-c:v","libx264",
                "-preset","ultrafast","-crf","31","-c:a","aac","-b:a","112k",
                "-movflags","+faststart","-shortest",str(root/"recap.mp4")]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=170)
            if result.returncode:raise RuntimeError(result.stderr[-1500:])
            data=(root/"recap.mp4").read_bytes()
            return data if 50_000<len(data)<19_000_000 else None
    try:return await asyncio.wait_for(asyncio.to_thread(work),timeout=180)
    except Exception as exc:
        import logging
        logging.getLogger("chl.studio").warning("Studio MP4 render failed: %s",exc)
        return None
