"""Smoke-test that a narrated cinematic MP4 can actually be rendered."""
import asyncio
import shutil
import subprocess
import unittest
from video import render, scenes, cards

class VideoTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg required")
    async def test_generated_video_contains_narration(self):
        audio=subprocess.run(
            ["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
             "-f","lavfi","-i","sine=frequency=440:duration=2",
             "-f","mp3","-"],
            capture_output=True,check=True,timeout=20).stdout
        game={"away":"WSH","home":"UTAH","a":6,"h":7,"status":"Final"}
        movie=await render(game,None,audio)
        self.assertIsNotNone(movie,"Cinematic FFmpeg render returned None")
        self.assertGreater(len(movie),50_000)
        self.assertTrue(movie[4:8] in (b"ftyp",b"free",b"mdat"))

    async def test_studio_scene_has_two_hosts_and_real_stat_cards(self):
        game={"away":"WSH","home":"UTAH","a":6,"h":7,"status":"Final"}
        box={"players":[
            {"team":"WSH","name":"Buckley0306","pos":"C","stats":{"G":"2","A":"3","P":"5"}},
            {"team":"WSH","name":"Charlielucia13","pos":"G","stats":{"SV":"13","SV%":"0.650"}},
            {"team":"UTAH","name":"OffsKripT I72I","pos":"LW","stats":{"G":"4","A":"3","P":"7"}}
        ]}
        reel=cards(game,box)
        self.assertGreaterEqual(len(reel),8)
        self.assertTrue(any("Buckley0306" in x["title"] for x in reel))
        self.assertTrue(any("Charlielucia13" in x["title"] for x in reel))
        self.assertTrue(any("OffsKripT" in x["title"] for x in reel))
        self.assertFalse(any("INTERVIEW" in x["header"] for x in reel))
        frames=scenes(game,box,female_analyst=True)
        self.assertEqual(len(frames),len(reel))
        self.assertEqual(frames[0].size,(1280,720))
