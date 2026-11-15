import random
import shutil
import subprocess
import unittest

from broadcast import make_dialogue,print_transcript,audio_text,_join_mp3,voice_pair
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

    def test_original_voices_are_distinct(self):
        for i in range(3):
            primary,analyst=voice_pair(i)
            self.assertNotEqual(primary,analyst)

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
        probe=subprocess.run(
            ["ffprobe","-v","error","-f","mp3","-show_entries","format=duration",
             "-of","default=noprint_wrappers=1:nokey=1","pipe:0"],
            input=combined,capture_output=True,check=True,timeout=10)
        self.assertGreater(float(probe.stdout.strip()),0.8)

if __name__=="__main__":unittest.main()
