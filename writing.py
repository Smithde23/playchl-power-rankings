"""Evidence-based NHL analyst copy. Gracefully works without AI credentials."""
import asyncio
import json
import os
from openai import AsyncOpenAI


def fallback(row):
    w=row['week'];s=row['season'];games=[g for g in row['games'] if not g['forfeit']]
    if not w['gp']:
        return (f"{row['name']} did not record a completed game during this ranking window. "
                f"Their season stands at {s['w']}-{s['l']}-{s['otl']}; their position is largely a reflection of earlier work.")
    trend=('a strong' if w['w']>w['l']+w['otl'] else 'a difficult' if w['w']<w['l']+w['otl'] else 'a mixed')
    top=max(games,key=lambda g:g['for_']-g['against']) if games else None
    note=(f" A notable result was a {top['for_']}-{top['against']} {'win' if top['win'] else 'loss'} against {top['opp']}." if top else '')
    return (f"{row['name']} delivered {trend} week at {w['w']}-{w['l']}-{w['otl']} "
            f"and sit {s['w']}-{s['l']}-{s['otl']} overall. "
            f"They scored {w['gf']} and allowed {w['ga']} goals in played games; forfeits are excluded from those goal totals.{note} "
            f"The next challenge is translating this stretch into consistent results against quality opposition.")


async def make_writeups(ranked):
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:return {r['team']:fallback(r) for r in ranked}
    client=AsyncOpenAI(api_key=key,timeout=35,max_retries=1)
    async def one(row):
        payload={'team':row['name'],'rank':row['rank'],'previous_rank':row['previous_rank'],
                 'week':row['week'],'season':row['season'],'games':row['games']}
        prompt=("Write a single 65-95 word analytical power-ranking blurb for the CHL NHL 27 esports team. "
                "Tone: professional NHL hockey analyst, insightful and restrained. Focus on the supplied "
                "weekly results in season context; reference a specific matchup when possible. "
                "Do not invent player names, goalie metrics, streaks, or events. "
                "Forfeit games count as wins or losses but do not support claims about on-ice play or goal production. "
                "If weekly games=0, state the ranking is driven by prior season results. Output plain prose only.\n"+json.dumps(payload))
        try:
            res=await client.chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),
                messages=[{'role':'system','content':'You are an accurate professional hockey analyst.'},
                          {'role':'user','content':prompt}],temperature=.45,max_tokens=180)
            value=(res.choices[0].message.content or '').strip()
            return row['team'],value[:1100] if value else fallback(row)
        except Exception:
            return row['team'],fallback(row)
    answer={}
    for i in range(0,len(ranked),3):
        answer.update(await asyncio.gather(*(one(r) for r in ranked[i:i+3])))
    return answer
