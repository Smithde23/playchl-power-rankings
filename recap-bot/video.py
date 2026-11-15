"""Original cinematic CHL recap with moving broadcast graphics and narrated audio.

All visuals are graphic illustrations, not alleged gameplay footage. Uses
verified score and box score only. Original ambient soundbed, no licensed music.
"""
import asyncio, io, json, math, random, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W,H=1280,720
BG=(5,13,25);PALE=(241,248,255);GOLD=(242,198,108);RED=(213,42,57);BLUE=(36,155,232)
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(n):return ImageFont.truetype(FONT,n)

def fitted(draw,text,max_size,max_width,minimum=26):
    for size in range(max_size,minimum-1,-2):
        face=font(size)
        if draw.textbbox((0,0),text,font=face)[2]<=max_width:return face
    return font(minimum)

def arena(seed):
    rng=random.Random(seed)
    im=Image.new("RGB",(W,H),BG);d=ImageDraw.Draw(im,"RGBA")
    # Dark, illuminated arena with perspective ice and abstract cheering crowd.
    d.polygon([(0,340),(1280,340),(1280,720),(0,720)],fill=(22,48,72,255))
    d.polygon([(0,540),(1280,540),(1280,720),(0,720)],fill=(129,180,196,100))
    d.line((0,520,1280,520),fill=(242,245,254,190),width=6)
    for i in range(55):
        x=rng.randrange(-30,1310);y=rng.randrange(175,490)
        r=rng.randrange(2,6)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(109+rng.randrange(100),131,170,rng.randrange(35,120)))
    for i,(x,c) in enumerate(((180,RED),(1030,BLUE))):
        d.ellipse((x-60,80,x+60,200),fill=(*c,70))
        d.polygon([(x,126),(x-260,575),(x+280,575)],fill=(*c,18))
        d.ellipse((x-19,108,x+19,146),fill=(*c,230))
    # Rink markings, directional movement.
    for x in (190,640,1090):
        d.line((x,530,int(640+(x-640)*1.7),720),fill=(255,255,255,45),width=4)
    for j in range(50):
        x=rng.randrange(30,1230);y=rng.randrange(180,690);sz=rng.randrange(1,5)
        d.ellipse((x,y,x+sz,y+sz),fill=(201,229,255,rng.randrange(45,170)))
    return im

def silhouette(d):
    # Illustrative hockey player/stick silhouette: not footage of a specific match.
    d.ellipse((915,168,995,254),fill=(5,8,17,210))
    d.polygon([(907,235),(1015,225),(1060,405),(940,451),(868,328)],fill=(2,10,24,220))
    d.polygon([(943,410),(982,418),(940,575),(890,582)],fill=(3,9,20,240))
    d.polygon([(992,410),(1035,390),(1123,580),(1074,594)],fill=(3,9,20,240))
    d.line((965,304,1130,355),fill=(3,8,18,255),width=27)
    d.line((1122,354,1180,610),fill=(19,25,40,255),width=11)
    d.line((1180,607,1240,620),fill=(14,19,30,255),width=17)
    d.line((940,290,795,380),fill=(2,9,21,255),width=25)

def base(kind,serial):
    im=arena(serial+12);d=ImageDraw.Draw(im,"RGBA")
    d.rectangle((0,0,W,12),fill=(*RED,255))
    d.rectangle((0,12,W,18),fill=(*BLUE,190))
    d.rounded_rectangle((58,65,610,114),12,fill=(2,9,20,210),outline=(*GOLD,120),width=2)
    d.text((77,76),"C H L    |    WASHINGTON CAPITALS",font=font(22),fill=GOLD)
    if kind in ("opening","ending"):silhouette(d)
    d.rectangle((0,625,W,720),fill=(2,8,18,222))
    d.text((60,649),"THE CAPITALS FILES   •   POSTGAME CINEMATIC RECAP",font=font(22),fill=(180,212,240))
    d.text((1177,649),f"0{serial}/04",font=font(20),fill=GOLD)
    return im,d

def headline(d,top,bottom,sub=None):
    d.text((64,225),top,font=fitted(d,top,62,825),fill=PALE,stroke_width=1,stroke_fill=(5,20,38))
    d.rectangle((65,310,730,318),fill=RED)
    d.text((64,345),bottom,font=fitted(d,bottom,44,890),fill=GOLD)
    if sub:d.text((66,421),sub[:70],font=fitted(d,sub[:70],25,925),fill=(199,223,244))

def scenes(g,box):
    rival=g["home"] if g["away"]=="WSH" else g["away"]
    ca=g["a"] if g["away"]=="WSH" else g["h"]
    foe=g["h"] if g["away"]=="WSH" else g["a"]
    won=ca>foe
    a,d=base("opening",1)
    headline(d,"THE CAPITALS FILES","ONE NIGHT. ONE RESULT.","A CHL POSTGAME SPECIAL")
    out=[a]

    a,d=base("score",2)
    d.text((65,171),"THE FINAL HORN",font=font(38),fill=GOLD)
    d.text((62,267),f"WSH  {ca}  —  {foe}  {rival}",font=fitted(d,f"WSH  {ca}  —  {foe}  {rival}",88,1130),fill=PALE)
    d.rectangle((66,398,690,406),fill=RED)
    desc=("WASHINGTON TAKES THE WIN" if won else "WASHINGTON FALLS SHORT")
    d.text((66,443),desc,font=fitted(d,desc,40,1060),fill=GOLD)
    out.append(a)

    a,d=base("player",3)
    player=None
    if box:
        players=[p for p in box.get("players",[]) if p.get("team")=="WSH"]
        def points(p):
            try:return int(float(p.get("stats",{}).get("P",0)))
            except Exception:return 0
        players.sort(key=points,reverse=True)
        if players:player=players[0]
    if player:
        s=player.get("stats",{})
        d.text((66,178),"CAPITALS SPOTLIGHT",font=font(36),fill=GOLD)
        name=player.get("name","CAPITALS PLAYER")
        d.text((65,266),name,font=fitted(d,name,70,1000),fill=PALE)
        line=(f"{s.get('G','—')} GOALS  •  {s.get('A','—')} ASSISTS  •  {s.get('P','—')} POINTS"
              if player.get("pos")!="G" else
              f"{s.get('SV','—')} SAVES  •  {s.get('SV%','—')} SAVE PERCENTAGE")
        d.text((67,388),line,font=fitted(d,line,30,1070),fill=GOLD)
        d.text((67,467),"SOURCE: VERIFIED GAME BOX SCORE",font=font(21),fill=(183,205,229))
    else:
        headline(d,"BY THE NUMBERS",f"WSH {ca} — {foe} {rival}","Confirmed final score; player report not available")
    out.append(a)

    a,d=base("ending",4)
    headline(d,("THE VICTORY IS WASHINGTON'S" if won else "THE SEASON MOVES FORWARD"),
             "THE NEXT CHAPTER AWAITS","WASHINGTON CAPITALS  •  CONTINENTAL HOCKEY LEAGUE")
    out.append(a)
    return out

def seconds(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(path)],
                     capture_output=True,text=True,check=True,timeout=10)
    return float(json.loads(r.stdout)["format"]["duration"])

async def render(g,box,audio):
    if not audio:return None
    def work():
        with tempfile.TemporaryDirectory(prefix="chl-cine-") as td:
            root=Path(td)
            images=scenes(g,box)
            for i,img in enumerate(images):img.save(root/f"{i}.png")
            voice=root/"voice.mp3";voice.write_bytes(audio)
            duration=seconds(voice)
            hold=max(5,math.ceil((duration+1)/4))
            # Ken Burns camera movement gives the illustrated arena a continuous
            # tracking-shot feel; soft fades act as scene transitions.
            filters=[];inputs=[]
            for i in range(4):
                inputs+=["-loop","1","-framerate","18","-t",str(hold),"-i",str(root/f"{i}.png")]
                z="min(zoom+0.00075,1.18)"
                x="iw/2-(iw/zoom/2)+30*sin(on/35)"
                y="ih/2-(ih/zoom/2)"
                filters.append(f"[{i}:v]scale=1440:810,zoompan=z='{z}':x='{x}':y='{y}':d=1:s=960x540:fps=18,trim=duration={hold},setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.40,fade=t=out:st={hold-0.45}:d=0.45,format=yuv420p[v{i}]")
            filters.append("".join(f"[v{i}]" for i in range(4))+"concat=n=4:v=1:a=0[outv]")
            # Original 55Hz harmonic atmosphere mixed quietly beneath speech.
            filters.append(f"aevalsrc='0.011*sin(2*PI*55*t)+0.005*sin(2*PI*82.4*t)+0.004*sin(2*PI*110*t)':s=44100:d={duration+1}[bed]")
            filters.append("[4:a]aresample=44100,volume=1.0[voice]")
            filters.append("[voice][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.94[outa]")
            cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y"]+inputs+[
                "-i",str(voice),"-filter_complex",";".join(filters),
                "-map","[outv]","-map","[outa]",
                "-c:v","libx264","-preset","veryfast","-crf","29",
                "-c:a","aac","-b:a","128k","-movflags","+faststart",
                "-shortest",str(root/"recap.mp4")]
            proc=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
            if proc.returncode:
                raise RuntimeError(proc.stderr[-1500:])
            data=(root/"recap.mp4").read_bytes()
            return data if 50_000<len(data)<19_000_000 else None
    try:return await asyncio.wait_for(asyncio.to_thread(work),timeout=110)
    except Exception as exc:
        import logging
        logging.getLogger("chl.cinema").warning("Cinematic MP4 render failed: %s",exc)
        return None
