"""Read official PlayCHL schedule. Public HTML can change; test /powerrefresh.
Optional GAMES_JSON_URL supports a durable league-owned JSON data feed.
"""
import json
import logging
import os
import re
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

log=logging.getLogger('playchl.schedule')
MONTH={m:i+1 for i,m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}
TEAM='ANA|BUF|CGY|DET|MIN|SEA|SJS|UTAH|VGK|WSH'
ROW=re.compile(r'(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(?P<day>\d{1,2})\s+(?P<clock>\d{1,2}:\d{2})\s*(?P<ampm>AM|PM)\s*UTC\s+(?P<away>'+TEAM+r')\s+Away\s+(?P<a>\d+)\s*[-–:]\s*(?P<h>\d+)\s+(?P<home>'+TEAM+r')\s+Home\s+(?P<status>Forfeit|Final(?:\s*/\s*OT)?)',re.I)


def parse_schedule(text,now=None):
    now=now or datetime.now(timezone.utc)
    text=re.sub(r'\s+',' ',text)
    out=[]
    for m in ROW.finditer(text):
        v=m.groupdict(); hh,mm=map(int,v['clock'].split(':'))
        hh=(hh%12)+(12 if v['ampm'].upper()=='PM' else 0)
        candidates=[]
        for y in (now.year-1,now.year,now.year+1):
            try:dt=datetime(y,MONTH[v['mon'].title()],int(v['day']),hh,mm,tzinfo=timezone.utc)
            except ValueError:continue
            candidates.append(dt)
        dt=min(candidates,key=lambda d:abs((d-now).days))
        status=v['status'].title(); away=v['away'].upper();home=v['home'].upper()
        out.append(dict(date=dt.isoformat(),away=away,home=home,away_score=int(v['a']),home_score=int(v['h']),status=status,overtime='OT' in status.upper()))
    return out


async def fetch_games():
    url=os.environ.get('GAMES_JSON_URL','').strip()
    if url:
        if not url.startswith('https://'):raise RuntimeError('GAMES_JSON_URL must use HTTPS')
        def read():
            with urlopen(Request(url,headers={'User-Agent':'PlayCHL-PowerRankings/1.0'}),timeout=30) as r:
                payload=json.load(r)
            return payload['games'] if isinstance(payload,dict) else payload
        import asyncio
        data=await asyncio.to_thread(read)
        if not isinstance(data,list):raise ValueError('JSON feed must be an array of games')
        return data
    target=os.getenv('PLAYCHL_SCHEDULE_URL','https://playchl.com/schedule')
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
        try:
            page=await browser.new_page()
            await page.goto(target,wait_until='domcontentloaded',timeout=60000)
            try:await page.get_by_text('Final',exact=False).first.wait_for(timeout=15000)
            except Exception:pass
            await page.wait_for_timeout(3000)
            raw=await page.locator('body').inner_text(timeout=20000)
            games=parse_schedule(raw)
            if not games:
                log.warning('PlayCHL page debug URL=%s title=%s body excerpt=%r',page.url,await page.title(),raw[:2400])
                text_content=await page.locator('body').text_content(timeout=20000)
                log.warning('PlayCHL body textContent excerpt=%r', (text_content or '')[:1500])
                games=parse_schedule(text_content or '')
            if not games:
                raise RuntimeError('No final scores parsed from PlayCHL schedule. Inspect site markup or use GAMES_JSON_URL / /powerimport.')
            return games
        finally:await browser.close()
