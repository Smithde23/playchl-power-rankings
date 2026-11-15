import random
import shutil
import subprocess
import unittest

from broadcast import make_dialogue,print_transcript,audio_text,_join_mp3,voice_pair,PAIRS
from test_story import GAME,BOX

class BroadcastTests(unittest.TestCase):
    def test_two_roles_alternate_and_include_verified_players(self):
        for k,style in enumerate(("score_first","player_first","matchup","scoreboard","spotlight","season")):
            dialogue=make_dialogue(GAME,BOX,style=style,rng=random.Random(k))
            self.assertGreaterEqual(len(dialogue),7)
            roles=[role for role,_ in dialogue]
            self.assertEqual(roles[0],"play")
            self.assertEqual(roles[1],"analyst")
            self.assertTrue(all(a!=b for a,b in zip(roles,roles[1:])))
            words=audio_text(dialogue)
            self.assertIn("Buckley0306",words)
            self.assertIn("Utah",words)
            self.assertIn("Washington",words)
            self.assertIn("PLAY-BY-PLAY",print_transcript(dialogue))
            self.assertIn("COLOR ANALYST",print_transcript(dialogue))

    def test_missing_stats_are_not_invented(self):
        dialogue=make_dialogue(GAME,None,rng=random.Random(1))
        spoken=audio_text(dialogue)
        self.assertNotIn("Buckley",spoken)
        self.assertIn("not confirmed",spoken)
        self.assertNotIn("late winning goal",spoken)

    def test_forfeit_is_administrative(self):
        game=dict(GAME,status="Forfeit")
        dialogue=make_dialogue(game,BOX,rng=random.Random(1))
        spoken=audio_text(dialogue)
        self.assertIn("administrative",spoken)
        self.assertNotIn("Buckley",spoken)

    def test_conversational_replies_and_nonclose_factual_margin(self):
        game=dict(GAME,a=4,h=7)
        for i in range(30):
            lines=make_dialogue(game,BOX,style="matchup",rng=random.Random(i))
            words=audio_text(lines).lower()
            self.assertNotIn("one goal separates",words)
            self.assertNotIn("one-goal final",words)
            self.assertNotIn("game-winning goal",words)
            self.assertTrue(any("?" in text for _,text in lines))
            self.assertIn("Buckley0306",audio_text(lines))

    def test_original_voices_are_distinct(self):
        female_analysts=0
        male_analysts=0
        for i in range(len(PAIRS)):
            primary,analyst=voice_pair(i)
            self.assertNotEqual(primary,analyst)
            if analyst in ("en-US-JennyNeural","en-US-AriaNeural"):
                female_analysts+=1
            else:male_analysts+=1
        self.assertGreaterEqual(female_analysts,2)
        self.assertGreaterEqual(male_analysts,1)

    def test_extended_player_analysis_stays_factually_grounded(self):
        complete={"players":[
            {"team":"WSH","name":"Buckley0306","pos":"C","stats":{"G":"2","A":"3","P":"5","SH":"0"}},
            {"team":"WSH","name":"Reqhzii","pos":"RW","stats":{"G":"2","A":"1","P":"3","SH":"7"}},
            {"team":"WSH","name":"KASKADE_420","pos":"RD","stats":{"G":"2","A":"0","P":"2","SH":"3"}},
            {"team":"WSH","name":"Charlielucia13","pos":"G","stats":{"SV":"13"}},
            {"team":"UTAH","name":"OffsKripT I72I","pos":"LW","stats":{"G":"4","A":"3","P":"7","SH":"7"}},
            {"team":"UTAH","name":"IIM PETER","pos":"C","stats":{"G":"1","A":"3","P":"4","SH":"4"}}
        ],"match":{}}
        lines=make_dialogue(GAME,complete,style="player_first",rng=random.Random(9))
        speech=audio_text(lines)
        for name in ("Buckley0306","Reqhzii","KASKADE_420","Charlielucia13","OffsKripT I72I","IIM PETER"):
            self.assertIn(name,speech)
        self.assertGreaterEqual(len(lines),16)
        self.assertTrue(all(a!=b for a,b in zip([x[0] for x in lines],[x[0] for x in lines][1:])))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg tools unavailable")
    def test_two_speaker_audio_segments_join_into_valid_mp3(self):
        samples=[]
        for hz in (220,430,300):
            data=subprocess.run(
                ["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-f","lavfi",
                 "-i",f"sine=frequency={hz}:duration=0.3","-codec:a","libmp3lame","-f","mp3","-"],
                capture_output=True,check=True,timeout=10).stdout
            samples.append(data)
        combined=_join_mp3(samples,120)
        self.assertGreater(len(combined),2000)
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as work:
            output=Path(work)/"two-hosts.mp3"
            output.write_bytes(combined)
            probe=subprocess.run(
                ["ffprobe","-v","error","-show_entries","format=duration",
                 "-of","default=noprint_wrappers=1:nokey=1",str(output)],
                capture_output=True,check=True,timeout=10)
            self.assertGreater(float(probe.stdout.strip()),0.8)

if __name__=="__main__":unittest.main()
