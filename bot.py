"""PlayCHL standalone weekly power rankings bot; python 3.12 / discord.py 2.4+."""
import asyncio
import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from engine import database, save_games, week_end, rank, previous, snapshot, get_snapshot, TEAMS, ET
from sources import fetch_games
from writing import make_writeups

load_dotenv();logging.basicConfig(level=logging.INFO)
log=logging.getLogger('playchl.power')
TOKEN=os.getenv('DISCORD_TOKEN','')
GUILD_ID=int(os.getenv('GUILD_ID','0'))
CHANNEL_ID=int(os.getenv('RANKINGS_CHANNEL_ID','0'))
ADMIN_ROLE_ID=int(os.getenv('ADMIN_ROLE_ID','0'))
DB_PATH=os.getenv('DATABASE_PATH','/data/power_rankings.sqlite3')
PUBLISH_DAY=os.getenv('PUBLISH_DAY','Saturday').lower()
PUBLISH_HOUR=int(os.getenv('PUBLISH_HOUR','12'))
PUBLISH_MINUTE=int(os.getenv('PUBLISH_MINUTE','0'))
POLL_MINUTES=max(5,int(os.getenv('POLL_MINUTES','30')))
FORFEIT_RECORD=os.getenv('INCLUDE_FORFEITS_IN_RECORD','true').lower()=='true'
bot=commands.Bot(command_prefix='!',intents=discord.Intents.default())
lock=asyncio.Lock()

def db():return database(DB_PATH)

def is_admin(i:discord.Interaction):
    if i.user.guild_permissions.manage_guild:return True
    if ADMIN_ROLE_ID and any(r.id==ADMIN_ROLE_ID for r in getattr(i.user,'roles',[])):return True
    return False

async def require_admin(i):
    if i.guild is None or not is_admin(i):
        await i.response.send_message('Manage Server permission or configured admin role required.',ephemeral=True)
        return False
    return True

async def ingest():
    raw=await fetch_games()
    if not raw:raise RuntimeError('The game feed is empty; existing history remains untouched.')
    with db() as conn: result=save_games(conn,raw)
    log.info('Imported games: new=%s updated=%s invalid=%s',*result)
    return result

def build_embeds(rows,messages,end):
    pages=[]
    for r in rows:
        w,s=r['week'],r['season'];change=r['movement']
        movement='NEW' if change is None else '▲ '+str(change) if change>0 else '▼ '+str(abs(change)) if change<0 else '—'
        e=discord.Embed(title=f"#{r['rank']} {r['name']}  |  {movement}",
            description=messages.get(r['team'],'No report available.'),color=discord.Color.from_rgb(18,95,168))
        e.add_field(name='This week',value=f"{w['w']}-{w['l']}-{w['otl']} | GF {w['gf']} · GA {w['ga']}")
        e.add_field(name='Season',value=f"{s['w']}-{s['l']}-{s['otl']} | GP {s['gp']}")
        e.add_field(name='Power score',value=f"{r['score']:.1f}/100",inline=True)
        e.set_footer(text=f"Week ending {end} (ET) · Forfeits excluded from GF/GA · CHL unofficial rankings")
        pages.append(e)
    return pages

async def rankings_report(rows,messages,end,interaction=None,channel=None):
    intro=discord.Embed(title=f'🏒 CHL Weekly Power Rankings — {end}',
        description=('Ranked by weekly results (40%), season results (20%), weekly goal differential (15%), '
                     'opponent strength (15%), and recent momentum (10%).\n'
                     'Games close Saturday ET; forfeits count for record but not goals.'),
        color=discord.Color.from_rgb(18,95,168))
    intro.add_field(name='Top 10',value='\n'.join(f"**{r['rank']}. {r['team']}** — {r['score']:.1f} ({'NEW' if r['movement'] is None else ('▲'+str(r['movement']) if r['movement']>0 else '▼'+str(abs(r['movement'])) if r['movement']<0 else '—')})" for r in rows),inline=False)
    embeds=[intro,*build_embeds(rows,messages,end)]
    chunks=[embeds[i:i+8] for i in range(0,len(embeds),8)]
    sent=[]
    for idx,group in enumerate(chunks):
        if interaction and idx==0:
            await interaction.followup.send(embeds=group,ephemeral=True)
        elif interaction:
            await interaction.followup.send(embeds=group,ephemeral=True)
        else:
            sent.append(await channel.send(embeds=group))
    return [str(x.id) for x in sent]

async def current_rankings(end):
    with db() as conn:
        old=previous(conn,end)
        return rank(conn,end,old,FORFEIT_RECORD)

async def publish(end,force=False):
    async with lock:
        with db() as conn:
            if get_snapshot(conn,end):return 'Already published; historical posts cannot be overwritten.'
        await ingest()
        with db() as conn:
            n=conn.execute('SELECT COUNT(*) FROM games').fetchone()[0]
            if not n:raise RuntimeError('No completed games in local database')
            rows=rank(conn,end,previous(conn,end),FORFEIT_RECORD)
        if all(r['season']['gp']==0 for r in rows):raise RuntimeError('No completed season games by this Saturday')
        messages=await make_writeups(rows)
        channel=bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        with db() as conn:snapshot(conn,end,rows,messages,CHANNEL_ID,[])
        try:
            ids=await rankings_report(rows,messages,end,channel=channel)
            with db() as conn:
                conn.execute('UPDATE snapshots SET message_ids_json=? WHERE week_end=?',(json.dumps(ids),end));conn.commit()
        except Exception:
            log.exception('Publishing incomplete. Check channel before manually reposting.')
            raise
        return f'Published {len(rows)} rankings for week ending {end} in <#{CHANNEL_ID}>.'

@bot.event
async def on_ready():
    if getattr(bot,'_initialized',False):return
    bot._initialized=True
    if GUILD_ID:
        guild=discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced=await bot.tree.sync(guild=guild)
    else:synced=await bot.tree.sync()
    log.info('Connected as %s; synced %s commands',bot.user,len(synced))
    if not ticker.is_running():ticker.start()

@tasks.loop(minutes=POLL_MINUTES)
async def ticker():
    now=datetime.now(ET)
    try:
        await ingest()
    except Exception as exc:log.warning('Feed poll failed: %s',exc)
    if now.strftime('%A').lower()==PUBLISH_DAY and (now.hour,now.minute)>=(PUBLISH_HOUR,PUBLISH_MINUTE):
        try:
            with db() as conn:already=get_snapshot(conn,week_end(now))
            if not already:log.info(await publish(week_end(now)))
        except Exception:log.exception('Automatic publishing failed; will retry on next poll')

@ticker.before_loop
async def before_ticker():await bot.wait_until_ready()


# Unofficial PlayCHL Vezina leaderboard, sourced from the published goalie table.
# Statistics are never inferred from team final scores.
def _vezina_number(row, *keys):
    for key in keys:
        raw=str(row.get(key,'')).strip().replace(',','').replace('%','')
        if not raw or raw in ('-','—','N/A'):continue
        try:return float(raw)
        except ValueError:continue
    return None

async def _vezina_goalies():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
        try:
            page=await browser.new_page()
            response=await page.goto('https://playchl.com/statistics',wait_until='domcontentloaded',timeout=45000)
            if not response or response.status>=400:
                raise RuntimeError('PlayCHL statistics page unavailable')
            tab=page.get_by_role('button',name='Goalies',exact=True)
            if await tab.count()==0:tab=page.get_by_text('Goalies',exact=True)
            await tab.first.click(timeout=12000)
            await page.locator('table tbody tr').first.wait_for(timeout=15000)
            tables=await page.locator('table').evaluate_all("""els => els.map(t => ({
                headers:[...t.querySelectorAll('thead th')].map(e=>e.innerText.trim().toUpperCase()),
                rows:[...t.querySelectorAll('tbody tr')].map(tr=>[...tr.querySelectorAll('th,td')].map(e=>e.innerText.trim()))
            }))""")
        finally:
            await browser.close()
    records=[]
    for table in tables:
        headers=table['headers']
        if not any(k in headers for k in ('PLAYER','NAME','GAMERTAG')):continue
        for cells in table['rows']:
            if len(cells)<len(headers):continue
            row=dict(zip(headers,cells))
            name=next((row[k].strip() for k in ('PLAYER','NAME','GAMERTAG') if row.get(k,'').strip()),'')
            gp=_vezina_number(row,'GP')
            sv=_vezina_number(row,'SV%','SAVE%','SAVE %','SAVE PCT')
            gaa=_vezina_number(row,'GAA')
            if name and gp is not None and sv is not None and gaa is not None:
                records.append(row)
    if not records:raise RuntimeError('No goalie rows with GP, SV% and GAA were found on PlayCHL')
    return records

def _vezina_rank(records,minimum_games=10):
    # Choose a single published season row per player; never add duplicate totals.
    unique={}
    for row in records:
        name=next((row.get(k,'').strip() for k in ('PLAYER','NAME','GAMERTAG') if row.get(k,'').strip()),'')
        team=row.get('TEAM','').strip()
        key=(name.casefold(),team.casefold())
        if key not in unique or (_vezina_number(row,'GP') or 0)>(_vezina_number(unique[key],'GP') or 0):
            unique[key]=row
    eligible=[r for r in unique.values() if (_vezina_number(r,'GP') or 0)>=minimum_games]
    if not eligible:return []
    # Score each category relative to the eligible field. Only award points
    # for statistics actually published; renormalize the available weights.
    categories=[('SV%',('SV%','SAVE%','SAVE %','SAVE PCT'),.35,True),
                ('GAA',('GAA',),.25,False),
                ('W',('W','WINS'),.15,True),
                ('SO',('SO','SHUTOUTS'),.10,True),
                ('SA',('SA','SHOTS AGAINST','SHOTS FACED'),.10,True),
                ('GP',('GP',),.05,True)]
    scored=[]
    for row in eligible:
        total=weight_sum=0.0
        for label,keys,weight,higher_better in categories:
            values=[_vezina_number(r,*keys) for r in eligible]
            if any(v is None for v in values):continue
            low,high=min(values),max(values)
            v=_vezina_number(row,*keys)
            scaled=(v-low)/(high-low) if high>low else 1.0
            if not higher_better:scaled=1-scaled if high>low else 1.0
            total+=weight*scaled
            weight_sum+=weight
        scored.append((round(100*total/weight_sum,1) if weight_sum else 0,row))
    return sorted(scored,key=lambda item:(-item[0],-(_vezina_number(item[1],'SV%') or 0),_vezina_number(item[1],'GAA') or 999))

@bot.tree.command(name='vezina',description='Post PlayCHL top five Vezina Trophy goalie candidates')
@app_commands.describe(minimum_games='Minimum games played to qualify (default 10)')
async def vezina(i:discord.Interaction,minimum_games:app_commands.Range[int,1,100]=10):
    await i.response.defer(thinking=True)
    try:
        records=await _vezina_goalies()
        ranked=_vezina_rank(records,minimum_games)
        if not ranked:
            return await i.followup.send(f'No goalies currently meet the {minimum_games}-game minimum. No trophy leader has been declared.')
        embed=discord.Embed(title='🏆 PlayCHL Vezina Trophy — Top 5',
            description=f'Unofficial performance-based goalie rankings • Minimum {minimum_games} GP\\n'
                        'Weights: SV% 35%, GAA 25%, W 15%, SO 10%, shots faced 10%, GP 5%. '
                        'Categories missing from the published table are excluded and remaining weights rescaled.',
            color=discord.Color.gold(),url='https://playchl.com/statistics')
        for index,(score,row) in enumerate(ranked[:5],1):
            name=next((row.get(k,'').strip() for k in ('PLAYER','NAME','GAMERTAG') if row.get(k,'').strip()),'Unknown')
            details=[]
            for label,keys in [('GP',('GP',)),('SV%',('SV%',)),('GAA',('GAA',)),
                               ('W',('W','WINS')),('SO',('SO','SHUTOUTS')),('SA',('SA',))]:
                value=_vezina_number(row,*keys)
                if value is not None:details.append(f'{label} {value:g}')
            embed.add_field(name=f'#{index} {name} • {row.get("TEAM","Unknown team")} — {score:.1f}/100',
                value=' · '.join(details) or 'No published details',inline=False)
        embed.set_footer(text='Source: PlayCHL goalie table • Scores are relative to eligible goalies • Not an official league award')
        await i.followup.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
    except Exception as exc:
        log.exception('Vezina leaderboard failed')
        await i.followup.send(f'Could not retrieve verified goalie stats: {str(exc)[:250]}')
    
@bot.tree.command(name='powerrefresh',description='Admin: refresh completed PlayCHL game scores')
async def powerrefresh(i:discord.Interaction):
    if not await require_admin(i):return
    await i.response.defer(ephemeral=True)
    try:
        a,b,c=await ingest()
        await i.followup.send(f'Updated game history: {a} new, {b} revised, {c} skipped invalid.',ephemeral=True)
    except Exception as e:await i.followup.send(f'Feed not available: {str(e)[:350]}',ephemeral=True)

@bot.tree.command(name='powerrankings',description='Show latest saved rankings (or live preview if none published)')
async def powerrankings(i:discord.Interaction):
    await i.response.defer(ephemeral=True)
    with db() as conn:s=get_snapshot(conn)
    if s:
        rows=json.loads(s['rankings_json']); messages=json.loads(s['messages_json']);end=s['week_end']
    else:
        end=week_end();rows=await current_rankings(end)
        if all(r['season']['gp']==0 for r in rows):return await i.followup.send('No games imported yet. Ask an admin to run /powerrefresh or /powerimport.',ephemeral=True)
        messages=await make_writeups(rows)
    await rankings_report(rows,messages,end,interaction=i)

@bot.tree.command(name='powerteam',description='See one team’s latest power ranking')
@app_commands.describe(team='Team abbreviation, e.g. WSH')
async def powerteam(i:discord.Interaction,team:str):
    team=team.upper().strip()
    if team not in TEAMS:return await i.response.send_message('Teams: '+', '.join(TEAMS),ephemeral=True)
    with db() as conn:s=get_snapshot(conn)
    if not s:return await i.response.send_message('No published rankings yet. Try /powerrankings.',ephemeral=True)
    row=next(r for r in json.loads(s['rankings_json']) if r['team']==team)
    msg=json.loads(s['messages_json'])
    await i.response.send_message(embed=build_embeds([row],msg,s['week_end'])[0],ephemeral=True)

@bot.tree.command(name='powercompare',description='Compare two teams in the latest snapshot')
async def powercompare(i:discord.Interaction,team1:str,team2:str):
    team1=team1.upper();team2=team2.upper()
    if team1 not in TEAMS or team2 not in TEAMS or team1==team2:
        return await i.response.send_message('Use two different team abbreviations from '+', '.join(TEAMS),ephemeral=True)
    with db() as conn:s=get_snapshot(conn)
    if not s:return await i.response.send_message('No published snapshot yet.',ephemeral=True)
    rows={r['team']:r for r in json.loads(s['rankings_json'])}
    a,b=rows[team1],rows[team2]
    def fmt(r):
        w=r['week'];season=r['season'];return f"#{r['rank']} | Score {r['score']:.1f}\nWeek {w['w']}-{w['l']}-{w['otl']} | GF-GA {w['gf']}-{w['ga']}\nSeason {season['w']}-{season['l']}-{season['otl']}"
    e=discord.Embed(title=f'{team1} vs {team2} · Power comparison',color=0x1260AA)
    e.add_field(name=a['name'],value=fmt(a));e.add_field(name=b['name'],value=fmt(b))
    await i.response.send_message(embed=e,ephemeral=True)

@bot.tree.command(name='powermovers',description='Biggest risers and fallers')
async def powermovers(i:discord.Interaction):
    with db() as conn:s=get_snapshot(conn)
    if not s:return await i.response.send_message('No published rankings yet.',ephemeral=True)
    rows=json.loads(s['rankings_json'])
    moves=[r for r in rows if r['movement'] is not None]
    if not moves:return await i.response.send_message('First published ranking: no movement history yet.',ephemeral=True)
    up=sorted((r for r in moves if r['movement']>0),key=lambda r:-r['movement'])
    down=sorted((r for r in moves if r['movement']<0),key=lambda r:r['movement'])
    fmt=lambda arr: '\n'.join(f"{r['team']}: {r['movement']:+d} spots (#{r['rank']})" for r in arr) or 'None'
    await i.response.send_message(f"**Biggest risers**\n{fmt(up)}\n\n**Biggest fallers**\n{fmt(down)}",ephemeral=True)

@bot.tree.command(name='powerhistory',description='See the dates of past published rankings')
async def powerhistory(i:discord.Interaction):
    with db() as conn:rows=conn.execute('SELECT week_end,channel_id,message_ids_json FROM snapshots ORDER BY week_end DESC LIMIT 20').fetchall()
    if not rows:return await i.response.send_message('No saved rankings yet.',ephemeral=True)
    lines=[]
    for row in rows:
        ids=json.loads(row['message_ids_json'] or '[]')
        link=f"https://discord.com/channels/{i.guild_id}/{row['channel_id']}/{ids[0]}" if ids and row['channel_id'] and i.guild_id else 'No post link'
        lines.append(f"**{row['week_end']}** — {link}")
    await i.response.send_message('\n'.join(lines),ephemeral=True)

@bot.tree.command(name='powerpublish',description='Admin: publish this week early (one post per week)')
async def powerpublish(i:discord.Interaction):
    if not await require_admin(i):return
    await i.response.defer(ephemeral=True)
    try:answer=await publish(week_end())
    except Exception as e:answer=f'Publish failed: {e}'
    await i.followup.send(answer,ephemeral=True)

@bot.tree.command(name='powerimport',description='Admin: import historical finals from an attached JSON file')
@app_commands.describe(file='JSON list of games; see games.example.json')
async def powerimport(i:discord.Interaction,file:discord.Attachment):
    if not await require_admin(i):return
    await i.response.defer(ephemeral=True)
    if file.size>2_000_000:return await i.followup.send('2 MB maximum file size.',ephemeral=True)
    try:
        data=json.loads((await file.read()).decode('utf-8'))
        if isinstance(data,dict):data=data['games']
        if not isinstance(data,list):raise ValueError('JSON root must be an array of games')
        with db() as conn:a,b,c=save_games(conn,data)
        await i.followup.send(f'Imported: {a} new, {b} updated, {c} invalid. Stored permanently.',ephemeral=True)
    except Exception as e:await i.followup.send('Import error: '+str(e)[:250],ephemeral=True)

if __name__=='__main__':
    if not TOKEN:raise SystemExit('Set DISCORD_TOKEN for the NEW dedicated bot')
    if not CHANNEL_ID:raise SystemExit('Set RANKINGS_CHANNEL_ID')
    with db():pass
    bot.run(TOKEN)
