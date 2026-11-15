"""Original TWO-VOICE Washington Capitals broadcast (never impersonates real people).

All dialogue draws exclusively from verified final score and matched game box score.
The color analyst describes what the numbers show, not invented gameplay.
"""
import asyncio
import io
import logging
import os
import random
import subprocess
import tempfile
from pathlib import Path

from story import TEAMS, top_players, number

log=logging.getLogger("chl.broadcast")
PAIRS=(
    ("en-US-GuyNeural","en-US-ChristopherNeural"),
    ("en-US-RogerNeural","en-US-GuyNeural"),
    ("en-US-ChristopherNeural","en-US-RogerNeural"),
)
# Allow an operator to set specific original TTS voices, not real broadcaster clones.
def voice_pair(index=0):
    a=os.getenv("PLAY_BY_PLAY_VOICE","").strip()
    b=os.getenv("ANALYST_VOICE","").strip()
    p,q=PAIRS[index % len(PAIRS)]
    return a or p,b or q

def _player(p,rng):
    name=p["name"];stats=p["stats"]
    if p.get("pos")=="G":
        saves=stats.get("SV")
        return (f"{name} is credited with {saves} saves." if saves is not None else "")
    goals=number(p,"G");assists=number(p,"A");pts=number(p,"P")
    if pts<=0:return ""
    if goals and assists:
        return rng.choice((
            f"{name} finishes with {goals} goals, {assists} assists, and {pts} points.",
            f"The box score has {name} at {pts} points, from {goals} goals and {assists} assists.",
            f"For {name}, that's {goals} goals and {assists} helpers. {pts} points in total.",
        ))
    if goals:
        return f"{name} records {goals} goals and {pts} points."
    return f"{name} contributes {assists} assists and {pts} points."

def make_dialogue(game,box,style="score_first",rng=None):
    """Alternating tuples (role, line), where role is 'play' or 'analyst'."""
    rng=rng or random.SystemRandom()
    away=game["away"];home=game["home"]
    if "WSH" not in (away,home):raise ValueError("Capitals games only")
    rival=home if away=="WSH" else away
    rival_name=TEAMS[rival]
    wsh=int(game["a"] if away=="WSH" else game["h"])
    other=int(game["h"] if away=="WSH" else game["a"])
    won=wsh>other
    close=abs(wsh-other)==1
    result=f"Washington {wsh}, {rival_name} {other}."
    if game.get("status")=="Forfeit":
        return [
            ("play",f"An official CHL result for Washington against {rival_name}. The recorded score is {result}"),
            ("analyst","This is a forfeit, an administrative result. We are not describing this as a played hockey game."),
            ("play","That's the official report. We'll return with confirmed results from the next game."),
        ]
    caps,cgoalies=top_players(box,"WSH")
    opponents,ogoalies=top_players(box,rival)
    leaders=[p for p in caps if number(p,"P")>0]
    rival_leaders=[p for p in opponents if number(p,"P")>0]
    player=leaders[0] if leaders else (cgoalies[0] if cgoalies else None)
    rival_player=rival_leaders[0] if rival_leaders else (ogoalies[0] if ogoalies else None)
    intros={
        "score_first":(f"Washington and {rival_name}. The final is in. {result}",
                       "That score catches your eye. Now let's look at the players who put up the numbers."),
        "player_first":(f"Welcome to the Capitals postgame desk. The score is final: {result}",
                        "Absolutely. There's a player performance worth talking about here."),
        "matchup":(f"Two clubs, one CHL matchup. The Capitals face {rival_name}, and the result is {result}",
                   "Exactly. Let's get into the numbers behind that result."),
        "scoreboard":(f"The final horn is in the books. Washington against {rival_name}: {result}",
                      "Right. And I want to look at what the box score says about both clubs."),
        "spotlight":(f"Tonight's Capitals spotlight begins with the game result. {result}",
                     "I'm glad you brought that up. One Capitals name jumps right off the stat sheet."),
        "season":(f"One more chapter in the Capitals' CHL season. The official final: {result}",
                  "And those player numbers are where this one gets interesting."),
    }
    intro,bridge=intros.get(style,intros["score_first"])
    sections=[("play",intro),("analyst",bridge)]
    if player:
        sections.append(("play",rng.choice(("Who jumps out for Washington?",
                                            "Give me the Capitals standout.",
                                            "Okay, who made the biggest mark in Washington's box score?"))))
        sections.append(("analyst",_player(player,rng)))
    else:
        sections.append(("play","The verified final is available, but this game's full player report is not confirmed."))
        sections.append(("analyst","So we won't guess at goalscorers, game-changing plays, or individual performances."))
    if len(leaders)>1:
        sections.append(("play",rng.choice(("And they weren't the only Capitals player putting up numbers, right?",
                                            "What about the other Washington contributors?"))))
        sections.append(("analyst",_player(leaders[1],rng)))
    elif cgoalies and player is not cgoalies[0]:
        sections.append(("play","And between the pipes, what do the numbers show?"))
        sections.append(("analyst",_player(cgoalies[0],rng)))
    if rival_player:
        sections.append(("play",f"Fair enough. What about {rival_name}?"))
        sections.append(("analyst",_player(rival_player,rng)))
    sections.append(("play",rng.choice((
        "Now, the final margin. Just one goal separates the teams." if close else f"The final margin is {abs(wsh-other)} goals.",
        "It's a one-goal final on the scoreboard." if close else f"A {abs(wsh-other)}-goal margin on the final scoreboard.",
    ))))
    sections.append(("analyst",rng.choice((
        "One goal separates the teams, and that is a tight final on paper.",
        "The final margin tells us where the matchup ended; the players' totals add the context.",
        "Exactly. Those numbers are the record, and the next game gives both teams another chance.",
    ))))
    if won:
        sections.append(("play",rng.choice((
            "Washington gets the victory. That's this chapter of the Capitals season.",
            "A win for the Capitals. Another result goes into the CHL record.",
        ))))
        sections.append(("analyst","And that's what makes this league fun to follow. Every game adds another chapter."))
    else:
        sections.append(("play",rng.choice((
            f"The win goes to {rival_name}. Washington will look for a response next time.",
            "The Capitals come up short in the final. The season continues.",
        ))))
        sections.append(("analyst","Exactly. You can't change the final. You can decide how you respond next game."))
    return [(role,text.strip()) for role,text in sections if text and text.strip()]

def print_transcript(lines):
    return "\n\n".join(("PLAY-BY-PLAY" if role=="play" else "COLOR ANALYST")+": "+text
                     for role,text in lines)

def audio_text(lines):
    return "\n\n".join(text for _,text in lines)

def _join_mp3(audio_list, pause_ms=170):
    """Re-encode MP3 clips plus original pauses, preserving role order."""
    if not audio_list or any(len(x)<400 for x in audio_list):
        raise ValueError("Missing synthesized speaker segment")
    with tempfile.TemporaryDirectory(prefix="chl-two-voices-") as directory:
        root=Path(directory)
        silence=root/"gap.mp3"
        subprocess.run(
            ["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
             "-f","lavfi","-i","anullsrc=r=24000:cl=mono",
             "-t",str(pause_ms/1000),"-codec:a","libmp3lame","-q:a","7",str(silence)],
            capture_output=True,check=True,timeout=12)
        concat=[]
        rng=random.SystemRandom()
        for i,chunk in enumerate(audio_list):
            target=root/f"speaker-{i:02d}.mp3"
            target.write_bytes(chunk)
            concat.append("file '"+str(target)+"'")
            if i<len(audio_list)-1:
                concat.extend(["file '"+str(silence)+"'"]*rng.choice((1,1,2,3)))
        (root/"playlist.txt").write_text("\n".join(concat)+"\n")
        result=root/"broadcast.mp3"
        process=subprocess.run(
            ["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
             "-f","concat","-safe","0","-i",str(root/"playlist.txt"),
             "-ar","24000","-ac","1","-codec:a","libmp3lame",
             "-b:a","112k",str(result)],
            capture_output=True,text=True,timeout=70)
        if process.returncode:
            raise RuntimeError("Audio assembly failed: "+process.stderr[-700:])
        combined=result.read_bytes()
        if len(combined)<400:raise RuntimeError("Empty combined broadcast audio")
        return combined

async def synthesize_dialogue(lines,voice_index=0,play_voice=None,analyst_voice=None):
    """Two unique, original neural voices. Synthesis can fail without making up audio."""
    import edge_tts
    p,a=voice_pair(voice_index)
    p=play_voice or p;a=analyst_voice or a
    if p==a:raise ValueError("Two distinct commentator voice IDs required")
    gate=asyncio.Semaphore(3)
    async def speak(role,words):
        voice=p if role=="play" else a
        is_question=words.rstrip().endswith("?")
        energetic=any(term in words.lower() for term in ("victory","the win","final","standout","goals","points"))
        if role=="play":
            rate=random.choice(("+3%","+6%","+8%","+10%")) if energetic else random.choice(("+1%","+3%","+5%"))
            pitch=random.choice(("+0Hz","+2Hz","+4Hz")) if energetic else "+0Hz"
        else:
            rate=random.choice(("+1%","+3%")) if is_question else random.choice(("-5%","-3%","+0%"))
            pitch=random.choice(("-5Hz","-3Hz","-1Hz"))
        async with gate:
            chunks=[]
            async for event in edge_tts.Communicate(words,voice=voice,rate=rate,pitch=pitch).stream():
                if event["type"]=="audio":chunks.append(event["data"])
            voice_data=b"".join(chunks)
            if len(voice_data)<400:raise RuntimeError("Voice service returned empty audio")
            return voice_data
    rendered=await asyncio.gather(*(speak(role,text) for role,text in lines))
    joined=await asyncio.to_thread(_join_mp3,rendered)
    log.info("Two-voice broadcast: %s and %s, %d exchanges, %d bytes",p,a,len(lines),len(joined))
    return joined
