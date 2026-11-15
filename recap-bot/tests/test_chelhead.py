import unittest
from datetime import datetime,timezone,timedelta
from chelhead import card_candidates,extract_box

GAME={"id":"test","date":datetime.now(timezone.utc).isoformat(),"away":"WSH","home":"UTAH","a":6,"h":7,"status":"Final"}
POPUP="""CLOSE SUMMARY PLAYERS Players
CHL27 WASHINGTON CAPITALS DIV 8 6 - 7 CHL27 UTAH MAMMOTH DIV 5 FINAL
CHL27 WASHINGTON CAPITALS 6 L
PLAYER G A P +/- SH HIT BLK TK GV ★
C Buckley0306 2 3 5 -1 0 0 0 1 9 15.04
RW Reqhzii 2 1 3 -1 7 3 0 3 3 14.00
GOALIES PLAYER SV% GAA SV SA ★
G Charlielucia13 0.650 7.00 13 20 1.60
CHL27 UTAH MAMMOTH 7 W
PLAYER G A P +/- SH HIT BLK TK GV ★
LW OffsKripT 4 3 7 1 7 0 0 3 18 29.34
GOALIES PLAYER SV% GAA SV SA ★
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
