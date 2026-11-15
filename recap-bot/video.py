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

def scenes(game,box,female_analyst=False):
    spots=cards(game,box)
    is_female=female_analyst
    return [studio_base(i,"play" if i%2==0 else "analyst",is_female,game,box,item)
            for i,item in enumerate(spots)]

def seconds(path):
    result=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                          "-of","json",str(path)],capture_output=True,text=True,check=True,timeout=10)
    return float(json.loads(result.stdout)["format"]["duration"])

def action_frame(game,card,frame_index,total_frames,analyst_female=False):
    """Original animated ice-hockey B-roll, not an actual CHL game clip.

    Each frame is drawn from scratch: skaters, sticks, puck, ice, camera
    motion, score ribbon and a small two-host inset. This supplies genuine
    moving video without attributing a simulated play to a real participant.
    """
    t=frame_index/12.0
    im=Image.new("RGB",(W,H),(6,17,33))
    d=ImageDraw.Draw(im)
    rng=random.Random(501)
    # Perspective ice arena, illuminated crowd and rink markings.
    d.rectangle((0,0,W,110),fill=(9,27,49))
    for row in range(4):
        for j in range(90):
            x=7+j*15+row%2*7
            y=111+row*22
            shade=28+(j*17+row*11)%85
            d.ellipse((x,y,x+4,y+4),fill=(shade,shade+13,shade+36))
    d.polygon([(24,205),(1256,205),(1190,620),(90,620)],fill=(183,214,226))
    d.line((38,210,1243,210),fill=(250,251,252),width=8)
    d.line((90,619,1190,619),fill=(244,248,250),width=8)
    for xx in (330,905):
        d.line((xx,213,xx+((xx-640)*0.09),618),fill=(168,65,76),width=6)
    d.line((640,211,640,620),fill=(69,128,182),width=6)
    d.ellipse((551,335,730,498),outline=(83,145,191),width=5)
    # Nets are clearly illustrative, with a live-replay camera perspective.
    for gx in (70,1100):
        d.rounded_rectangle((gx,345,gx+95,455),12,outline=(194,44,57),width=7)
        for k in range(1,5):
            d.line((gx+k*18,351,gx+k*18,451),fill=(120,155,173),width=2)
    # Continuous puck pursuit, with opposing clubs skaters in motion.
    puck_x=210+int((t*122)%820)
    puck_y=386+int(58*math.sin(t*1.6))
    d.line((puck_x-72,puck_y-22,puck_x-8,puck_y),fill=(107,156,172),width=3)
    d.ellipse((puck_x-9,puck_y-5,puck_x+9,puck_y+5),fill=(13,16,22))
    def skater(x,y,shirt,accent,heading):
        bob=int(3*math.sin(t*5+x/57))
        y+=bob
        d.ellipse((x-24,y+20,x+24,y+32),fill=(103,142,156))
        d.line((x-10,y+7,x-18,y+31),fill=(21,32,47),width=7)
        d.line((x+10,y+7,x+19,y+29),fill=(21,32,47),width=7)
        d.ellipse((x-27,y-21,x+27,y+19),fill=shirt,outline=accent,width=4)
        d.ellipse((x-14,y-47,x+14,y-19),fill=(38,43,58),outline=(232,236,241),width=3)
        d.line((x+heading*14,y-3,x+heading*51,y+23),fill=(37,42,53),width=6)
        d.line((x+heading*51,y+23,x+heading*76,y+24),fill=(31,34,39),width=4)
    for i in range(3):
        xx=180+i*180+int(42*math.sin(t*1.7+i))
        yy=310+i*69+int(24*math.cos(t*1.8+i))
        skater(xx,yy,(169,35,53),(238,223,226),1)
    for i in range(3):
        xx=1030-i*178-int(47*math.sin(t*1.5+i*1.3))
        yy=304+i*75+int(20*math.sin(t*1.6+i))
        skater(xx,yy,(233,238,245),(68,102,141),-1)
    # Camera panning ribbons and quick light sweeps.
    sweep=int((t*185)%W)
    d.polygon([(sweep-150,203),(sweep-126,203),(sweep+210,618),(sweep+185,618)],
              fill=(215,231,240))
    d.rectangle((0,0,W,85),fill=(8,17,34))
    d.rectangle((0,0,W,9),fill=RED)
    txt(d,(31,23),"CHL TOP PERFORMANCES",30,WHITE,620)
    txt(d,(1048,28),"RECAP REEL",18,GOLD,200)
    # Leaderboard panel is an editorial ranking of real box-score totals,
    # explicitly not a claim that the animation depicts those plays.
    rounded(d,(35,491,870,593),16,(5,19,39),outline=(62,129,162))
    txt(d,(52,501),card.get("title","CAPITALS RECAP"),38,WHITE,770)
    txt(d,(53,554),card.get("detail","VERIFIED MATCH RESULT"),20,GOLD,770)
    d.rectangle((0,631,W,720),fill=(6,16,34))
    d.rectangle((0,631,W,644),fill=RED)
    txt(d,(28,659),f"{game['away']} {game['a']}    —    {game['h']} {game['home']}",31,WHITE,575)
    txt(d,(618,663),"AI-ILLUSTRATED HOCKEY ACTION • NOT ACTUAL GAME FOOTAGE",
        15,(175,211,230),650)
    # Two commentators remain visible as stylized mini portrait windows.
    rounded(d,(914,464,1252,624),12,(7,22,42),outline=(68,127,162))
    person(d,1004,596,female=False,active=(frame_index//27)%2==0)
    person(d,1164,596,female=analyst_female,active=(frame_index//27)%2==1)
    # Restore panels above the projected portrait desk so they stay unclipped.
    d.rectangle((908,607,1258,627),fill=(8,21,40))
    txt(d,(937,610),"PLAY-BY-PLAY   |   ANALYST",15,GOLD,304)
    return im

def verified_reel(game,box):
    panels=cards(game,box)
    # Keep a compact editorial sequence; no fabricated Top 10 "plays".
    return panels[:10]

def generate_action_loop(root,game,box,female_analyst):
    reel=verified_reel(game,box)
    folder=root/"frames"
    folder.mkdir()
    fps=12
    total_frames=max(72,len(reel)*12)
    for i in range(total_frames):
        # Each confirmed performance receives a short rotating visual panel,
        # while synthetic hockey movement continues underneath.
        card=reel[min(len(reel)-1,int(i/12))]
        im=action_frame(game,card,i,total_frames,female_analyst)
        im.resize((960,540),Image.Resampling.BILINEAR).save(folder/f"f{i:04d}.jpg",quality=73)
    output=root/"illustrated-hockey.mp4"
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
         "-framerate",str(fps),"-i",str(folder/"f%04d.jpg"),
         "-c:v","libx264","-preset","ultrafast","-crf","31",
         "-pix_fmt","yuv420p","-movflags","+faststart",str(output)]
    completed=subprocess.run(cmd,capture_output=True,text=True,timeout=95)
    if completed.returncode:raise RuntimeError(completed.stderr[-1200:])
    return output

async def render(game,box,audio,female_analyst=False):
    if not audio:return None
    def work():
        with tempfile.TemporaryDirectory(prefix="chl-reel-") as td:
            root=Path(td)
            voice=root/"voice.mp3";voice.write_bytes(audio)
            video=generate_action_loop(root,game,box,female_analyst)
            duration=seconds(voice)
            out=root/"recap.mp4"
            # Loop the original synthetic action, while placing existing
            # separately synthesized two-host commentary above it.
            cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
                 "-stream_loop","-1","-i",str(video),"-i",str(voice),
                 "-filter_complex",
                 f"aevalsrc='0.003*sin(2*PI*55*t)+0.002*sin(2*PI*82*t)':s=44100:d={duration+0.2}[bed];"
                 "[1:a]aresample=44100[voice];"
                 "[voice][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
                 "-map","0:v","-map","[a]","-t",str(duration),
                 "-c:v","libx264","-preset","ultrafast","-crf","31",
                 "-r","12","-c:a","aac","-b:a","112k",
                 "-pix_fmt","yuv420p","-movflags","+faststart","-shortest",str(out)]
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
            if result.returncode:raise RuntimeError(result.stderr[-1300:])
            data=out.read_bytes()
            return data if 50_000<len(data)<19_000_000 else None
    try:return await asyncio.wait_for(asyncio.to_thread(work),timeout=195)
    except Exception as exc:
        import logging
        logging.getLogger("chl.reel").warning("Illustrated recap MP4 failed: %s",exc)
        return None
