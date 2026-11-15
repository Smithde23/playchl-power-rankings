"""Read VERIFIED individual box scores and team stats from PlayCHL game-detail pages.
A game without a uniquely matched page has NO invented players or stats.
"""
import logging
import re
from urllib.parse import urlparse
log=logging.getLogger("chl.recaps.stats")
VALID=re.compile(r"^https://playchl\.com/games/[a-zA-Z0-9_-]+/?$")
FIELD_NAMES={"G","A","P","SH","HIT","TK","GV","BLK","INT","PIM","SV","SA","GA","SV%"}
MATCH_LABELS={"Goals","Shots","Hits","TOA","Faceoffs%","PIM","Blocks","Takeaways","Giveaways","Interceptions"}

def valid_url(url):
    return bool(VALID.fullmatch(url or ""))

def rows_from_table(table):
    return table.get("rows",[])

def parse_box(payload,away,home,away_score,home_score):
    """Payload comes ONLY from live game page. Validate the game's scoreboard first."""
    body=" ".join(payload.get("body","").split())
    # Both team names and the exact score must be seen on the game page.
    names=payload.get("team_names",{})
    for abbreviation in (away,home):
        if not names.get(abbreviation):return None
    # Page header scores are extracted from the match-stat "Goals" row, not random numbers.
    match={}
    players=[]
    for table in payload.get("tables",[]):
        heading=" ".join((table.get("heading","") or "").split())
        header=[x.strip() for x in table.get("header",[])]
        grid=rows_from_table(table)
        if "Match Stats" in heading:
            for row in grid:
                if len(row)>=3 and row[1].strip() in MATCH_LABELS:
                    match[row[1].strip()]=[row[0].strip(),row[2].strip()]
        if not ("Skaters" in heading or "Goalies" in heading):continue
        team=next((k for k,v in names.items() if v.lower() in heading.lower()),None)
        if team not in (away,home):continue
        # Explicit header order is required: avoids mislabeling fields.
        for raw in grid:
            if len(raw)<len(header) or len(header)<4:continue
            cells=raw[-len(header):]
            if cells[0].lower() in ("player",""):continue
            # Some pages include an extra numeric player score cell before the username.
            name=re.sub(r"^\s*\d+(?:\.\d+)?\s*","",cells[0]).strip()
            name=re.sub(r"(?:Xbox|PlayStation)\s*$","",name,flags=re.I).strip()
            if not name or len(name)>80:continue
            fields={k:v for k,v in zip(header[1:],cells[1:]) if k.strip() in FIELD_NAMES}
            pos=fields.get("Pos") or (cells[1] if len(cells)>1 else "")
            if pos not in ("C","LW","RW","D","G"):continue
            numbers={}
            for field in FIELD_NAMES:
                val=fields.get(field)
                if val is not None and re.fullmatch(r"-?\d+(?:\.\d+)?%?",val.strip()):
                    numbers[field]=val.strip()
            players.append(dict(name=name,team=team,pos=pos,stats=numbers))
    goals=match.get("Goals")
    # Page uses home-first or away-first visual ordering; require unordered agreement
    # before including any game stats.
    if not goals or sorted(goals)!=sorted([str(away_score),str(home_score)]):return None
    if not players:return None
    return {"url":payload.get("url"),"players":players,"match":match}

async def discover_schedule_links(page,games):
    """Link a schedule row and a URL only if the DOM provides an unambiguous match."""
    links=await page.evaluate("""() => [...document.querySelectorAll('a[href*="/games/"]')].map(a => ({
        url: a.href,
        text: (a.innerText || a.textContent || '').replace(/\\s+/g,' ').trim(),
        parent: (a.parentElement?.innerText || '').replace(/\\s+/g,' ').trim(),
        grand: (a.parentElement?.parentElement?.innerText || '').replace(/\\s+/g,' ').trim()
    })).slice(0,1500)""")
    found={}
    for g in games:
        if "WSH" not in (g["away"],g["home"]):continue
        candidates=set()
        # The same row must identify BOTH clubs and exact final score; if not, skip.
        score=re.compile(r"\b"+str(g["a"])+r"\s*[-–:]\s*"+str(g["h"])+r"\b")
        for entry in links:
            url=entry.get("url","")
            if not valid_url(url):continue
            for field in ("text","parent"):
                s=entry.get(field,"")
                if g["away"] in s and g["home"] in s and score.search(s):
                    candidates.add(url);break
        if len(candidates)==1:found[g["id"]]=candidates.pop()
    return found

async def fetch_box(browser,url,away,home,a,h):
    if not valid_url(url):return None
    p=await browser.new_page()
    try:
        await p.goto(url,wait_until="domcontentloaded",timeout=45000)
        await p.wait_for_timeout(1400)
        payload=await p.evaluate("""() => {
          const headings=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')];
          const tables=[...document.querySelectorAll('table')].map(t=>{
            let h=t.previousElementSibling;
            let heading='';
            for(let i=0;i<7 && h;i++,h=h.previousElementSibling){
              if(h.matches('h1,h2,h3,h4,h5,h6')){heading=h.innerText;break;}
              const prior=h.querySelector('h1,h2,h3,h4,h5,h6');
              if(prior){heading=prior.innerText;break;}
            }
            if(!heading){
              let ancestor=t.parentElement;
              for(let i=0;i<5&&ancestor;i++,ancestor=ancestor.parentElement){
                const all=[...ancestor.querySelectorAll('h1,h2,h3,h4,h5,h6')];
                if(all.length===1){heading=all[0].innerText;break;}
              }
            }
            const trs=[...t.querySelectorAll('tr')];
            let header=[...t.querySelectorAll('thead th')].map(x=>x.innerText.trim());
            if(!header.length && trs.length)header=[...trs[0].querySelectorAll('th')].map(x=>x.innerText.trim());
            const rows=trs.slice(1).map(r=>[...r.querySelectorAll('th,td')].map(x=>x.innerText.trim()));
            return {heading,header,rows};
          });
          return {url:location.href,body:document.body.innerText.slice(0,150000),tables};
        }""")
        names={"ANA":"Anaheim Ducks","BUF":"Buffalo Sabres","CGY":"Calgary Flames","DET":"Detroit Red Wings","MIN":"Minnesota Wild","SEA":"Seattle Kraken","SJS":"San Jose Sharks","UTAH":"Utah Hockey Club","VGK":"Vegas Golden Knights","WSH":"Washington Capitals"}
        payload["team_names"]={away:names[away],home:names[home]}
        return parse_box(payload,away,home,a,h)
    except Exception as exc:
        log.warning("Box score unavailable for %s: %s",url,exc)
        return None
    finally:await p.close()

def noteworthy(box,team):
    if not box:return []
    people=[x for x in box["players"] if x["team"]==team]
    def n(x,k):
        try:return int(x["stats"].get(k,"0"))
        except Exception:return 0
    people.sort(key=lambda x:(n(x,"P"),n(x,"G"),n(x,"SH")),reverse=True)
    return people[:4]
