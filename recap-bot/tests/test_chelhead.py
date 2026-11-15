import unittest
from datetime import datetime,timezone,timedelta
from chelhead import card_candidates,extract_box

GAME={"id":"test","date":datetime.now(timezone.utc).isoformat(),"away":"WSH","home":"UTAH","a":6,"h":7,"status":"Final"}
POPUP="""CLOSE SUMMARY PLAYERS Login Players 1ST OffsKripT I72I 29.34 2ND IIM PETER 19.66
3RD Buckley0306 15.04
CHL27 WASHINGTON CAPITALS 6 L
PLAYER G GOALS A ASSISTS P POINTS +/- PLUS MINUS SH SHOTS HIT HITS BLK BLOCKED SHOTS TK TAKEAWAYS GV GIVEAWAYS STAR SCORE DETAILS
C 3rd Star, Buckley0306 , Center 2 3 5 -1 0 0 0 1 9 15.04
RW Reqhzii , Right Wing 2 1 3 -1 7 3 0 3 3 14.00
LW CrazyJHawk91 , Left Wing 0 3 3 -1 7 2 0 3 6 12.62
LD YESHUA_RETURNS , Left Defense 0 3 3 -1 2 0 2 1 2 10.83
RD KASKADE_420 , Right Defense 2 0 2 -1 3 4 0 6 1 12.08
TOTAL 6 10 16 19 9 2 14 21
GOALIES PLAYER SV% SAVE PERCENTAGE GAA GOALS AGAINST AVERAGE SV SAVES SA SHOTS AGAINST STAR SCORE DETAILS
G Charlielucia13 0.650 7.00 13 20 1.60
CHL27 UTAH MAMMOTH 7 W
PLAYER G GOALS A ASSISTS P POINTS +/- PLUS MINUS SH SHOTS HIT HITS BLK BLOCKED SHOTS TK TAKEAWAYS GV GIVEAWAYS STAR SCORE DETAILS
LW 1st Star, OffsKripT I72I , Left Wing 4 3 7 +1 7 0 0 3 18 29.34
C 2nd Star, IIM PETER , Center 1 3 4 +1 4 6 0 2 2 19.66
RW kadokincaid , Right Wing 1 2 3 +1 2 4 0 1 7 11.56
RD xBuium28- , Right Defense 1 1 2 +1 4 2 1 2 1 11.45
LD FLwestcoast775 , Left Defense 0 1 1 +1 0 1 0 0 4 3.47
TOTAL 7 10 17 17 13 1 8 32
GOALIES PLAYER SV% SAVE PERCENTAGE GAA GOALS AGAINST AVERAGE SV SAVES SA SHOTS AGAINST STAR SCORE DETAILS
G The_milky_Way420 0.730 6.00 16 22 7.20
"""

class FallbackTests(unittest.TestCase):
    def test_popup_extracts_and_attributes_players(self):
        box=extract_box(POPUP,GAME)
        self.assertIsNotNone(box)
        mapped={p["name"]:p for p in box["players"]}
        self.assertEqual(mapped["Buckley0306"]["team"],"WSH")
        self.assertEqual(mapped["Buckley0306"]["stats"]["G"],"2")
        self.assertEqual(mapped["Buckley0306"]["stats"]["A"],"3")
        self.assertEqual(mapped["Charlielucia13"]["stats"]["SV"],"13")
        self.assertEqual(mapped["OffsKripT"]["team"],"UTAH")

    def test_wrong_score_rejected(self):
        wrong=dict(GAME,a=5)
        self.assertIsNone(extract_box(POPUP,wrong))

    def test_wrong_opponent_rejected(self):
        wrong=dict(GAME,home="DET")
        self.assertIsNone(extract_box(POPUP,wrong))

    def test_reverse_fixture_not_matched(self):
        opposite={"id":"opposite","text":"6v6 lobby. CHL27 UTAH MAMMOTH 6 at CHL27 WASHINGTON CAPITALS 7. 1 days ago"}
        correct={"id":"correct","text":"6v6 lobby. CHL27 WASHINGTON CAPITALS 6 at CHL27 UTAH MAMMOTH 7. 1 days ago"}
        matches=card_candidates([opposite,correct],GAME)
        self.assertEqual([x["id"] for x in matches],["correct"])

    def test_ambiguous_cards_rejected_by_resolver(self):
        card={"id":"1","text":"6v6 lobby. CHL27 WASHINGTON CAPITALS 6 at CHL27 UTAH MAMMOTH 7. 0 hours ago"}
        self.assertEqual(len(card_candidates([card,dict(card,id="2")],GAME)),2)

if __name__=="__main__":unittest.main()
