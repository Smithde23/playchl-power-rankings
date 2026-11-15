"""CHEL HEAD club match fallback; reads rendered match popups, never guesses identities.

Source club: CHL27 WASHINGTON CAPITALS, common-gen5/1940.
Requires unique score/opponent and close date. Ambiguity = no player data.
"""
import logging,os,re
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright
log=logging.getLogger("chl.chelhead")
URL=os.getenv("CHELHEAD_CLUB_URL","https://chelhead.com/view-club/common-gen5/1940")
ET=ZoneInfo("America/New_York")
NAMES={
"ANA":["ANAHEIM DUCKS","ANAHEIM"],
"BUF":["BUFFALO SABRES","BUFFALO"],
"CGY":["CALGARY FLAMES","CALGARY"],
"DET":["DETROIT RED WINGS","DETROIT"],
"MIN":["MINNESOTA WILD","MINNESOTA"],
"SEA":["SEATTLE KRAKEN","SEATTLE"],
"SJS":["SAN JOSE SHARKS","SAN JOSE"],
"UTAH":["UTAH MAMMOTH","UTAH HOCKEY CLUB","UTAH"],
"VGK":["GOLDEN KNIGHTS","VEGAS"],
"WSH":["WASHINGTON CAPITALS","WASHINGTON"],
}
POS=r"(?:C|RW|LW|LD|RD)"
NUM=r"-?\d+(?:\.\d+)?"
SKATER=re.compile(
r"(?:^|\s)(C|RW|LW|LD|RD)\s+([A-Za-z][A-Za-z0-9_.-]{1,38})\s+"
+r"\s+".join([r"("+NUM+r")"]*10)+r"(?=\s|$)",re.I)
GOALIE=re.compile(
r"(?:^|\s)G\s+([A-Za-z][A-Za-z0-9_.-]{1,38})\s+"
+r"\s+".join([r"("+NUM+r")"]*5)+r"(?=\s|$)",re.I)
HEADINGS=["PLAYER","GOALIES","TOTAL","CHL27 WASHINGTON CAPITALS"]
def clean(s):return re.sub(r"\s+"," ",s or "").strip()
def minutes_ago(s):
    t=s.lower()
    m=re.search(r"(\d+)\s*(minute|hour|day|week)s?\s+ago",t)
    if not m:return None
    v=int(m[1]);u=m[2]
    return v*({"minute":1,"hour":60,"day":1440,"week":10080})[u]
def rival_code(text,g):
    target=g["home"] if g["away"]=="WSH" else g["away"]
    return any(x in text.upper() for x in NAMES[target])
def card_candidates(cards,g):
    results=[]
    target_score=g["a"] if g["away"]=="WSH" else g["h"]
    other_score=g["h"] if g["away"]=="WSH" else g["a"]
    played=datetime.fromisoformat(g["date"]).astimezone(ET)
    # EA match history time is a relative age; preserve a generous but limited
    # two-day window because game schedule time is UTC and reported ages are rounded.
    for card in cards:
        text=clean(card.get("text",""))
        if "WASHINGTON CAPITALS" not in text.upper() or not rival_code(text,g):continue
        values=re.findall(r"(?<!\d)\d{1,2}(?!\d)",text)
        if str(target_score) not in values or str(other_score) not in values:continue
        age=minutes_ago(text)
        if age is None:continue
        when=datetime.now(ET)-timedelta(minutes=age)
        if abs((when-played).total_seconds())>2*86400:continue
        results.append(card)
    return results

async def clickable_cards(page):
    return await page.evaluate("""() => {
      const focus=[...document.querySelectorAll('*')].filter(e=>
        e.children.length===0 && (e.textContent||'').trim().toUpperCase()==='CHL27 WASHINGTON CAPITALS');
      const out=[],seen=new Set();
      for (const el of focus) {
        let a=el;
        for(let depth=0;depth<8 && a;depth++,a=a.parentElement){
          const text=(a.innerText||'').replace(/\\s+/g,' ').trim();
          const rect=a.getBoundingClientRect();
          if(text.length>30 && text.length<550 && /(?:ago|today|yesterday)/i.test(text) &&
              rect.width>180 && rect.height>70){
            if(!seen.has(a)){
              const id='chl-card-'+out.length;
              a.setAttribute('data-chl-matchcard',id);
              seen.add(a);out.push({id,text});
            }
            break;
          }
        }
      }
      return out;
    }""")

def extract_box(text,g):
    """Parse skater and goalie table rows from visible popup text, with team partitions."""
    raw=clean(text)
    if not ("WASHINGTON CAPITALS" in raw.upper() and rival_code(raw,g)):return None
    a=g["a"];h=g["h"]
    # Score confirmation requires the title order with WSH as home or away.
    opponent=g["home"] if g["away"]=="WSH" else g["away"]
    w=a if g["away"]=="WSH" else h
    o=h if g["away"]=="WSH" else a
    up=raw.upper()
    title_match=False
    for name in NAMES[opponent]:
        # header may interpose division label; allow up to 65 chars between.
        if re.search(r"WASHINGTON CAPITALS.{0,100}\b"+str(w)+r"\s*[-–]\s*"+str(o)+r"\b.{0,100}"+re.escape(name),up):
            title_match=True
        if re.search(re.escape(name)+r".{0,100}\b"+str(o)+r"\s*[-–]\s*"+str(w)+r"\b.{0,100}WASHINGTON CAPITALS",up):
            title_match=True
    # Screenshots show score in modal heading, so enforce it rather than attach
    # stats from coincidental same-score recent matches.
    if not title_match:return None
    players_at=up.find("PLAYERS")
    if players_at<0:return None
    data=raw[players_at:]
    # Team sections are headed by full club names. Keep each team's rows isolated.
    marks=[]
    for abbreviation in ("WSH",opponent):
        for name in NAMES[abbreviation]:
            for m in re.finditer(re.escape(name),data.upper()):
                marks.append((m.start(),abbreviation,m.end()))
    marks.sort()
    parts=[]
    for i,(start,team,after) in enumerate(marks):
        finish=marks[i+1][0] if i+1<len(marks) else len(data)
        seg=data[after:finish]
        if "PLAYER" in seg.upper() or "GOALIES" in seg.upper():
            parts.append((team,seg))
    players=[]
    for team,section in parts:
        for m in SKATER.finditer(section):
            pos,name,*vals=m.groups()
            # G,A,P,+/-,SH,HIT,BLK,TK,GV,star rating
            nums={k:v for k,v in zip(("G","A","P","+/-","SH","HIT","BLK","TK","GV","SCORE"),vals)}
            if int(float(nums["G"]))+int(float(nums["A"]))!=int(float(nums["P"])):
                continue
            if float(nums["G"])>g["a"]+g["h"]:continue
            players.append({"name":name,"team":team,"pos":pos.upper(),"stats":nums})
        for m in GOALIE.finditer(section):
            name,*vals=m.groups()
            sv,gaa,saves,against,score=vals
            if float(saves)>float(against):continue
            players.append({"name":name,"team":team,"pos":"G","stats":{"SV%":sv,"GAA":gaa,"SV":saves,"SA":against,"SCORE":score}})
    if not any(p["team"]=="WSH" for p in players):return None
    # A real boxscore must be internally consistent for skaters when all skaters
    # are visible; partial extraction cannot prove goals, but never invents stats.
    unique={(p["team"],p["name"],p["pos"]):p for p in players}
    return {"url":URL,"source":"chelhead","players":list(unique.values()),"match":{}}

async def fetch_fallback(game):
    """Open ChelHead match card and verify the match. Returns None if uncertain."""
    if "WSH" not in (game["away"],game["home"]) or game["status"]!="Final":return None
    if URL!="https://chelhead.com/view-club/common-gen5/1940":
        log.warning("Unexpected CHEL HEAD URL; refusing non-verified profile")
        return None
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=await browser.new_page(viewport={"width":1440,"height":900})
            await page.goto(URL,wait_until="domcontentloaded",timeout=60000)
            try:await page.get_by_text("RECENT MATCHES",exact=False).first.wait_for(timeout=20000)
            except Exception:pass
            await page.wait_for_timeout(3000)
            cards=await clickable_cards(page)
            matched=card_candidates(cards,game)
            if len(matched)!=1:
                log.info("CHELHEAD match resolution %s: %d cards, %d plausible for %s %s-%s %s",
                         game["id"],len(cards),len(matched),game["away"],game["a"],game["h"],game["home"])
                return None
            candidate=matched[0]
            await page.locator('[data-chl-matchcard="'+candidate["id"]+'"]').click(timeout=8000)
            await page.get_by_text("SUMMARY",exact=True).first.wait_for(timeout=8000)
            await page.get_by_text("PLAYERS",exact=True).last.click(timeout=8000)
            await page.wait_for_timeout(600)
            # Popup text extracted in DOM reading order; not a navigation URL.
            modal=await page.evaluate("""() => {
              const all=[...document.querySelectorAll('[role=dialog], [aria-modal=true]')];
              const dialogs=all.filter(x=>(x.innerText||'').includes('GOALIES'));
              if(dialogs.length)return dialogs.sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length)[0].innerText;
              const body=document.body.innerText;
              const idx=body.lastIndexOf('CLOSE\\n');
              return idx>=0?body.slice(idx):body.slice(-35000);
            }""")
            box=extract_box(modal,game)
            if box:log.info("CHELHEAD verified %d player entries for %s",len(box["players"]),game["id"])
            else:log.info("CHELHEAD popup opened but boxscore validation failed: %s",game["id"])
            return box
        except Exception as exc:
            log.warning("CHELHEAD fallback unavailable: %s",exc)
            return None
        finally:await browser.close()
