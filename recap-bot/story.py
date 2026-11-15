"""Varied, fact-checked NHL 27 Washington Capitals postgame narration.

Random choices change narrative structure and emphasis, not the source facts.
There are no invented scoring timelines, go-ahead goals or comeback claims.
"""
import random

TEAMS={"ANA":"Anaheim","BUF":"Buffalo","CGY":"Calgary","DET":"Detroit","MIN":"Minnesota","SEA":"Seattle","SJS":"San Jose","UTAH":"Utah","VGK":"Vegas","WSH":"Washington"}
STYLES=("score_first","player_first","matchup","scoreboard","spotlight","season")

def number(p,key):
    try:return int(float(p.get("stats",{}).get(key,0)))
    except (TypeError,ValueError):return 0

def top_players(box,team):
    matches=[p for p in (box or {}).get("players",[]) if p.get("team")==team]
    skaters=[p for p in matches if p.get("pos")!="G"]
    goalies=[p for p in matches if p.get("pos")=="G"]
    skaters.sort(key=lambda p:(number(p,"P"),number(p,"G"),number(p,"SH")),reverse=True)
    goalies.sort(key=lambda p:number(p,"SV"),reverse=True)
    return skaters,goalies

def describe_player(p,rng):
    s=p.get("stats",{})
    name=p.get("name","")
    if p.get("pos")=="G" and "SV" in s:
        return rng.choice((
            f"Between the pipes, {name} is credited with {s['SV']} saves.",
            f"For {name}, the box score records {s['SV']} saves.",
            f"The goaltending numbers show {name} with {s['SV']} stops.",
        ))
    goals=number(p,"G");assists=number(p,"A");points=number(p,"P")
    if points<1:return ""
    if goals and assists:
        return rng.choice((
            f"{name} delivers {goals} goals and {assists} assists, a {points}-point night.",
            f"{name} puts a stamp on the score sheet: {goals} goals, {assists} assists, {points} points in all.",
            f"Look at {name}. {points} points, built on {goals} goals and {assists} assists.",
        ))
    if goals:
        return rng.choice((f"{name} finds the scoresheet for {goals} goals.",
                           f"{name} accounts for {goals} goals in this matchup."))
    return rng.choice((f"{name} supplies {assists} assists and {points} points.",
                       f"{name} finishes with {points} points, all from assists."))

def build_narration(game,box=None,style=None,rng=None):
    rng=rng or random.SystemRandom()
    g=game
    opponent_code=g["home"] if g["away"]=="WSH" else g["away"]
    opponent=TEAMS[opponent_code]
    wsh=g["a"] if g["away"]=="WSH" else g["h"]
    other=g["h"] if g["away"]=="WSH" else g["a"]
    won=wsh>other
    margin=abs(wsh-other)
    if g.get("status")=="Forfeit":
        return ((f"Continental Hockey League official result. Washington and {opponent} have a "
                 f"recorded forfeit: Capitals {wsh}, {opponent} {other}. "
                 "This is an administrative result, not a played-game highlight."), "forfeit")
    if style not in STYLES:style=rng.choice(STYLES)
    caps,cap_goalies=top_players(box,"WSH")
    opp,opp_goalies=top_players(box,opponent_code)
    starring=[p for p in caps if number(p,"P")>=1]
    rival_stars=[p for p in opp if number(p,"P")>=1]
    wsh_star=starring[0] if starring else (cap_goalies[0] if cap_goalies else None)
    rival_star=rival_stars[0] if rival_stars else (opp_goalies[0] if opp_goalies else None)
    result=f"Washington {wsh}, {opponent} {other}."
    score=rng.choice((
        f"The final reads {result}",
        f"Put it on the board. {result}",
        f"The official score: {result}",
        f"At the finish, it is {result}",
    ))
    if won:
        outcome=rng.choice((
            "The Capitals come away with the win.",
            "Washington has its result.",
            "A Capitals victory goes into the league record.",
            "The win belongs to Washington tonight.",
        ))
    else:
        outcome=rng.choice((
            f"{opponent} takes the result, and Washington has questions to answer in the next one.",
            "The Capitals will want a different ending next time.",
            "Washington comes away on the losing side of the scoreboard.",
            "The result stings. The opportunity to respond is still ahead.",
        ))
    gap=(rng.choice((
        "A single goal separates them in the final.",
        "Just one goal. That is the difference on the scoreboard.",
        "This one ends with a one-goal margin.",
    )) if margin==1 else rng.choice((
        f"The margin at the final is {margin} goals.",
        f"A {margin}-goal gap decides the final result.",
        f"The scoreboard ends with {margin} goals between the clubs.",
    )))
    wsh_feature=describe_player(wsh_star,rng) if wsh_star else ""
    rival_feature=describe_player(rival_star,rng) if rival_star else ""
    extra=""
    if len(starring)>1:extra=describe_player(starring[1],rng)
    goalie=""
    if cap_goalies:
        goalie=describe_player(cap_goalies[0],rng)
    opener_by_style={
        "score_first":rng.choice((
            "The numbers are in, and they tell a story. ",
            "A final horn, an official score, and another entry in the CHL season. ",
            "The Capitals have another chapter in the books. ",
        )),
        "player_first":rng.choice((
            "Some games are remembered through the names on the score sheet. ",
            "Start with the players. Their numbers help explain this matchup. ",
            "Tonight's story begins with the performances that made the stat sheet. ",
        )),
        "matchup":rng.choice((
            f"Washington and {opponent}. Two clubs. One result. ",
            f"Another chapter in the Capitals' rivalry with {opponent}. ",
            f"The CHL spotlight falls on Washington against {opponent}. ",
        )),
        "scoreboard":rng.choice((
            "When the final score settles, the picture becomes clear. ",
            "Another night in the CHL comes down to the numbers on the board. ",
            "Every league matchup leaves a result. This is Washington's. ",
        )),
        "spotlight":rng.choice((
            "There is a score, and then there are the performances behind it. ",
            "The scoreboard is only one piece of this game. The individual numbers tell another. ",
            "Beyond the final horn are the players who filled the stat sheet. ",
        )),
        "season":rng.choice((
            "A season is written one result at a time. ",
            "The Capitals' campaign moves forward, one matchup and one final at a time. ",
            "One night never defines an entire season, but every result counts. ",
        )),
    }
    paragraphs=[]
    if style=="player_first" and wsh_feature:
        paragraphs=[opener_by_style[style]+wsh_feature,score+" "+gap,outcome]
    elif style=="spotlight" and wsh_feature:
        paragraphs=[opener_by_style[style]+score,"For the Capitals, the names tell part of the story. "+wsh_feature,gap+" "+outcome]
    elif style=="season":
        paragraphs=[opener_by_style[style]+score+" "+outcome,gap]
    elif style=="matchup":
        paragraphs=[opener_by_style[style]+score+" "+outcome,gap]
    elif style=="scoreboard":
        paragraphs=[opener_by_style[style]+score+" "+gap,outcome]
    else:
        paragraphs=[opener_by_style[style]+score+" "+gap,outcome]
    if wsh_feature and not any(wsh_feature in p for p in paragraphs):
        paragraphs.append(rng.choice(("For Washington, one performance stands out. ","A Capitals name to remember from this one: ","The individual numbers have a voice, too. "))+wsh_feature)
    if extra and rng.random()<0.76:paragraphs.append(extra)
    if rival_feature:
        paragraphs.append(rng.choice((f"On the {opponent} side, ",f"Across the matchup, {opponent} has its own contributor. ",f"And for {opponent}, "))+rival_feature)
    if goalie and (not wsh_star or cap_goalies[0] is not wsh_star):
        paragraphs.append(goalie)
    if not box:
        paragraphs.append("The final score has been verified, but the individual player box score is not yet confirmed for this game.")
    closers_win=(
        "The final result belongs to Washington. Another chapter awaits.",
        "That's the record from this matchup. The Capitals carry the win into what comes next.",
        "The scoreboard is settled. Washington's season story keeps moving.",
        "That is tonight's chapter. A Capitals victory, officially in the books.",
    )
    closers_loss=(
        "The final score cannot be rewritten. The next game offers a new page.",
        "The numbers are final, but this Capitals season is not.",
        "For Washington, the answer will have to come in the next matchup.",
        "A difficult result is part of the journey. The Capitals have another chapter still to write.",
    )
    paragraphs.append(rng.choice(closers_win if won else closers_loss))
    return "\n\n".join(paragraphs),style

def select_style(previous=None,rng=None):
    rng=rng or random.SystemRandom()
    styles=[s for s in STYLES if s!=previous]
    return rng.choice(styles)

def select_voice(rng=None,preferred=None):
    # Use readily available Edge neural US-English announcer-style voices;
    # voice availability is checked naturally by the TTS service at generation.
    rng=rng or random.SystemRandom()
    voices=("en-US-GuyNeural","en-US-RogerNeural","en-US-ChristopherNeural")
    return preferred if preferred else rng.choice(voices)
