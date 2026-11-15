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
        # ChelHead exposes a spoken-accessible line with precise away/home order:
        # "WASHINGTON CAPITALS 6 at UTAH MAMMOTH 7".
        # This is critical when the reverse fixture (Utah 6 at Washington 7)
        # exists on the same date. Never match on unordered 6/7 scores.
        away_alias="|".join(re.escape(x) for x in NAMES[g["away"]])
        home_alias="|".join(re.escape(x) for x in NAMES[g["home"]])
        ordered=(r"(?:CHL27\s+)?(?:"+away_alias+r")\s+"+str(g["a"])
                 +r"\s+at\s+(?:CHL27\s+)?(?:"+home_alias+r")\s+"+str(g["h"])+r"\b")
        # JS card text is already collapsed; normalize to uppercase.
        if not re.search(ordered,text.upper(),re.I):continue
        age=minutes_ago(text)
        if age is None:continue
        when=datetime.now(ET)-timedelta(minutes=age)
        if abs((when-played).total_seconds())>2*86400:continue
        results.append(card)
    return results

async def clickable_cards(page):
    """Find rendered match cards without relying on brittle leaf DOM shapes."""
    return await page.evaluate("""() => {
      const possible=[...document.querySelectorAll('ion-card, ion-card-content, ion-item, ion-button, article, button, div, [role=button], a')];
      const picked=[];
      for(const el of possible){
        const rect=el.getBoundingClientRect();
        if(rect.width<100 || rect.height<40 || rect.height>700)continue;
        const raw=(el.innerText||'').replace(/\\s+/g,' ').trim();
        const t=raw.toUpperCase();
        if(raw.length<30 || raw.length>1050 || !t.includes('WASHINGTON CAPITALS'))continue;
        if(!/(?:\\d+\\s*(?:hour|day|week|minute)s?\\s+ago|yesterday|today)/i.test(raw))continue;
        if(!t.includes('CHL27'))continue;
        picked.push({element:el,text:raw,size:raw.length});
      }
      // Keep the smallest qualifying container for each card; remove broad wrappers.
      const minimal=picked.filter(c=>!picked.some(d=>d!==c && c.element.contains(d.element) && d.size<c.size));
      const out=[];const seen=new Set();
      for(const cand of minimal.sort((a,b)=>a.size-b.size)){
        const key=cand.text;
        if(seen.has(key))continue;
        seen.add(key);
        const id='chl-card-'+out.length;
        cand.element.setAttribute('data-chl-matchcard',id);
        out.push({id,text:cand.text});
      }
      return out.slice(0,200);
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
    # Overlapping aliases (e.g. "UTAH" and "UTAH MAMMOTH") are collapsed.
    marks.sort(key=lambda x:(x[0],-(x[2]-x[0])))
    dedup=[]
    for mark in marks:
        if dedup and mark[0]<dedup[-1][2]:continue
        dedup.append(mark)
    marks=dedup
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
            await page.locator('ion-segment-button[value="matches"]').click(timeout=12000)
            try:await page.get_by_text("RECENT MATCHES",exact=False).first.wait_for(timeout=20000)
            except Exception:pass
            await page.wait_for_timeout(3000)
            cards=await clickable_cards(page)
            if not cards:
                excerpt=clean((await page.locator("body").inner_text(timeout=10000))[:1600])
                log.warning("CHELHEAD rendered no selectable match cards; page excerpt=%r",excerpt[:900])
            else:log.info("CHELHEAD rendered %d selectable club match cards",len(cards))
            matched=card_candidates(cards,game)
            if len(matched)>1:
                log.warning("CHELHEAD ambiguous game %s candidate cards: %s",game["id"],[(x["id"],x["text"][:300]) for x in matched[:5]])
            if len(matched)!=1:
                log.info("CHELHEAD match resolution %s: %d cards, %d plausible for %s %s-%s %s",
                         game["id"],len(cards),len(matched),game["away"],game["a"],game["h"],game["home"])
                return None
            candidate=matched[0]
            await page.locator('[data-chl-matchcard="'+candidate["id"]+'"]').click(timeout=8000)
            await page.get_by_text("SUMMARY",exact=True).first.wait_for(timeout=8000)
            await page.locator('ion-segment-button[value="players"]').last.click(timeout=8000)
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
