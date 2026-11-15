import random
import unittest
from story import build_narration, select_style, STYLES

GAME={"id":"sample","date":"2026-11-14T23:00:00+00:00","away":"WSH","home":"UTAH","a":6,"h":7,"status":"Final"}
BOX={"source":"chelhead","players":[
    {"team":"WSH","name":"Buckley0306","pos":"C","stats":{"G":"2","A":"3","P":"5","SH":"0"}},
    {"team":"WSH","name":"Reqhzii","pos":"RW","stats":{"G":"2","A":"1","P":"3","SH":"7"}},
    {"team":"WSH","name":"Charlielucia13","pos":"G","stats":{"SV":"13","SV%":"0.650"}},
    {"team":"UTAH","name":"OffsKripT I72I","pos":"LW","stats":{"G":"4","A":"3","P":"7"}}
],"match":{}}

class StoryTests(unittest.TestCase):
    def test_six_distinct_angles_with_identical_facts(self):
        scripts=[]
        for k,style in enumerate(STYLES):
            speech,chosen=build_narration(GAME,BOX,style=style,rng=random.Random(10+k))
            self.assertEqual(chosen,style)
            self.assertIn("Buckley0306",speech)
            self.assertIn("Utah",speech)
            self.assertIn("Washington",speech)
            scripts.append(speech)
        self.assertEqual(len(set(scripts)),len(STYLES))

    def test_repeated_styles_do_not_repeat_immediately(self):
        for prev in STYLES:
            for seed in range(15):
                self.assertNotEqual(select_style(prev,random.Random(seed)),prev)

    def test_missing_box_does_not_create_player_claim(self):
        for style in STYLES:
            speech,_=build_narration(GAME,None,style=style,rng=random.Random(5))
            self.assertNotIn("Buckley",speech)
            self.assertIn("not yet confirmed",speech)

    def test_forfeit_no_play_by_play(self):
        g=dict(GAME,status="Forfeit")
        speech,_=build_narration(g,BOX,rng=random.Random(0))
        self.assertIn("administrative",speech)
        self.assertNotIn("Buckley",speech)

if __name__=="__main__":unittest.main()
