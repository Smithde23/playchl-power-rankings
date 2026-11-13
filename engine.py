"""CHL game normalization, durable snapshots, transparent power score.
Rankings are earned from recorded final games; LLM never assigns ranks.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone, time
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
TEAMS = {'ANA':'Anaheim Ducks','BUF':'Buffalo Sabres','CGY':'Calgary Flames',
         'DET':'Detroit Red Wings','MIN':'Minnesota Wild','SEA':'Seattle Kraken',
         'SJS':'San Jose Sharks','UTAH':'Utah Mammoth','VGK':'Vegas Golden Knights',
         'WSH':'Washington Capitals'}
ALIAS = {'UTA':'UTAH','SJ':'SJS'}
FINAL = ('final','forfeit')


def utc_date(value):
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None:
        raise ValueError('game date must include timezone, e.g. Z')
    return dt.astimezone(timezone.utc)


def normalize(raw):
    away = ALIAS.get(str(raw.get('away','')).upper(),str(raw.get('away','')).upper())
    home = ALIAS.get(str(raw.get('home','')).upper(),str(raw.get('home','')).upper())
    if away not in TEAMS or home not in TEAMS or away == home:
        raise ValueError('Unknown team(s) or duplicate teams')
    status = str(raw.get('status','')).lower().strip()
    if not any(status.startswith(x) for x in FINAL):
        raise ValueError('Not a final game')
    a, h = int(raw['away_score']), int(raw['home_score'])
    if a < 0 or h < 0 or a == h:
        raise ValueError('Invalid final score')
    dt = utc_date(raw['date'])
    is_forfeit = status.startswith('forfeit')
    natural_id = f'{dt.isoformat()}:{away}:{home}'
    game_id = str(raw.get('id') or hashlib.sha256(natural_id.encode()).hexdigest()[:24])
    return {'id': game_id, 'date':dt.isoformat(), 'away':away,'home':home,
            'away_score':a,'home_score':h,'status':'Forfeit' if is_forfeit else 'Final',
            'overtime':('ot' in status or bool(raw.get('overtime',False)))}


def database(path):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(str(path),timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA busy_timeout=30000')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS games(
      id TEXT PRIMARY KEY, played_at TEXT NOT NULL, away TEXT NOT NULL, home TEXT NOT NULL,
      away_score INTEGER NOT NULL, home_score INTEGER NOT NULL, status TEXT NOT NULL, overtime INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_games_date ON games(played_at);
    CREATE TABLE IF NOT EXISTS snapshots(
      week_end TEXT PRIMARY KEY, published_at TEXT NOT NULL, rankings_json TEXT NOT NULL,
      messages_json TEXT NOT NULL, channel_id TEXT, message_ids_json TEXT);
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    ''')
    return db


def save_games(db, raw_games):
    added = changed = invalid = 0
    for raw in raw_games:
        try: g=normalize(raw)
        except (ValueError,KeyError,TypeError,OverflowError):
            invalid += 1; continue
        old=db.execute('SELECT * FROM games WHERE id=?',(g['id'],)).fetchone()
        vals=(g['id'],g['date'],g['away'],g['home'],g['away_score'],g['home_score'],g['status'],int(g['overtime']))
        if old is None: added += 1
        elif any(old[k]!=v for k,v in zip(('played_at','away','home','away_score','home_score','status','overtime'),vals[1:])): changed += 1
        db.execute('''INSERT INTO games VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        played_at=excluded.played_at,away=excluded.away,home=excluded.home,
        away_score=excluded.away_score,home_score=excluded.home_score,
        status=excluded.status,overtime=excluded.overtime''',vals)
    db.commit()
    return added,changed,invalid


def week_end(now=None):
    """Week runs Sunday 00:00 through Saturday 23:59:59 Eastern."""
    now=(now or datetime.now(ET)).astimezone(ET)
    return (now.date()+timedelta(days=(5-now.weekday())%7)).isoformat()


def week_bounds(end):
    saturday=datetime.fromisoformat(end).date()
    if saturday.weekday()!=5: raise ValueError('Week ending must be a Saturday')
    start=datetime.combine(saturday-timedelta(days=6),time.min,tzinfo=ET)
    stop=start+timedelta(days=7)
    return start,stop


def game_rows(db,at=None):
    at=at or datetime.now(timezone.utc)
    return [dict(x) for x in db.execute('SELECT * FROM games WHERE played_at < ? ORDER BY played_at,id', (at.astimezone(timezone.utc).isoformat(),))]


def stats(games, start=None,stop=None, forfeit_record=True):
    s={t:dict(gp=0,w=0,l=0,otl=0,gf=0,ga=0,opponents=[],results=[],games=[]) for t in TEAMS}
    for g in games:
        when=utc_date(g['played_at']).astimezone(ET)
        if (start is not None and when<start) or (stop is not None and when>=stop):continue
        if g['status']=='Forfeit' and not forfeit_record:continue
        a,h=g['away'],g['home'];as_,hs=g['away_score'],g['home_score']
        for team,opp,sc,against in [(a,h,as_,hs),(h,a,hs,as_)]:
            z=s[team]; win=sc>against
            z['gp']+=1;z['w']+=int(win)
            if not win:
                if g.get('overtime'):z['otl']+=1
                else:z['l']+=1
            if g['status']!='Forfeit':z['gf']+=sc;z['ga']+=against
            z['opponents'].append(opp);z['results'].append(int(win))
            z['games'].append(dict(opp=opp,for_=sc,against=against,win=win,forfeit=g['status']=='Forfeit',date=g['played_at']))
    return s


def pct(t):
    return (t['w']+0.5*t['otl'])/t['gp'] if t['gp'] else 0


def clipped(x,a,b):return min(b,max(a,x))


def rank(db,end,prior=None,forfeit_record=True):
    start,stop=week_bounds(end)
    full=game_rows(db,stop.astimezone(timezone.utc))
    season=stats(full,stop=stop,forfeit_record=forfeit_record)
    weekly=stats(full,start=start,stop=stop,forfeit_record=forfeit_record)
    ranked=[]
    for t in TEAMS:
        w=weekly[t];s=season[t]
        weekly_pct=pct(w) if w['gp'] else 0.5
        season_pct=pct(s) if s['gp'] else 0.5
        played_games=sum(not game['forfeit'] for game in w['games'])
        gd_per_game=(w['gf']-w['ga'])/played_games if played_games else 0
        gd_index=clipped(50+gd_per_game*10,0,100)
        strength=(sum(pct(season[opp]) if season[opp]['gp'] else .5 for opp in w['opponents'])/len(w['opponents'])) if w['gp'] else .5
        momentum=(sum((i+1)*result for i,result in enumerate(w['results']))/sum(range(1,len(w['results'])+1))) if w['results'] else .5
        score=(.40*weekly_pct*100 + .20*season_pct*100 + .15*gd_index + .15*strength*100 + .10*momentum*100)
        if not w['gp']:score-=12
        ranked.append({'team':t,'name':TEAMS[t], 'score':round(score,2),'week':{k:w[k] for k in ('gp','w','l','otl','gf','ga')},
                       'season':{k:s[k] for k in ('gp','w','l','otl','gf','ga')},'games':w['games'],
                       'strength':round(strength,3)})
    ranked.sort(key=lambda x:(-x['score'],-x['week']['w'],-x['season']['w'],x['team']))
    old={r['team']:i+1 for i,r in enumerate(prior or [])}
    for i,r in enumerate(ranked):
        r['rank']=i+1;r['previous_rank']=old.get(r['team'])
        r['movement']=(old[r['team']]-(i+1)) if r['team'] in old else None
    return ranked


def previous(db,end):
    row=db.execute('SELECT rankings_json FROM snapshots WHERE week_end < ? ORDER BY week_end DESC LIMIT 1',(end,)).fetchone()
    return json.loads(row['rankings_json']) if row else None


def snapshot(db,end,ranking,messages,channel_id=None,message_ids=None):
    db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?)',(
        end,datetime.now(timezone.utc).isoformat(),json.dumps(ranking),json.dumps(messages),
        str(channel_id) if channel_id else None,json.dumps(message_ids or [])))
    db.commit()


def get_snapshot(db,end=None):
    row=db.execute('SELECT * FROM snapshots '+('WHERE week_end=?' if end else 'ORDER BY week_end DESC LIMIT 1'), ((end,) if end else ())).fetchone()
    return dict(row) if row else None
