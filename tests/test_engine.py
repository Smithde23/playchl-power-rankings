import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from engine import database,save_games,rank,week_end,week_bounds,normalize
from sources import parse_schedule

class RankingTests(unittest.TestCase):
    def test_schedule(self):
        txt='Nov 5 1:00 AM UTC REG SEA Away 4-3 DET Home Final Nov 5 1:35 AM UTC REG ANA Away 0-1 BUF Home Forfeit'
        data=parse_schedule(txt,datetime(2026,11,13,tzinfo=timezone.utc))
        self.assertEqual(len(data),2)
        self.assertEqual(data[1]['status'],'Forfeit')
    def test_snapshot_math_and_forfeits(self):
        with tempfile.TemporaryDirectory() as d:
            with database(Path(d)/'x.sqlite3') as db:
                a,b,c=save_games(db,[
                dict(date='2026-11-12T01:00:00Z',away='WSH',home='BUF',away_score=5,home_score=2,status='Final'),
                dict(date='2026-11-13T01:00:00Z',away='ANA',home='WSH',away_score=0,home_score=1,status='Forfeit')])
                self.assertEqual((a,b,c),(2,0,0))
                ranked=rank(db,'2026-11-14')
                w=next(x for x in ranked if x['team']=='WSH')
                self.assertEqual(w['week']['w'],2)
                self.assertEqual(w['week']['gf'],5)
                self.assertEqual(w['week']['ga'],2)
                self.assertEqual(len(ranked),10)
                self.assertEqual(sorted(x['rank'] for x in ranked),list(range(1,11)))
    def test_week_utc_boundary(self):
        a,b=week_bounds('2026-11-14')
        self.assertEqual(a.weekday(),6)
        self.assertEqual(b.weekday(),6)
if __name__=='__main__':unittest.main()
