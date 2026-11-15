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
    ("en-US-GuyNeural","en-US-JennyNeural"),
    ("en-US-RogerNeural","en-US-AriaNeural"),
    ("en-US-ChristopherNeural","en-US-GuyNeural"),
    ("en-US-GuyNeural","en-US-ChristopherNeural"),
)
# Both female and male color analysts rotate, without mimicking any
# real broadcaster. Override ANALYST_VOICE to use one consistently.
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
    """Fast-paced two-host story with grounded standouts, opposition and closing.

    This is an editorial recap of verified aggregates, never claimed play-by-play.
    No official Three Stars, scoring order, standings movement or comeback is
    invented. Two alternating roles remain compatible with the audio mixer.
    """
    rng=rng or random.SystemRandom()
    away,home=game["away"],game["home"]
    if "WSH" not in (away,home):raise ValueError("Capitals games only")
    rival=home if away=="WSH" else away
    rival_name=TEAMS[rival]
    wsh=int(game["a"] if away=="WSH" else game["h"])
    other=int(game["h"] if away=="WSH" else game["a"])
    won=wsh>other
    diff=abs(wsh-other)
    winner="Washington" if won else rival_name
    loser=rival_name if won else "Washington"
    winner_score=max(wsh,other)
    loser_score=min(wsh,other)
    location="at home" if (home=="WSH" and won) or (home==rival and not won) else "on the road"
    if game.get("status")=="Forfeit":
        return [
            ("play",f"An official CHL result for Washington and {rival_name}: Capitals {wsh}, {rival_name} {other}."),
            ("analyst","This was recorded as a forfeit, an administrative result, not an on-ice performance. Player highlights would be misleading here."),
            ("play","That's the official result. We'll return with a full breakdown when the next played game is confirmed."),
        ]
    caps,cgoalies=top_players(box,"WSH")
    opposition,ogoalies=top_players(box,rival)
    skaters={"WSH":caps,rival:opposition}
    goalies={"WSH":cgoalies,rival:ogoalies}
    leaders=skaters["WSH"]
    rivals=skaters[rival]
    lead=leaders[0] if leaders and number(leaders[0],"P") else None
    lead_opp=rivals[0] if rivals and number(rivals[0],"P") else None

    openings={
        "score_first":("What a night on the CHL schedule!",
                       "Let's open up that score sheet, because there's more to this one than the final."),
        "player_first":("The numbers are in, and the names behind them are worth talking about!",
                        "Absolutely. This recap has some serious player production to dig into."),
        "matchup":(f"Washington against {rival_name}. Another CHL matchup, another final!",
                   "And the matchup tells an interesting story when you look at the verified player totals."),
        "scoreboard":("The final horn has sounded, and here's your Capitals postgame report!",
                      "The scoreboard gives us the result; the player stats help fill out the picture."),
        "spotlight":("It's time to put the spotlight on the names who filled the box score!",
                     "I've got the numbers, and there are some performances worth highlighting."),
        "season":("Another chapter in the Capitals' CHL campaign is in the books!",
                   "Every final adds to the picture. Let's see what this result actually tells us."),
    }
    opening,reply=openings.get(style,openings["score_first"])
    result=f"{winner} takes a {winner_score} to {loser_score} decision over {loser}, {location}."
    margin=(rng.choice(("A single goal separates these two sides!",
                         "Just one goal between them at the finish!",
                         "A one-goal result on the board!"))
            if diff==1 else f"That's a {diff}-goal difference on the final scoreboard.")
    lines=[
        ("play",f"{opening} {result} {margin}"),
        ("analyst",reply),
    ]

    def spotlight(p,team):
        pts=number(p,"P");goals=number(p,"G");assists=number(p,"A")
        if pts<1:return None
        if goals and assists:
            detail=f"{goals} {'goal' if goals==1 else 'goals'}, {assists} {'assist' if assists==1 else 'assists'} and {pts} total points"
        elif goals:detail=f"{goals} {'goal' if goals==1 else 'goals'} and {pts} {'point' if pts==1 else 'points'}"
        else:detail=f"{assists} {'assist' if assists==1 else 'assists'} for {pts} total {'point' if pts==1 else 'points'}"
        shots=number(p,"SH")
        extra=f" That's {shots} recorded shots as well." if shots>=5 else (f" Add {shots} shots to the line." if shots>0 else "")
        return rng.choice((
            f"{p['name']} delivers {detail}.{extra}",
            f"Look at {p['name']}: {detail}.{extra}",
            f"The verified box score lists {p['name']} with {detail}.{extra}",
        )).strip()

    if lead or lead_opp:
        # The winning side can lead the player story, rather than always
        # beginning with Washington regardless of the game result.
        starring_team="WSH" if won else rival
        starring=lead if won else lead_opp
        other_team=rival if won else "WSH"
        secondary=lead_opp if won else lead
        if starring:
            lines.append(("play",rng.choice((
                f"And the {winner} attack has a player to headline this one!",
                f"Let's start with the name at the top of {winner}'s scoring totals!",
                f"What a statistical performance from the {winner} side!",
            ))))
            lines.append(("analyst",spotlight(starring,starring_team)))
        else:
            lines.append(("play",f"Let's look at the individual numbers for {winner}."))
            lines.append(("analyst","The team result is verified, but a leading scorer wasn't confirmed in the available player report."))
        # Use a second scorer from the winning side when confirmed.
        winner_skaters=skaters[starring_team]
        more=[p for p in winner_skaters if p is not starring and number(p,"P")>0]
        if more:
            p=more[0]
            lines.append(("play",rng.choice((
                "And it wasn't a one-player score sheet. Who else delivered?",
                "The leading scorer had company. What about the other contributors?",
            ))))
            lines.append(("analyst",spotlight(p,starring_team)))
        # Losing team gets recognition without claiming specific game sequences.
        if secondary:
            lines.append(("play",f"Now, {loser} didn't leave the score sheet empty. Who stands out there?"))
            lines.append(("analyst",spotlight(secondary,other_team)))
        more_other=[p for p in skaters[other_team] if p is not secondary and number(p,"P")>0]
        if more_other:
            lines.append(("play",f"And there's another {loser} name worth mentioning, too."))
            lines.append(("analyst",spotlight(more_other[0],other_team)))
        # Complete the supporting cast: third confirmed Capitals contributor
        # earns a mention when available, without inventing an official award.
        if other_team=="WSH":
            additional=[p for p in skaters["WSH"] if p is not secondary and number(p,"P")>0]
        else:
            additional=[p for p in skaters["WSH"] if p is not starring and p not in more and number(p,"P")>0]
        if len(additional)>1:
            p=additional[1]
            lines.append(("play","One more Capitals contributor deserves a mention."))
            lines.append(("analyst",spotlight(p,"WSH")))
    else:
        lines.extend([
            ("play","We have the final score. Do we also have verified individual performances?"),
            ("analyst","Not for this game. The player report is not confirmed, so we won't assign goals, assists, or highlights to anyone."),
        ])

    # Additional verified numbers offer depth while avoiding imagined sequences.
    best_shooter=max(caps,key=lambda p:number(p,"SH")) if caps else None
    if best_shooter and number(best_shooter,"SH")>=4:
        lines.append(("play","Let's talk about Washington's shot production."))
        lines.append(("analyst",f"{best_shooter['name']} registered {number(best_shooter,'SH')} shots. "
                        "That is a verified measure of the Capitals' shooting activity."))

    # Discuss confirmed goaltending on both sides, especially the winning side,
    # without describing the timing or importance of individual saves.
    winning_goalies=goalies["WSH" if won else rival]
    losing_goalies=goalies[rival if won else "WSH"]
    if winning_goalies:
        g=winning_goalies[0];s=g.get("stats",{})
        if "SV" in s:
            lines.append(("play",f"And don't overlook the goaltending in that {winner} win."))
            lines.append(("analyst",f"{g['name']} is credited with {s['SV']} saves in the verified report."
                          +(f" The reported save percentage is {s['SV%']}." if s.get("SV%") else "")))
    if losing_goalies and rng.random()<0.55:
        g=losing_goalies[0];s=g.get("stats",{})
        if "SV" in s:
            lines.append(("play",f"Before we wrap up, what was the goaltending number for {loser}?"))
            lines.append(("analyst",f"{g['name']} finished with {s['SV']} recorded saves."))

    if not box:
        lines.append(("play","So the score is final, but we won't fill the gaps with an imaginary game story."))
        lines.append(("analyst","Exactly. No player performance is verified here, and that distinction matters."))
    lines.append(("play",rng.choice((
        "Put it all together: the score, the standout scorers, and those confirmed goaltending numbers.",
        "The individual stats add real color to that final result.",
        "The final score tells you who won. The box score lets us recognize the contributors.",
    ))))
    # Official stars are only included if the feed provides explicit rankings.
    stars=(box or {}).get("three_stars")
    if isinstance(stars,list) and len(stars)>=3 and all(
        isinstance(item,dict) and item.get("name") and item.get("rank")==i
        for i,item in enumerate(stars[:3],1)
    ):
        names=[item["name"] for item in stars[:3]]
        lines.append(("analyst",f"The verified Three Stars: first, {names[0]}; second, {names[1]}; and third, {names[2]}."))
    else:
        lines.append(("analyst",rng.choice((
            "Those are the confirmed performances we'll remember from this matchup." if box else "We have the verified score; the remaining individual details aren't confirmed.",
            "And that gives you the story of the recorded numbers without guessing about unreported shifts or scoring order.",
            "There is plenty to talk about in those player totals, even without a verified play-by-play timeline.",
        ))))
    if won:
        final=rng.choice((
            "A strong result for the Capitals, and another game in the books. On to the next!",
            "Washington claims the victory. That's your Capitals postgame story!",
            "Put a win beside Washington's name. The next CHL matchup is already another opportunity!",
        ))
    else:
        final=rng.choice((
            f"{rival_name} gets the win, and the Capitals get another chance to answer next game.",
            "Not the ending Washington wanted, but another matchup means another opportunity.",
            f"Credit {rival_name} with the victory. For Washington, the story continues!",
        ))
    lines.append(("play",final))
    return [(role,text.strip()) for role,text in lines if text and text.strip()]

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
