"""Create an original, cinematic, scoreboard-led narrated MP4.
No gameplay footage and no fake player/event photos are used.
"""
import asyncio,io,os,subprocess,tempfile,math,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
BLUE="#05121f";NAVY="#0b2337";GOLD="#e9be69";WHITE="#f1f7ff"
def typeface(size):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",size)
def card(title,main,sub,serial):
    im=Image.new("RGB",(1280,720),BLUE);d=ImageDraw.Draw(im)
    d.polygon([(0,0),(1280,0),(970,720),(680,720)],fill=NAVY)
    for j in range(20):
        x=j*85;d.line((x,0,x-300,720),fill="#112c43",width=2)
    d.rectangle((0,0,1280,13),fill=GOLD)
    d.text((80,70),"C H L  /  W A S H I N G T O N",font=typeface(33),fill=GOLD)
    d.text((80,235),title[:30],font=typeface(45),fill=WHITE)
    d.text((80,315),main[:23],font=typeface(90),fill=WHITE)
    d.text((82,445),sub[:65],font=typeface(28),fill="#a9c9dd")
    d.text((83,640),"THE CAPITALS FILES     •     VERIFIED POSTGAME REPORT",font=typeface(19),fill="#799caf")
    d.text((1150,635),f"{serial:02d} / 04",font=typeface(20),fill=GOLD)
    return im
def scenes(g,box=None):
    cap=g["a"] if g["away"]=="WSH" else g["h"]
    foe=g["h"] if g["away"]=="WSH" else g["a"]
    rival=g["home"] if g["away"]=="WSH" else g["away"]
    win=cap>foe
    r=[card("THE CAPITALS FILES","GAME RECAP","CONTINENTAL HOCKEY LEAGUE",1),
       card("THE FINAL SCORE",f"WSH  {cap} — {foe}  {rival}","WASHINGTON CAPITALS  /  "+("VICTORY" if win else "DEFEAT"),2)]
    if box and box.get("players"):
        members=[p for p in box["players"] if p.get("team")=="WSH" and p.get("stats")]
        members.sort(key=lambda p:int(p["stats"].get("P","0") or 0),reverse=True)
        if members:
            p=members[0];s=p["stats"]
            r.append(card("CAPITALS PLAYER FOCUS",p["name"][:19],f"{s.get('G','—')} GOALS   {s.get('A','—')} ASSISTS   {s.get('P','—')} POINTS",3))
    if len(r)==2:r.append(card("BY THE NUMBERS",f"{cap} TO {foe}","CONFIRMED FINAL RESULT",3))
    r.append(card("THE STORY CONTINUES","NEXT CHAPTER","WASHINGTON CAPITALS • CHL POSTGAME",4))
    return r
async def render(g,box,audio):
    """Generate short 16:9 narrated video; if audio unavailable, don't pretend MP4 includes narration."""
    if not audio:return None
    def blocking():
        with tempfile.TemporaryDirectory(prefix="chl-video-") as work:
            root=Path(work)
            images=scenes(g,box)
            for i,img in enumerate(images):
                img.save(root/f"{i:02d}.png")
            (root/"voice.mp3").write_bytes(audio)
            probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(root/"voice.mp3")],capture_output=True,text=True,check=True,timeout=10)
            seconds=float(json.loads(probe.stdout)["format"]["duration"])
            hold=max(5,math.ceil((seconds+2)/len(images)))
            playlist=[]
            for i in range(len(images)):
                playlist+=["file '"+str(root/f"{i:02d}.png")+"'", "duration "+str(hold)]
            playlist+=["file '"+str(root/f"{len(images)-1:02d}.png")+"'"]
            (root/"slides.txt").write_text("\n".join(playlist)+"\n")
            outfile=root/"recap.mp4"
            cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y",
                 "-safe","0","-f","concat","-i",str(root/"slides.txt"),
                 "-i",str(root/"voice.mp3"),"-map","0:v:0","-map","1:a:0",
                 "-vf","fps=24,scale=960:540,format=yuv420p",
                 "-c:v","libx264","-preset","ultrafast","-crf","30",
                 "-c:a","aac","-b:a","112k","-shortest","-movflags","+faststart",str(outfile)]
            subprocess.run(cmd,check=True,capture_output=True,timeout=60)
            data=outfile.read_bytes()
            return data if 50000<len(data)<19_000_000 else None
    try:return await asyncio.wait_for(asyncio.to_thread(blocking),timeout=75)
    except Exception:return None
