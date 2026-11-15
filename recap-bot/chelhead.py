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
    """Parse CHEL HEAD's real visible Players tab, including accessible labels.

    Team sections are marked by club name, score, and win/loss. Each player
    must appear inside its team's section, with a validated G + A = P total.
    This code never treats the players from a different club as Washington.
    """
    raw=clean(text)
    opponent=g["home"] if g["away"]=="WSH" else g["away"]
    away,home=g["away"],g["home"]
    if "WASHINGTON CAPITALS" not in raw.upper() or not rival_code(raw,g):return None
    # The selected match card has already been checked for ordered home-away
    # matchup and date. Verify the report repeats both exact team scores.
    markers=[]
    for club,expected in ((away,g["a"]),(home,g["h"])):
        options=NAMES[club]
        matches=[]
        for alias in options:
            exp=r"(?:CHL27\s+)?"+re.escape(alias)+r"\s+(?:"+r"DIV\s+\d+\s+)?" +str(expected)+r"\s+[WL]\b"
            matches.extend(re.finditer(exp,raw,re.I))
        if not matches:return None
        first=min(matches,key=lambda x:x.start())
        markers.append((first.start(),first.end(),club))
    markers.sort()
    if markers[0][0]==markers[1][0]:return None
    sections={}
    for i,(start,end,club) in enumerate(markers):
        until=markers[i+1][0] if i+1<len(markers) else len(raw)
        sections[club]=raw[end:until]
    numeric=r"([+-]?\d+(?:\.\d+)?)"
    skater=re.compile(
        r"(?:^|\s)(C|RW|LW|LD|RD)\s+"
        r"(?:(?:1st|2nd|3rd)\s+Star,\s*)?"
        r"(.{2,72}?)\s*,\s*"
        r"(?:Center|Right Wing|Left Wing|Left Defense|Right Defense)\s+"
        +r"\s+".join([numeric]*10)+r"(?=\s|$)",re.I)
    goalie=re.compile(
        r"(?:^|\s)G\s+(.{2,72}?)\s+(0\.\d+|1\.000)\s+"
        +r"\s+".join([numeric]*4)+r"(?=\s|$)",re.I)
    players=[]
    for team,section in sections.items():
        for match in skater.finditer(section):
            pos,name,*values=match.groups()
            if "PLAYER" in name.upper() or "GOALIES" in name.upper():continue
            stats=dict(zip(("G","A","P","+/-","SH","HIT","BLK","TK","GV","SCORE"),values))
            if int(float(stats["G"]))+int(float(stats["A"]))!=int(float(stats["P"])):continue
            team_goals=g["a"] if team==away else g["h"]
            if int(float(stats["G"]))>team_goals:continue
            players.append({"name":name.strip(),"team":team,"pos":pos.upper(),"stats":stats})
        for match in goalie.finditer(section):
            name,rate,gaa,saves,against,score=match.groups()
            if "GOALIES" in name.upper() or float(saves)>float(against):continue
            players.append({"name":name.strip(),"team":team,"pos":"G",
                            "stats":{"SV%":rate,"GAA":gaa,"SV":saves,"SA":against,"SCORE":score}})
    skaters=[p for p in players if p["pos"]!="G"]
    if not any(p["team"]=="WSH" for p in skaters):return None
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
            target=page.locator('[data-chl-matchcard="'+candidate["id"]+'"]')
            await target.click(timeout=8000)
            # CHEL HEAD's report is a custom Ionic popup, not an ion-segment
            # with a summary value. Verify the report by its heading text.
            await page.wait_for_timeout(650)
            snapshot=clean(await page.locator("body").inner_text(timeout=12000))
            if not ("DESERVE TO WIN" in snapshot.upper() and "SUMMARY" in snapshot.upper()):
                log.warning("CHELHEAD report did not open for %s",game["id"])
                return None
            pressed=await page.evaluate("""() => {
              const els=[...document.querySelectorAll('ion-segment-button, ion-tab-button, ion-button, button, [role=tab], [role=button], div, span')];
              const labels=els.filter(el=>el.children.length<=2 && (el.innerText||'').trim().toUpperCase()==='PLAYERS')
                  .filter(el=>el.getBoundingClientRect().width>0 && el.getBoundingClientRect().height>0);
              for(const el of labels.reverse()){
                const clickable=el.closest('ion-segment-button,ion-tab-button,ion-button,button,[role=tab],[role=button]')||el;
                clickable.click();
                return clickable.outerHTML.slice(0,300);
              }
              return '';
            }""")
            if not pressed:
                log.warning("CHELHEAD report opened, but Players tab was not found")
                return None
            log.info("CHELHEAD clicked Players tab via %s",pressed[:180])
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
            else:log.warning("CHELHEAD player report parser failed for %s; popup excerpt=%r",game["id"],clean(modal)[:3200])
            return box
        except Exception as exc:
            log.warning("CHELHEAD fallback unavailable: %s",exc)
            return None
        finally:await browser.close()
