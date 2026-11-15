"""Smoke-test that a narrated cinematic MP4 can actually be rendered."""
import asyncio
import shutil
import subprocess
import unittest
from video import render

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
