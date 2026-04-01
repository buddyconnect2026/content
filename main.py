#!/usr/bin/env python3
"""
main.py — Content Script Generator + Dark Web UI (localhost:8080)

Usage:
  python3 main.py                              # auto trending topic, English
  python3 main.py "Tamilnadu elections"        # specific topic
  python3 main.py "Tamilnadu elections" Tamil  # topic + language
"""

import sys, re, json as _json, random, subprocess, os, signal, socket
from datetime import date, datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote_plus
import webbrowser, threading

# ── Auto-install ───────────────────────────────────────────────────────────────
def _ensure_libs():
    import importlib.util
    for mod, pkg in [("requests","requests"),("bs4","beautifulsoup4"),("lxml","lxml")]:
        if not importlib.util.find_spec(mod):
            print(f"  📦 Installing {pkg}...")
            subprocess.run([sys.executable,"-m","pip","install",pkg],
                           check=True, capture_output=True)

_ensure_libs()
import requests
from bs4 import BeautifulSoup

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent
SCRIPT_JSON = BASE / "today_script.json"
SCRIPT_MD   = BASE / "today_script.md"
HISTORY     = BASE / "content_history.json"

TODAY = date.today().isoformat()

# ── Port helpers ───────────────────────────────────────────────────────────────
def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0

def _kill_port(port):
    """Kill whatever is holding the port (macOS/Linux)."""
    try:
        out = subprocess.check_output(["lsof","-ti",f":{port}"], text=True).strip()
        for pid in out.splitlines():
            os.kill(int(pid), signal.SIGTERM)
        import time; time.sleep(0.4)
    except Exception:
        pass

# ── Category detection ─────────────────────────────────────────────────────────
PERSONAL_CATS = {"tired","work","overthink","phone","routine","sleep","money","focus","social"}

def detect_category(text):
    t = text.lower()
    # Check content-type categories first (higher specificity) before personal/emotional
    for cat, kw in [
        ("tech",      ["ai","artificial intelligence","chatgpt","openai","llm","robot",
                       "tech","technology","software","app","startup","gadget","iphone",
                       "android","google","apple","microsoft","meta","x.com","twitter",
                       "machine learning","data","coding","programming","crypto","bitcoin",
                       "blockchain","ev","electric vehicle","tesla","chip","semiconductor",
                       "automation","algorithm","cloud","saas","api","launch","update"]),
        ("fitness",   ["fitness","workout","exercise","gym","run","running","yoga","diet",
                       "nutrition","weight","fat","muscle","protein","cardio","strength",
                       "calories","steps","marathon","cycling","swim","sport",
                       "body","training","coach","meal prep","sleep hygiene"]),
        ("lifestyle", ["lifestyle","minimalism","morning routine","productivity",
                       "travel","recipe","home decor","fashion","style",
                       "personal finance","self care","wellness","meditation","journaling",
                       "solo travel","work from home","slow living","minimalist"]),
        ("news",      ["war","election","elections","economy","government","crisis",
                       "protest","inflation","politics","world","iran","america",
                       "india","conflict","news","minister","party","vote",
                       "strike","court","arrest","police","attack","flood",
                       "earthquake","disaster","cricket","ipl","match","film","movie",
                       "actor","release","pakistan","china","modi","rahul","bjp","dmk",
                       "aiadmk","vijay","tamilnadu","karnataka","andhra","telangana",
                       "geopolitics","diplomacy","summit","treaty","sanction","military"]),
        ("tired",     ["tired","exhaust","drain","fatigue","no energy","drained"]),
        ("work",      ["procrastin","task","busy","office","job","produc"]),
        ("overthink", ["overthink","anxious","worry","stress","spiral","anxiety"]),
        ("phone",     ["phone","scroll","instagram","social media","screen","tiktok"]),
        ("sleep",     ["sleep","wake","2am","insomnia","bed","nighttime"]),
        ("money",     ["money","spend","broke","save","finance","afford","salary","debt"]),
        ("routine",   ["routine","stuck","same","bored","autopilot","every day"]),
        ("social",    ["friend","relationship","lonely","connect","text back"]),
        ("focus",     ["focus","concentrat","distract","brain fog","attention"]),
    ]:
        if any(k in t for k in kw):
            return cat
    return "news"

def is_personal(cat):
    return cat in PERSONAL_CATS

def cat_to_bank(cat):
    """Map category → bank key used for scene selection."""
    if cat in PERSONAL_CATS:  return "personal"
    if cat == "tech":          return "tech"
    if cat == "fitness":       return "fitness"
    if cat == "lifestyle":     return "lifestyle"
    return "news"

# ── Angle pools ────────────────────────────────────────────────────────────────
PERSONAL_ANGLES = {
    "tired":     ["physically drained","mentally exhausted","emotionally empty",
                  "no motivation at all","tired without any reason"],
    "work":      ["procrastinating everything","doing tasks that feel pointless",
                  "slowly losing interest in everything","too much pressure building up"],
    "overthink": ["late at night when everything is quiet","spiraling about the future",
                  "replaying past mistakes","overthinking what other people think of me"],
    "phone":     ["doom scrolling for hours without realising","comparing my life to others online",
                  "losing hours I can never get back","using it to avoid everything else"],
    "routine":   ["every single day feels exactly the same","running on autopilot",
                  "small changes never sticking","quietly feeling behind everyone else"],
    "sleep":     ["can't fall asleep no matter what I try","waking up at 3am with racing thoughts",
                  "bad sleep affecting everything else","midnight thought spirals"],
    "money":     ["spending on things I don't need","feeling financially behind",
                  "the quiet anxiety around money","wanting to save but always failing"],
    "focus":     ["can't focus for more than ten minutes","starting five things and finishing none",
                  "brain just not cooperating at all","distracted by absolutely everything"],
    "social":    ["slowly disconnecting from people I used to be close to",
                  "friendships quietly fading away","not knowing what to say anymore",
                  "wanting connection but avoiding it at the same time"],
}
NEWS_ANGLES = [
    "how this actually affects everyday life for regular people",
    "what this means for people going forward",
    "the context that helps this make more sense",
    "a simple and clear way of looking at this situation",
    "the part that often gets less attention in coverage",
    "why this matters beyond the immediate headlines",
]

TECH_ANGLES = [
    "whether this is actually as big as people are saying",
    "what this realistically means for someone non-technical",
    "the gap between the hype and what's actually happening",
    "why this is genuinely useful vs just interesting",
    "the honest timeline of when this actually reaches people",
    "what to actually do with this information right now",
]

FIT_ANGLES = [
    "the small daily habit that changes everything",
    "why most people quit at week three and how to not be that person",
    "the difference between effort and consistency",
    "what sustainable fitness actually looks like in real life",
    "the mental shift that matters more than the workout itself",
    "what I wish I had known before I started",
]

LIFE_ANGLES = [
    "the small thing that actually made the difference",
    "what I wish I had known earlier",
    "why this took longer than expected but was worth it",
    "the version nobody posts about honestly",
    "the realistic messy version of making a change",
    "what this looks like when it's actually working",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  PERSONAL SCENE BANKS
# ═══════════════════════════════════════════════════════════════════════════════

P_EN_HOOKS = [
    "I don't know if it's just me… but {topic}. And honestly, I've been sitting with this for a while now and I just needed to say it out loud.",
    "Okay, I'm just going to say it. {topic}. No big intro. No advice at the end. Just me talking about something real.",
    "Can I just be honest for a second? {topic}. And I know a lot of people probably feel the same way but nobody really talks about it like this.",
    "So I've been thinking about {topic} a lot lately. And I realised — I've never actually said this out loud before. So today I'm just going to.",
]

P_EN_SCENES = [
    ("Start", "0:00 – 0:45",
     ["Sit naturally wherever you are. Desk, couch, floor — doesn't matter. Just turn the camera on and start talking like you would to a close friend.",
      "No fancy setup needed. Just you, wherever you are right now. Start mid-thought, like you've already been thinking about this."],
     ["Okay so I'm just going to jump straight into it. {topic}. It's been something that keeps coming up for me lately — like I can't ignore it anymore. And I thought, instead of just sitting with it in my head, let me just turn the camera on and talk. The way I would if a friend called me and asked how I was actually doing. Not the \"I'm fine\" answer. The real one.",
      "So {topic}. I've thought about this probably a hundred times. In the shower, late at night, while I'm just doing nothing. And every time I think about it I'm like — why does nobody actually talk about this honestly? Not the advice version. Not the \"here's how to fix it\" version. Just the real, honest, slightly messy version. So that's what this is."]),

    ("What People Think", "0:45 – 2:00",
     ["Stay relaxed. You're describing a shared experience here. Talk like you're telling a friend something you've both noticed but never said out loud.",
      "Lean in slightly. Like you're getting to the part of the conversation that actually matters."],
     ["And I think the thing about {topic} is — most people experience it but nobody wants to be the first one to admit it. Like there's this unspoken thing where you're supposed to just push through it or pretend it's fine. And so you do. You push through. And then it comes back. And you push through again. And after a while you realise — I've been doing this for months. Maybe longer. And nothing has actually changed. I've just been... managing it. And {angle} — that's the specific version that gets me the most.",
      "Here's what I've noticed. With {topic}, there's usually two reactions. There's the version of it you show people — where you're basically fine, you're handling it, everything is under control. And then there's the version that actually happens at like 11pm when you're lying there and it just hits you. And the gap between those two versions is where I think most of the real stuff lives. For me it's always been — {angle}. That's the quiet version. The one that doesn't make it into the conversation."]),

    ("Real-World Insight", "2:00 – 3:30",
     ["Lean back a little. Slower pace. Talk like you're actually thinking through something in real time — because you are.",
      "This is the honest part of the video. No performance here. Just say what you actually think."],
     ["And the thing I keep coming back to with {topic} is — I used to think it was just a me problem. Like something was specifically wrong with me that I couldn't just get past it like everyone else seemed to. But the more I talk to people — really talk, not just surface-level stuff — the more I realise almost everyone is dealing with some version of this. The specific version for me is {angle}. And I think the reason it sticks around is because I keep treating it like a problem to solve instead of something to actually sit with and understand. And those are two completely different things.",
      "What I've started to notice is — {topic} doesn't just show up on its own. It shows up when something else is already off. When I'm not sleeping properly. When I've been avoiding something. When I've been performing \"fine\" for too long without actually stopping and checking in with myself. And the {angle} piece of it — that's usually the first sign that I've been ignoring something. It's not the main thing. It's the thing pointing to the main thing. And I keep treating the symptom instead of actually looking at what's underneath it."]),

    ("Personal Thought", "3:30 – 4:30",
     ["A quiet moment. Not a big revelation — just something small you've started to figure out. Let it land naturally.",
      "Direct and honest. Like you're telling someone something you've only recently realised."],
     ["And here's the thing I've slowly started to accept about {topic} — I don't need to fix it every single time it shows up. That was my whole approach for a long time. It shows up, I go into problem-solving mode, I try to push through it, I feel temporarily better, and then it comes back. And I think what I was missing was just — acknowledging it. Like, okay. This is here right now. I'm not going to pretend it isn't. I'm not going to spiral about it either. It's just here. And somehow that small thing — just naming it instead of reacting to it — that actually helps more than anything else I've tried.",
      "I think the most useful thing I've done with {topic} is just start being honest about it. Not in a public, dramatic way. Just in a quiet, internal way. Like instead of waking up and immediately going into autopilot and not acknowledging how I actually feel — just pausing for a second and going, yeah, this is what's happening right now. This is real. And it doesn't mean something is permanently wrong. It just means today is one of those days. And that's okay. I can still function. I can still do things. I just don't have to pretend I'm not carrying it."]),

    ("Small Moment", "4:30 – 5:00",
     ["Pause here. Look away briefly. Let the silence sit for a second. Low energy is fine — it actually feels more real.",
      "Still and quiet. Like the end of a real conversation where both people just sit for a second before someone speaks again."],
     ["…I don't have a clean ending for this. I don't have the answer. I'm still in the middle of it honestly. But I think that's kind of the point — that it's okay to be in the middle of something without having it figured out. And just saying that out loud, to a camera, to you, whoever's watching — that already feels like something.",
      "I just wanted to say this because I think a lot of people are dealing with {topic} quietly. Without saying anything. Without even fully acknowledging it to themselves. And sometimes just hearing someone else say it out loud — not with advice, not with a solution, just honestly — makes it feel a little less heavy. At least that's what it does for me."]),

    ("Ending", "5:00 – 5:30",
     ["Look back at the camera. Simple. Like ending a voice note to someone you trust.",
      "Warm and honest close. No pressure. Like saying goodbye after a real conversation."],
     ["Anyway. If {topic} is something you've been dealing with too — I just want you to know you're not alone in it. Not even close. And you don't have to have it figured out. You just have to keep going, one day at a time. That's enough. If this resonated with you, drop a comment below — I genuinely read every single one. Subscribe if you want more honest conversations like this. I'll see you in the next one.",
      "That's all I had for today. No big takeaway. No life advice. Just a real conversation about something real. If it helped even a little — that's everything. Hit like if it did, it actually helps more people find this. And if you've got something to add or a different experience — leave it in the comments. Take care of yourself. Talk soon."]),
]

P_EN_LINES = [
    "I don't know if it's just me… but {topic} hits different lately.",
    "Nobody really talks about {topic} honestly. And that's exactly the problem.",
    "I kept waiting for it to pass. It didn't. And I think that's actually important to say.",
    "There's something about {angle} that nobody prepares you for.",
    "Some days are just harder than others. That's not weakness. That's just real.",
    "It's okay to not be okay with something. You don't have to perform fine.",
    "Just saying it out loud — even to a camera — already makes it feel smaller.",
    "If you've been carrying {topic} quietly — you don't have to. You're not alone.",
    "Maybe the expectation that we should be fine all the time is the actual problem.",
    "Not everything needs a solution. Sometimes it just needs to be acknowledged.",
    "The {angle} part is what gets me every single time. Nobody talks about that part.",
    "I thought I was the only one dealing with this. Turns out I wasn't even close.",
]

P_TA_HOOKS = [
    "சரி நான் directly சொல்லிட்டு போறேன். {topic}. இது என் mind-ல நிறைய நாளா இருந்துக்கிட்டே இருக்கு. இதை out loud சொல்லணும்னு feel ஆச்சு.",
    "Okay so. {topic}. இது நான் மட்டுமே feel பண்றேன்னு நினைச்சேன் நீண்ட நாளா. ஆனா இல்ல. So let me just talk about this honestly.",
    "நான் {topic} பத்தி நிறைய யோசிச்சிருக்கேன். And honestly — இதை யாரிடமாவது சொல்லணும்னு இருந்தேன். Camera-வ turn on பண்ணி பேசலாம்னு decide பண்ணினேன்.",
]

P_TA_SCENES = [
    ("Start", "0:00 – 0:45",
     ["Casually உட்காருங்க. Couch-லயோ desk-லயோ — எங்க comfortable-ஆ இருக்கீங்களோ அங்க. Friend-கிட்ட பேசுவது மாதிரி ஆரம்பிங்க.",
      "Phone stand-ல வச்சுட்டு natural-ஆ start பண்ணுங்க. No intro needed — just start talking."],
     ["Okay so நான் directly jump பண்றேன். {topic}. இது என் கூட நிறைய நாளா இருக்கு — ignore பண்ண முடியாத மாதிரி. நான் இதை யாரோட கூடயாவது பேசணும்னு feel பண்ணினேன். Camera-வ on பண்ணி, பேசலாம்னு decide பண்ணினேன். Advice இல்ல, solution இல்ல — just honest-ஆ பேசுவோம்.",
      "So {topic}. இதை நான் probably நூறு தடவை யோசிச்சிருப்பேன். Late night-ல, shower-ல, just ஒண்ணும் பண்ணாம இருக்கும்போது. And every time நான் think பண்றேன் — ஏன் யாரும் இதை honestly பேசமாட்டாங்க? Fix பண்றது மாதிரி பேசல. Just real-ஆ, honest-ஆ. So that's what this is going to be."]),

    ("Situation", "0:45 – 2:00",
     ["Relax ஆக இருங்க. Shared experience-ஐ describe பண்றீங்க. Friend-கிட்ட out loud சொல்வது மாதிரி.",
      "Lean in slightly. The real part of the conversation starts here."],
     ["{topic} பத்தி என்ன நினைக்கிறேன்னா — most people இதை experience பண்றாங்க ஆனா யாரும் first-ஆ admit பண்ண ready இல்ல. Like ஒரு unspoken rule இருக்கு — push through பண்ணணும், fine-ஆ இருக்கணும்னு. So நீங்க அப்படியே பண்றீங்க. Push through பண்றீங்க. And then it comes back. And again push through. சில மாசம் கழிச்சு realise ஆகுது — நான் இதை just manage பண்ணிட்டே இருக்கேன், actually deal பண்ணவே இல்ல. {angle} — specifically அந்த part தான் என்னை அதிகமா affect பண்றது.",
      "{topic} பத்தி நான் notice பண்றது என்னன்னா — two versions இருக்கு. People-கிட்ட காட்டுற version — basically fine, handle பண்றோம், under control. And then 11pm-ல lie down பண்ணும்போது actually feel ஆகுறது — அது different. And that gap between those two versions — அந்த space-ல தான் real stuff இருக்கு. என்னோட case-ல always — {angle}. Quiet version அது. யாரோட கூடயும் share பண்ண முடியாத part."]),

    ("Real Thought", "2:00 – 3:30",
     ["Lean back. Slower. Like you're thinking out loud in real time.",
      "Honest part. No performance. Just say what you actually think."],
     ["{topic} பத்தி நான் keep coming back பண்றது என்னன்னா — நான் முன்னாடி நினைச்சேன் இது just a me problem-னு. என்னால மட்டும் தான் get past பண்ண முடியல, others எல்லாரும் easily handle பண்றாங்கன்னு. ஆனா நான் people-கிட்ட really பேசும்போது — surface level இல்ல, actually பேசும்போது — almost everyone some version of this deal பண்றாங்க-ன்னு தெரியுது. என்னோட specific version — {angle}. And I think it stays because நான் இதை solve பண்ண try பண்றேன் instead of actually sitting with it. Those are two different things.",
      "{topic} alone-ஆ வராது-ன்னு notice பண்ணிருக்கேன். Something else already off-ஆ இருக்கும்போது வருது. Properly தூக்கம் வராதபோது, ஏதோ avoid பண்ணும்போது, நீண்ட நாளா 'fine' perform பண்ணிட்டு actually check-in பண்ணாதபோது. And {angle} part — அது usually first sign. அது main issue இல்ல. Main issue-ஐ point பண்ற விஷயம். ஆனா நான் symptom-ஐ treat பண்றேன் — underneath-ல என்ன இருக்குன்னு பாக்கல."]),

    ("Personal Realization", "3:30 – 4:30",
     ["Quiet moment. Small realisation — not a big epiphany. Let it land.",
      "Direct and honest. Something you've recently started figuring out."],
     ["{topic} பத்தி நான் slowly accept பண்ண ஆரம்பிச்சது என்னன்னா — every time வரும்போது fix பண்ண வேண்டாம். அதுதான் என்னோட approach-ஆ இருந்தது — வருது, problem-solving mode போறேன், push through பண்றேன், temporarily better feel ஆகுது, திரும்ப வருது. நான் miss பண்றது — just acknowledge பண்றது. Okay. இது இப்போ இருக்கு. Pretend பண்ணல, spiral ஆகலயும். Just — இருக்கு. And that small thing — name பண்றது instead of reacting — அது உண்மையிலேயே help பண்றது.",
      "{topic} பத்தி நான் பண்ண ஆரம்பிச்சது என்னன்னா — honest-ஆ இருக்கிறது. Dramatic-ஆ இல்ல. Just quietly, internally. Autopilot போகாம, actually feel பண்றதை acknowledge பண்றது. 'Yeah, இது நடக்குது right now. இது real.' Permanent-ஆ wrong இல்ல. Just today இப்படி இருக்கு. That's okay. நான் still function பண்ண முடியும். Carry பண்றது pretend பண்ண வேண்டாம்."]),

    ("Quiet Moment", "4:30 – 5:00",
     ["Pause. Look away. Silence is good here. Low energy feels more real.",
      "Still and quiet. End of a real conversation where both people just sit for a moment."],
     ["…Clean ending என்கிட்ட இல்ல. Answer-உம் இல்ல. Honestly நான் still middle-ல இருக்கேன். ஆனா அதுதான் point — answer இல்லாம middle-ல இருக்கிறது okay. And just இதை out loud சொல்றது — camera-கிட்ட, உங்ககிட்ட, யார் பாக்குறாங்களோ — that already feels like something.",
      "நிறைய people {topic}-ஐ quietly deal பண்றாங்க. Acknowledge பண்ணாம, யாரிடமும் சொல்லாம. And sometimes — யாரோ honestly சொல்றது கேக்கும்போது, advice இல்லாம, solution இல்லாம — அது கொஞ்சம் lighter feel ஆகுது. At least என்னோட case-ல அப்படி."]),

    ("Ending", "5:00 – 5:30",
     ["Camera-கிட்ட பாருங்க. Simple-ஆ, warm-ஆ close பண்ணுங்க.",
      "Like ending a voice note to someone you trust."],
     ["Anyway. {topic} உங்களுக்கும் இருந்தா — you're not alone. Not even close. Everything figured out பண்ண வேண்டாம். Just keep going, one day at a time. நீங்களும் இது மாதிரி feel பண்றீங்களா — comment-ல சொல்லுங்க. நான் எல்லாத்தையும் படிக்கிறேன். இது மாதிரி honest conversations-க்கு subscribe பண்ணுங்க. See you in the next one.",
      "இன்னிக்கு இது தான். Big takeaway இல்ல. Life advice இல்ல. Just real conversation about something real. Helped even a little-ஆ இருந்தா — like பண்ணுங்க, அது more people-க்கு reach ஆக help பண்றது. உங்க experience different-ஆ இருந்தா comments-ல சொல்லுங்க. Take care."]),
]

P_TA_LINES = [
    "நான் மட்டும் தான் feel பண்றேன்னு நினைச்சேன். Turns out — இல்ல.",
    "{topic} பத்தி யாரும் honestly பேசமாட்டாங்க. And that silence is the actual problem.",
    "I kept waiting for it to pass. It didn't. And I think that's important to say.",
    "{angle} — that specific part, nobody prepares you for it.",
    "Some days are harder. That's not weakness — that's just being human.",
    "Fine-ஆ perform பண்ண வேண்டாம். It's okay to not be okay.",
    "Out loud சொல்றதே — even to a camera — already makes it feel smaller.",
    "{topic} quietly carry பண்றீங்களா? You don't have to. You're not alone.",
    "Expectation that we should always be okay — maybe that's the real problem.",
    "Every solution-க்கு முன்னாடி — just acknowledge பண்ணாலே போதும்.",
    "{angle} part-ஐ யாரும் பேசமாட்டாங்க. That's the part I keep thinking about.",
    "நான் alone-ஆ இருக்கேன்னு நினைச்சேன். நான் அதுவும் இல்ல.",
]

P_TE_HOOKS = [
    "సరే నేను directly చెప్పేస్తాను. {topic}. ఇది చాలా రోజులు నా mind లో ఉంది. ఇది out loud చెప్పాలని feel అయింది.",
    "Okay so. {topic}. ఇది నేను మాత్రమే feel అవుతున్నానని చాలా కాలం అనుకున్నాను. కానీ కాదు. So let me just talk about this honestly.",
    "నేను {topic} గురించి చాలా ఆలోచించాను. And honestly — దీన్ని ఎవరికైనా చెప్పాలని ఉంది. Camera on చేసి మాట్లాడదాం అని decide చేశాను.",
]

P_TE_SCENES = [
    ("Start", "0:00 – 0:45",
     ["Casually కూర్చోండి. Couch లో, desk దగ్గర — comfortable గా ఎక్కడైనా. Friend తో మాట్లాడినట్టు start చేయండి.",
      "Phone stand పెట్టి natural గా start చేయండి. No intro needed — just start talking."],
     ["Okay so నేను directly jump చేస్తాను. {topic}. ఇది నా తో చాలా రోజులు ఉంది — ignore చేయలేనట్టు. నేను దీన్ని ఎవరితోనైనా మాట్లాడాలని feel అయింది. Camera on చేసి, మాట్లాడదాం అని decide చేశాను. Advice లేదు, solution లేదు — just honest గా మాట్లాడదాం.",
      "So {topic}. నేను దీన్ని probably వంద సార్లు ఆలోచించి ఉంటాను. Late night లో, shower లో, just ఏమీ చేయకుండా ఉన్నప్పుడు. And every time నేను think చేస్తాను — ఎందుకు ఎవరూ దీన్ని honestly మాట్లాడరు? Fix చేయడం కాదు. Just real గా, honest గా. So that's what this is going to be."]),

    ("Situation", "0:45 – 2:00",
     ["Relax గా ఉండండి. Shared experience describe చేస్తున్నారు. Friend కి out loud చెప్తున్నట్టు.",
      "Lean in slightly. The real part of the conversation starts here."],
     ["{topic} గురించి నా thought ఏమిటంటే — most people దీన్ని experience చేస్తారు కానీ ఎవరూ first గా admit చేయడానికి ready గా ఉండరు. Like ఒక unspoken rule ఉంది — push through చేయాలి, fine గా ఉండాలి అని. So మీరు అలా చేస్తారు. Push through చేస్తారు. And then it comes back. And again. కొన్ని నెలల తరువాత realise అవుతుంది — నేను దీన్ని just manage చేస్తున్నాను, actually deal చేయట్లేదు. {angle} — specifically ఆ part నన్ను చాలా affect చేస్తుంది.",
      "{topic} గురించి నేను notice చేసేది ఏమిటంటే — two versions ఉంటాయి. People కి చూపించే version — basically fine, handle చేస్తున్నాం, under control. And then రాత్రి 11 కి lie down చేసినప్పుడు actually feel అయ్యేది — అది different. And that gap between those two versions — ఆ space లో real stuff ఉంటుంది. నా case లో always — {angle}. Quiet version. ఎవరికీ share చేయలేని part."]),

    ("Real Thought", "2:00 – 3:30",
     ["Lean back. Slower. Like you're thinking out loud in real time.",
      "Honest part. No performance. Just say what you actually think."],
     ["{topic} గురించి నేను keep coming back చేసేది ఏమిటంటే — ముందు నేను అనుకున్నాను ఇది just నా problem అని. నాకు మాత్రమే get past చేయలేకపోతున్నాను, others అందరూ easily handle చేస్తున్నారు అని. కానీ నేను people తో really మాట్లాడినప్పుడు — surface level కాదు, actually మాట్లాడినప్పుడు — almost everyone ఇదే deal చేస్తున్నారు అని తెలిసింది. నా specific version — {angle}. And I think it stays because నేను దీన్ని solve చేయడానికి try చేస్తాను instead of actually sitting with it. Those are two different things.",
      "{topic} alone గా రాదు అని notice చేశాను. Something else already off గా ఉన్నప్పుడు వస్తుంది. Properly sleep రాకపోయినప్పుడు, ఏదో avoid చేస్తున్నప్పుడు, చాలా కాలంగా 'fine' perform చేస్తూ actually check-in చేయనప్పుడు. And {angle} part — అది usually first sign. అది main issue కాదు. Main issue ని point చేసే విషయం. కానీ నేను symptom treat చేస్తాను — underneath లో ఏమి ఉందో చూడట్లేదు."]),

    ("Personal Realization", "3:30 – 4:30",
     ["Quiet moment. Small realisation — not a big epiphany. Let it land.",
      "Direct and honest. Something you've recently started figuring out."],
     ["{topic} గురించి నేను slowly accept చేయడం start చేసింది ఏమిటంటే — every time వచ్చినప్పుడు fix చేయక్కర్లేదు. అది నా approach గా ఉండేది — వస్తుంది, problem-solving mode లోకి వెళ్తాను, push through చేస్తాను, temporarily better feel అవుతుంది, తిరిగి వస్తుంది. నేను miss చేసేది — just acknowledge చేయడం. Okay. ఇది ఇప్పుడు ఉంది. Pretend చేయడం లేదు, spiral అవడం లేదు. Just — ఉంది. And that small thing — name చేయడం instead of reacting — అది నిజంగా help చేస్తుంది.",
      "{topic} గురించి నేను start చేసింది ఏమిటంటే — honest గా ఉండటం. Dramatic గా కాదు. Just quietly, internally. Autopilot లో వెళ్ళకుండా, actually feel అవుతున్నది acknowledge చేయడం. 'Yeah, ఇది ఇప్పుడు జరుగుతోంది. ఇది real.' Permanent గా wrong కాదు. Just today ఇలా ఉంది. That's okay. నేను still function చేయగలను. Carry చేస్తున్నది pretend చేయక్కర్లేదు."]),

    ("Quiet Moment", "4:30 – 5:00",
     ["Pause. Look away. Silence is good here.",
      "Still and quiet."],
     ["…Clean ending నా దగ్గర లేదు. Answer కూడా లేదు. Honestly నేను still middle లో ఉన్నాను. కానీ అదే point — answer లేకుండా middle లో ఉండటం okay. And just ఇది out loud చెప్పడం — camera కి, మీకు — that already feels like something.",
      "చాలా మంది {topic} ని quietly deal చేస్తున్నారు. Acknowledge చేయకుండా, ఎవరికీ చెప్పకుండా. And sometimes — ఎవరైనా honestly చెప్పినప్పుడు విన్నప్పుడు, advice లేకుండా — అది కొంచెం lighter feel అవుతుంది."]),

    ("Ending", "5:00 – 5:30",
     ["Camera వైపు చూడండి. Simple గా, warmly close చేయండి.",
      "Like ending a voice note to someone you trust."],
     ["Anyway. {topic} మీకూ ఉంటే — you're not alone. Not even close. Everything figured out చేయక్కర్లేదు. Just keep going, one day at a time. మీకూ ఇలా అనిపిస్తోందా — comment లో చెప్పండి. నేను అన్నీ చదువుతాను. ఇలాంటి honest conversations కోసం subscribe చేయండి. See you in the next one.",
      "ఇంతే today కి. Big takeaway లేదు. Life advice లేదు. Just real conversation about something real. Helped even a little అయినా — like చేయండి, అది more people కి reach అవడానికి help చేస్తుంది. మీ experience different గా ఉంటే comments లో చెప్పండి. Take care."]),
]

P_TE_LINES = [
    "నేను మాత్రమే feel అవుతున్నానని అనుకున్నాను. Turns out — కాదు.",
    "{topic} గురించి ఎవరూ honestly మాట్లాడరు. And that silence is the actual problem.",
    "I kept waiting for it to pass. It didn't. And I think that matters.",
    "{angle} — ఆ specific part కి ఎవరూ prepare చేయరు.",
    "కొన్ని రోజులు harder గా ఉంటాయి. అది weakness కాదు — అది human being.",
    "Fine perform చేయక్కర్లేదు. It's okay to not be okay.",
    "Out loud చెప్పడమే — even to a camera — makes it feel smaller.",
    "{topic} quietly carry చేస్తున్నారా? You don't have to. You're not alone.",
    "Always okay గా ఉండాలన్న expectation — maybe that's the real problem.",
    "Solution కంటే ముందు — just acknowledge చేయడమే చాలు.",
    "{angle} part గురించి ఎవరూ మాట్లాడరు. That's what I keep thinking about.",
    "నేను alone అని అనుకున్నాను. నేను అది కూడా కాదు.",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  NEWS / EVENTS SCENE BANKS
# ═══════════════════════════════════════════════════════════════════════════════

N_EN_HOOKS = [
    "So {topic}. I've been reading about this and honestly — there's a lot being said but very little that actually makes sense to a normal person. So let me just give you my plain, honest take on it.",
    "Okay so {topic} — it's everywhere right now. And I get that. But I keep feeling like the conversation happening in the media and the conversation happening in real life are two completely different things. So let me just bridge that gap a little.",
    "{topic}. I know you've seen a lot of takes on this already. Expert opinions, political commentary, hot takes — all of it. But what about just a regular person's view? Someone who's not trying to make a point or win an argument? That's what this is.",
    "I was just going through my news feed today — {TODAY} — and {topic} keeps coming up everywhere. And I thought, you know what, let me just talk about this the way I would to a friend. No spin. No agenda. Just what I actually think.",
]

N_EN_SCENES = [
    ("Start", "0:00 – 0:45",
     ["Talk directly to camera. Casual and relaxed. Like you just sat down to catch your friend up on something.",
      "No intro, no music, no title card. Just start talking, mid-thought, like the conversation has already been going."],
     ["So {topic}. I've been following this for a few days now and honestly, the more I read, the more I feel like most of the coverage is missing the thing that actually matters to normal people. Not the political angle. Not the expert analysis. Just — what does this actually mean for people going about their daily lives? And I thought, let me just sit down and talk about this the way I would to anyone who asked me. No big claims. Just my honest read on it.",
      "Okay so I want to talk about {topic}. And I want to do it the way nobody seems to be doing it right now — simply. Because I've been scrolling through takes and news pieces and none of it is actually answering the questions I have. The basic ones. The ones a normal person would ask. So let me try and do that. I'm not an expert. I'm just someone who's been paying attention. And sometimes that's actually enough."]),

    ("What People Think", "0:45 – 2:00",
     ["Lean in slightly. Like you're sharing what you've been hearing from real people around you.",
      "Conversational. Like you're catching a friend up on something that happened and telling them what everyone's been saying about it."],
     ["So the thing with {topic} is — most people in the news are having one conversation, and most normal people are having a completely different one. In the news it's all about {news0}. And that's a real thing, that matters, I'm not dismissing it. But when I talk to people around me — friends, family, people on the street — what they're actually worried about is something different. They're worried about how this lands in their daily life. In their pocket. In their neighbourhood. In their kid's school. And those two conversations are barely overlapping right now.",
      "Here's what I keep noticing about {topic}. There's the loud version of the story — which is {news0}. Big headlines, strong opinions, lots of noise. And then there's the quiet version. The version where someone's just sitting at home wondering what this actually means for them personally. And I think it's the quiet version that nobody is really speaking to. That's the conversation I want to have."]),

    ("Real-World Insight", "2:00 – 3:30",
     ["Slower pace. Like you're thinking it through as you talk — because you are. Let it breathe.",
      "More honest here. Share what you actually found when you looked past the headlines."],
     ["Because here's the thing that I think is actually important about {topic} — {news1}. And I feel like most people scroll past this part. This is the bit that's buried in paragraph seven of every article, after all the dramatic stuff at the top. But this is the part that actually changes things on the ground. For regular people. Not the political fallout. Not the who-said-what. This specific thing. And the reason I keep coming back to it is that it's the part with actual consequences for how people live. And that should be the story. But it's not getting the space it deserves.",
      "What I've been trying to understand about {topic} is — {news1}. And when you put that next to {news0}, which is what everyone's talking about, you start to see a picture that's actually more complicated and more interesting than the simple takes suggest. The surface story is one thing. But when you sit with the details — the actual data, the actual timeline, what actually happened versus what people are saying happened — it's more nuanced. And nuance is boring for headlines. But it's where the truth usually lives."]),

    ("Personal Take", "3:30 – 4:30",
     ["Direct and honest. Your actual opinion. Not what you think you should say — what you actually think.",
      "Talk like you're telling a friend what you genuinely believe, after having thought about it properly."],
     ["And my honest take on {topic} — and I want to be clear this is just my read, I could be wrong — is that this matters way more to normal people than the coverage suggests. Like, the stuff that actually affects how people pay their bills, feed their family, feel safe in their city — that's the story. And right now that story is getting drowned out by the louder, more dramatic version of events. And I think that's a real problem. Because when people can't connect the news to their actual life, they stop paying attention. And then they stop participating. And that's when things really go sideways.",
      "Here's what I genuinely think about {topic}. The people most affected by this are probably not the ones with the microphone right now. They're the people who are going to quietly deal with whatever comes out of this — without anyone asking them how it actually landed. And I think one of the most useful things anyone can do is just pay attention to that. Not the version that sounds good on camera. The version that's real. And right now — {news0} — that's real. That affects people. And it deserves more honest attention than it's getting."]),

    ("Small Moment", "4:30 – 5:00",
     ["Pause. Let a quiet realisation land. Low energy is fine here — it actually feels more real.",
      "Simple and honest. Like you're thinking out loud at the end of the conversation."],
     ["I'll be honest — I don't know exactly how {topic} is going to play out. Nobody does, really, even if they act like they do. But I do know that the gap between what's being covered and what's actually happening in people's lives is real. And I think the most honest thing any of us can do right now is just — stay curious. Keep asking the simple questions. Not just absorb whatever the loudest voice is saying.",
      "I just keep thinking — with {topic} — there's so much noise. So many hot takes. So many people confidently explaining things. And somewhere underneath all of that is just a situation that affects real people in real ways. And I think it's worth pausing on that. Not as a political statement. Just as a human one."]),

    ("Ending", "5:00 – 5:30",
     ["Look at the camera. Warm and simple. No dramatic close.",
      "Like finishing a conversation with a friend. Easy and natural."],
     ["Anyway. That's my honest take on {topic}. Not an expert opinion. Just a regular person trying to make sense of something. If you see it differently — leave a comment, I genuinely want to read your perspective. If this kind of straightforward coverage is useful to you, subscribe so you don't miss the next one. See you then.",
      "That's all I had on {topic} today. Simple take. Real perspective. If it helped you think about it a bit differently — that's everything. Hit like if it did, it helps more people find this. And drop a comment with what you think is being missed in the coverage. Take care."]),
]

N_EN_LINES = [
    "Everyone's talking about {topic}. But nobody's just explaining it simply — and that matters.",
    "The stuff that affects real people's lives is always in paragraph seven. Never the headline.",
    "I'm not an expert. I'm just a normal person who's been paying attention. And sometimes that's enough.",
    "{news0} — and that's the part I think is being underreported.",
    "The political version of this story and the human version are two completely different things.",
    "I don't have all the answers. But I have questions — and I think that actually counts for something.",
    "With {topic}, the real story is usually in the quiet details, not the loud headlines.",
    "People are reacting. But not everyone is actually understanding. And that gap matters.",
    "I just wanted to talk about this simply. Because simple is what's missing.",
    "The people most affected by {topic} are probably the ones least likely to be on camera talking about it.",
    "{news1} — that's the part that actually changes things for normal people.",
    "Stay curious. Keep asking the basic questions. Don't just absorb the loudest take.",
]

N_TA_HOOKS = [
    "So {topic} — இதை பத்தி பேசணும்னு நிறைய நாளா இருந்தேன். News-ல நிறைய இருக்கு. ஆனா normal person-ஆ simply யாரும் explain பண்றதில்ல. So let me try to do that.",
    "Okay so {topic}. இது everywhere இருக்கு right now. ஆனா media-ல நடக்குற conversation-உம் real life-ல நடக்குற conversation-உம் completely different-ஆ இருக்கு. That gap-ஐ bridge பண்ண try பண்றேன்.",
    "{topic} பத்தி நிறைய takes வருது. Expert opinions, political commentary — எல்லாமே. ஆனா just a regular person-ஓட view? Agenda இல்லாம, argument win பண்ண try பண்ணாம? That's what this is.",
    "இன்னிக்கு — {TODAY} — news feed திறந்தேன். {topic} everywhere. நான் நினைச்சேன் — friend-கிட்ட பேசுவது மாதிரி இதை talk பண்ணலாம். No spin. No agenda. என்னோட actual thoughts மட்டும்.",
]

N_TA_SCENES = [
    ("Start", "0:00 – 0:45",
     ["Camera-கிட்ட directly பேசுங்க. Casual-ஆ, relaxed-ஆ. Friend-கிட்ட catch up பண்றது மாதிரி.",
      "No intro. Just start mid-thought. Conversation already நடக்குது மாதிரி."],
     ["So {topic}. நான் இதை சில நாளா follow பண்றேன். And honestly, நான் பாக்குற coverage எல்லாமே normal people-க்கு actually என்ன matter பண்றதுன்னு miss பண்றது மாதிரி feel ஆகுது. Political angle இல்ல. Expert analysis இல்ல. Just — இது நம்ம daily life-ஐ actually எப்படி affect பண்றதுன்னு. நான் யாராவது கேட்டா பேசுவது மாதிரி பேசலாம்னு உட்கார்ந்தேன். Big claims இல்ல. Just என்னோட honest read.",
      "Okay so {topic} பத்தி பேசணும். And I want to do it the way nobody seems to be doing it right now — simply. நான் scroll பண்ணி நிறைய takes படிச்சேன், news pieces படிச்சேன் — none of it is answering the questions I actually have. Basic questions. Normal person கேக்குற questions. So let me try. Expert இல்ல நான். Just someone who's been paying attention. And sometimes that's actually enough."]),

    ("What People Think", "0:45 – 2:00",
     ["Lean in slightly. Real people-கிட்ட கேட்டதை share பண்றது மாதிரி.",
      "Conversational. Friend-கிட்ட நடந்தது சொல்வது மாதிரி."],
     ["{topic} பத்தி issue என்னன்னா — news-ல பேசுற conversation-உம் normal people பேசுற conversation-உம் match ஆகல. News-ல எல்லாமே {news0} பத்தி. That's real, that matters — dismiss பண்றது இல்ல. ஆனா நான் என் கூட இருக்குறவங்க கிட்ட பேசும்போது — friends, family, அன்னிக்கு meet ஆன people — அவங்க actually worry பண்றது different. அவங்க daily life-ல எப்படி land ஆகுதுன்னு worry பண்றாங்க. Pocket-ல, neighbourhood-ல, kids-ஓட school-ல. Those two conversations barely overlap பண்றது இல்ல right now.",
      "{topic} பத்தி நான் keep noticing பண்றது என்னன்னா — loud version of the story இருக்கு — {news0}. Big headlines, strong opinions, lots of noise. And then quiet version இருக்கு. யாரோ வீட்ல உட்கார்ந்து 'இது என்னோட life-ஐ actually எப்படி affect பண்றது?' அப்படி wonder பண்றது. And nobody is really speaking to that quiet version. அந்த conversation தான் நான் வேணும்னு நினைக்குறேன்."]),

    ("Real Thought", "2:00 – 3:30",
     ["Slower. Like you're thinking through it in real time.",
      "Honest. Share what you actually found past the headlines."],
     ["{topic} பத்தி actually important-ஆ நான் நினைக்குறது — {news1}. இந்த part-ஐ most people scroll பண்ணிட்டு போவாங்க. Every article-ல paragraph seven-ல buried-ஆ இருக்கு, dramatic stuff எல்லாம் முன்னாடி வச்சதுக்கு பிறகு. ஆனா இந்த part தான் ground level-ல things-ஐ change பண்றது. Regular people-க்கு. Political fallout இல்ல. Who-said-what இல்ல. This specific thing. And அதுக்கு space கிடைக்கல. That should be the story. But it's not.",
      "{topic} பத்தி நான் understand பண்ண try பண்றது — {news1}. இதை {news0}-கூட put பண்ணும்போது — everybody பேசுற part — actually more complicated picture தெரியுது. Surface story ஒரு மாதிரி. ஆனா details-ல உட்கார்ந்து பாக்கும்போது — actual data, actual timeline, என்ன நடந்தது versus என்ன சொல்றாங்க — அது more nuanced. Nuance boring for headlines. But அதுல தான் truth இருக்கு usually."]),

    ("Personal Take", "3:30 – 4:30",
     ["Direct and honest. Your actual opinion.",
      "Friend-கிட்ட properly யோசிச்சதுக்கு பிறகு சொல்வது மாதிரி."],
     ["என்னோட honest take — {topic} பத்தி — coverage suggest பண்றதை விட normal people-ஐ way more affect பண்றது. Bills pay பண்றது, family feed பண்றது, city-ல safe feel ஆவது — அதுதான் story. And right now அந்த story-ஐ louder, more dramatic version of events drown out பண்றது. That's a real problem. People news-ஐ அவங்க actual life-கூட connect பண்ண முடியல-ன்னா — they stop paying attention. Then they stop participating. And that's when things really go sideways.",
      "என்னோட genuine take — {topic} பத்தி. Most affected people probably microphone-கிட்ட இல்லாதவங்க right now. Quietly deal பண்ணுவாங்க — யாரும் actually எப்படி land ஆச்சுன்னு கேக்காம. And I think அதை notice பண்றதுதான் most useful thing. Camera-ல good-ஆ sound ஆகுற version இல்ல. Real-ஆ இருக்குற version. And right now — {news0} — that's real. That affects people. And it deserves more honest attention."]),

    ("Small Moment", "4:30 – 5:00",
     ["Pause. Quiet realisation.",
      "Simple and honest."],
     ["Honestly — {topic} எப்படி play out ஆகும்னு தெரியல. யாருக்கும் தெரியல, really, even if they act like they do. ஆனா coverage-ஐயும் people's actual lives-ஐயும் பிரிக்குற gap — அது real. And most honest thing நாம் பண்ண முடிறது — stay curious. Keep asking simple questions. Loudest voice சொல்றதை absorb பண்ணாம.",
      "{topic} — இதை யோசிக்கும்போது, நிறைய noise இருக்கு. Hot takes. Confident explanations. And somewhere underneath எல்லாத்துக்கும் கீழே — real people-ஐ real-ஆ affect பண்றது. That's worth pausing on. Not as a political statement. Just as a human one."]),

    ("Ending", "5:00 – 5:30",
     ["Camera-கிட்ட பாருங்க. Warm-ஆ, simple-ஆ.",
      "Like finishing a conversation with a friend."],
     ["Anyway. {topic} பத்தி என்னோட honest take இது. Expert opinion இல்ல. Just normal person making sense of something. நீங்க differently பாக்குறீங்களா — comment-ல சொல்லுங்க, genuinely படிக்கிறேன். இது மாதிரி straightforward coverage useful-ஆ இருந்தா subscribe பண்ணுங்க. See you in the next one.",
      "{topic} பத்தி இன்னிக்கு இது தான். Simple take. Real perspective. Useful-ஆ இருந்தா like பண்ணுங்க — more people-க்கு reach ஆக help பண்றது. Coverage-ல miss ஆகுதுன்னு நீங்க நினைக்குற part இருந்தா comment-ல சொல்லுங்க. Take care."]),
]

N_TA_LINES = [
    "{topic} பத்தி everybody பேசுறாங்க. ஆனா simply explain பண்றவங்க இல்ல — and that's the problem.",
    "Real people-ஐ affect பண்றது always paragraph seven-ல இருக்கு. Never the headline.",
    "நான் expert இல்ல. Just normal person paying attention. And sometimes that's enough.",
    "{news0} — அந்த part underreported-ஆ இருக்குன்னு நினைக்கிறேன்.",
    "Political version of this story-உம் human version-உம் two different things.",
    "All answers என்கிட்ட இல்ல. But I have questions — and I think that counts.",
    "{topic} பத்தி real story — loud headlines-ல இல்ல, quiet details-ல இருக்கு.",
    "React பண்றாங்க. ஆனா actually understand பண்றவங்க குறைவு. That gap matters.",
    "Simply பேசுறது — அதுதான் missing. அதுதான் நான் try பண்றது.",
    "Most affected people probably camera-முன்னாடி இல்லாதவங்க.",
    "{news1} — அது normal people-க்கு actually things-ஐ change பண்றது.",
    "Curious-ஆ இருங்க. Basic questions கேளுங்க. Loudest take-ஐ மட்டும் absorb பண்ணாதீங்க.",
]

N_TE_HOOKS = [
    "So {topic} — దీని గురించి మాట్లాడాలని చాలా రోజులు అనిపించింది. News లో చాలా ఉంది. కానీ normal person గా simply explain చేసే వాళ్ళు లేరు. So let me try to do that.",
    "Okay so {topic}. ఇది ఇప్పుడు everywhere ఉంది. కానీ media లో జరుగుతున్న conversation, real life లో జరుగుతున్న conversation completely different గా ఉన్నాయి. That gap bridge చేయడానికి try చేస్తాను.",
    "{topic} గురించి చాలా takes వస్తున్నాయి. Expert opinions, political commentary — అన్నీ. కానీ just a regular person's view? Agenda లేకుండా? That's what this is.",
    "ఈ రోజు — {TODAY} — news feed తెరిచాను. {topic} everywhere. నేను అనుకున్నాను — friend తో మాట్లాడినట్టు దీన్ని talk చేద్దాం. No spin. No agenda. నా actual thoughts మాత్రమే.",
]

N_TE_SCENES = [
    ("Start", "0:00 – 0:45",
     ["Camera వైపు directly మాట్లాడండి. Casual గా, relaxed గా. Friend కి catch up చేస్తున్నట్టు.",
      "No intro. Just start mid-thought. Conversation already జరుగుతున్నట్టు."],
     ["So {topic}. నేను దీన్ని కొన్ని రోజులుగా follow చేస్తున్నాను. And honestly, నేను చూస్తున్న coverage అన్నీ normal people కి actually ఏం matter అవుతుందో miss చేస్తున్నట్టు feel అవుతోంది. Political angle కాదు. Expert analysis కాదు. Just — ఇది మన daily life ని actually ఎలా affect చేస్తుందో. నేను ఎవరైనా అడిగినట్టు మాట్లాడదాం అని కూర్చున్నాను. Big claims లేవు. Just నా honest read.",
      "Okay so {topic} గురించి మాట్లాడాలి. And I want to do it the way nobody seems to be doing it right now — simply. నేను scroll చేసి చాలా takes చదివాను — none of it is answering my actual questions. Basic questions. Normal person అడిగే questions. So let me try. Expert కాదు నేను. Just someone who's been paying attention. And sometimes that's actually enough."]),

    ("What People Think", "0:45 – 2:00",
     ["Lean in slightly. Real people దగ్గర విన్నది share చేస్తున్నట్టు.",
      "Conversational. Friend కి జరిగింది చెప్తున్నట్టు."],
     ["{topic} తో problem ఏమిటంటే — news లో జరుగుతున్న conversation, normal people మాట్లాడే conversation match అవట్లేదు. News లో అంతా {news0} గురించి. That's real, that matters — dismiss చేయట్లేదు. కానీ నేను నా చుట్టూ ఉన్న వాళ్ళతో మాట్లాడినప్పుడు — friends, family, ఈ రోజు కలిసిన వాళ్ళు — వాళ్ళు actually worry చేసేది different. వాళ్ళ daily life లో ఎలా land అవుతుందో అని worry చేస్తున్నారు. Pocket లో, neighbourhood లో, kids school లో. Those two conversations barely overlap అవట్లేదు right now.",
      "{topic} గురించి నేను keep noticing చేసేది ఏమిటంటే — loud version of the story ఉంది — {news0}. Big headlines, strong opinions. And then quiet version ఉంది. ఎవరో ఇంట్లో కూర్చుని 'ఇది నా life ని actually ఎలా affect చేస్తుంది?' అని wonder చేస్తున్నారు. And nobody is really speaking to that quiet version. ఆ conversation నాకు కావాలి."]),

    ("Real Thought", "2:00 – 3:30",
     ["Slower. Like you're thinking through it in real time.",
      "Honest. Share what you actually found past the headlines."],
     ["{topic} గురించి actually important గా నేను think చేసేది — {news1}. ఈ part ని most people scroll చేసి వెళ్ళిపోతారు. Every article లో paragraph seven లో buried గా ఉంటుంది. కానీ ఈ part తానే ground level లో things change చేసేది. Regular people కి. Political fallout కాదు. Who-said-what కాదు. This specific thing. And దీనికి space దొరకట్లేదు. అదే story అవ్వాలి. కానీ అవట్లేదు.",
      "{topic} గురించి నేను understand చేసుకోవడానికి try చేస్తున్నది — {news1}. దీన్ని {news0} తో కలిపి చూస్తే — everybody మాట్లాడే part — actually more complicated picture కనిపిస్తుంది. Surface story ఒక విధంగా ఉంటుంది. కానీ details లో కూర్చుని చూస్తే — actual data, actual timeline, ఏం జరిగిందో versus ఏం చెప్తున్నారో — అది more nuanced. Nuance headlines కి boring. But అందులోనే truth usually ఉంటుంది."]),

    ("Personal Take", "3:30 – 4:30",
     ["Direct and honest. Your actual opinion.",
      "Friend కి properly ఆలోచించిన తర్వాత చెప్తున్నట్టు."],
     ["నా honest take — {topic} గురించి — coverage suggest చేసేదానికంటే normal people ని way more affect చేస్తుంది. Bills pay చేయడం, family feed చేయడం, city లో safe feel అవడం — అదే story. And right now ఆ story ని louder, more dramatic version of events drown out చేస్తోంది. That's a real problem. People news ని వాళ్ళ actual life తో connect చేయలేకపోతే — they stop paying attention. Then they stop participating. And that's when things really go sideways.",
      "నా genuine take — {topic} గురించి. Most affected people probably ఇప్పుడు microphone దగ్గర లేరు. Quietly deal చేస్తారు — ఎవరూ actually ఎలా land అయిందో అడగకుండా. And I think దాన్ని notice చేయడమే most useful thing. Camera లో good గా sound అయ్యే version కాదు. Real గా ఉన్న version. And right now — {news0} — that's real. That affects people. And it deserves more honest attention."]),

    ("Small Moment", "4:30 – 5:00",
     ["Pause. Quiet realisation.",
      "Simple and honest."],
     ["Honestly — {topic} ఎలా play out అవుతుందో తెలీదు. ఎవరికీ తెలీదు, really. కానీ coverage కి, people's actual lives కి మధ్య gap — అది real. And most honest thing మనం చేయగలిగేది — stay curious. Basic questions అడగడం continue చేయండి. Loudest voice చెప్పేది మాత్రమే absorb చేయకండి.",
      "{topic} — దీన్ని ఆలోచించినప్పుడు, చాలా noise ఉంది. Hot takes. Confident explanations. And somewhere underneath అన్నింటి కింద — real people ని real గా affect చేసేది ఉంది. That's worth pausing on. Not as a political statement. Just as a human one."]),

    ("Ending", "5:00 – 5:30",
     ["Camera వైపు చూడండి. Warm గా, simple గా.",
      "Like finishing a conversation with a friend."],
     ["Anyway. {topic} గురించి నా honest take ఇది. Expert opinion కాదు. Just normal person making sense of something. మీరు differently చూస్తున్నారా — comment లో చెప్పండి, నేను genuinely చదువుతాను. ఇలాంటి straightforward coverage useful గా అనిపిస్తే subscribe చేయండి. See you in the next one.",
      "{topic} గురించి ఈ రోజు ఇంతే. Simple take. Real perspective. Useful గా అనిపిస్తే like చేయండి — more people కి reach అవడానికి help చేస్తుంది. Coverage లో miss అవుతోందని మీకు అనిపించే part ఉంటే comment లో చెప్పండి. Take care."]),
]

N_TE_LINES = [
    "{topic} గురించి everybody మాట్లాడుతున్నారు. కానీ simply explain చేసే వాళ్ళు లేరు — and that's the problem.",
    "Real people ని affect చేసేది always paragraph seven లో ఉంటుంది. Never the headline.",
    "నేను expert కాదు. Just normal person paying attention. And sometimes that's enough.",
    "{news0} — ఆ part underreported గా ఉందని అనిపిస్తుంది.",
    "Political version of this story, human version — two completely different things.",
    "All answers నా దగ్గర లేవు. But I have questions — and I think that counts.",
    "{topic} గురించి real story — loud headlines లో కాదు, quiet details లో ఉంది.",
    "React చేస్తున్నారు. కానీ actually understand చేస్తున్న వాళ్ళు తక్కువ. That gap matters.",
    "Simply మాట్లాడడం — అదే missing. అదే నేను try చేస్తున్నది.",
    "Most affected people probably camera ముందు లేరు.",
    "{news1} — అది normal people కి actually things change చేస్తుంది.",
    "Curious గా ఉండండి. Basic questions అడగండి. Loudest take మాత్రమే absorb చేయకండి.",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  TECH SCENE BANKS
# ═══════════════════════════════════════════════════════════════════════════════

T_EN_HOOKS = [
    "Okay so {topic}. I've been going down the rabbit hole on this one and honestly — there's a lot of hype and not much plain explanation. So let me just break this down the way I would to a friend who asked me about it.",
    "So {topic} is everywhere right now. And I keep seeing two types of reactions — people saying it's going to change everything, and people who've completely tuned out. I think there's a more honest version in the middle. Let me share it.",
    "{topic}. I know the tech world moves fast and it's hard to keep up. So I just want to spend a few minutes explaining what this actually is, what it realistically means for you, and whether it's worth paying attention to.",
    "I've been looking into {topic} today — {TODAY} — and I want to give you the version I wish I'd found when I started looking. Not the hype version. Not the doom version. Just the clear, honest picture.",
]

T_EN_SCENES = [
    ("Hook Setup", "0:00 – 0:30",
     ["Directly to camera. Relaxed. Like you just figured something out and want to share it.",
      "Casual start. No dramatic music needed. Just you talking clearly."],
     ["Okay so I want to talk about {topic}. And I want to skip past all the hype for a second because I think there's a really clear, useful version of this story that isn't getting told very well. So that's what I'm going to do — just explain what this actually is, why people are talking about it, and honestly, what you actually need to know about it right now.",
      "So {topic}. I've spent the last few days actually reading about this instead of just absorbing takes — and here's the thing. Once you get past the noise, it's actually pretty interesting and understandable. My goal today is just to give you the version I wish I'd found first. Clear, honest, no unnecessary jargon."]),

    ("What It Actually Is", "0:30 – 1:30",
     ["Lean in. You're explaining something clearly. Imagine your smartest non-technical friend is listening.",
      "Conversational. Break it down step by step without talking down."],
     ["So at its core, {topic} is — {news0}. And I know that might sound technical but stick with me here because once you see the basic idea, the rest of it actually makes sense. The way I like to think about it is this: it's basically solving a problem that existed before but in a way that's significantly faster, more accurate, or more accessible than what came before. That's usually what's actually new. Not magic — just a meaningful improvement on something that already existed.",
      "Here's the simplest way I can put {topic}. What it does is — {news0}. Which sounds straightforward when you say it like that, right? The reason it sounds more complicated in most articles is that people explain the mechanism before the purpose. But if you start with what problem it solves, the rest clicks much faster. And the problem it's actually solving is — {angle}. That's the real starting point."]),

    ("Why It Matters Now", "1:30 – 3:00",
     ["Slower. Like you're connecting the dots in real time. Let it breathe.",
      "More thoughtful here. This is the part where the bigger picture lands."],
     ["And here's why {topic} is getting attention right now specifically — {news1}. Timing matters in tech, and this is one of those moments where a few things are converging at once. The underlying capability has improved, the cost has come down, and a critical mass of people are starting to actually use it in daily life rather than just read about it. That combination is what makes something actually shift from 'interesting' to 'relevant'. And {topic} has crossed that line, or is very close to it.",
      "The reason {topic} matters right now — and not just as an interesting thing to read about — is that {news1}. This is the part that doesn't make it into most coverage because it's less dramatic than the big claims. But it's the part that actually affects how people use their time, do their work, or spend their money. And those practical consequences are usually what matter most to regular people."]),

    ("Honest Assessment", "3:00 – 4:00",
     ["Direct. Your actual read on this — what's real vs overhyped.",
      "Honest and measured. Not dismissive, not breathless."],
     ["My honest take on {topic} is that it's genuinely worth understanding — but the version in most headlines is either too optimistic or too pessimistic. The realistic version is more like — {angle}. Meaning: real progress is happening, some of the use cases are legitimately useful for regular people, but the timeline and the impact for the average person is probably more gradual than the big claims suggest. And I think knowing that realistic version actually helps you make better decisions about whether to pay attention to this, learn about it, or wait.",
      "If I had to summarise my read on {topic} honestly — it's genuinely significant but not in the apocalyptic or utopian way it's often framed. What's actually true is that {angle}. And I think that realistic framing is more useful than the extremes, because it helps you engage with it intelligently rather than either panic-buying in or completely ignoring it. Both extremes usually lead to worse decisions than just understanding the thing clearly."]),

    ("Quick Takeaway", "4:00 – 4:30",
     ["Simple and clear. One or two things they can actually use.",
      "Practical close. Not a lecture — just the useful bit."],
     ["So if I'm distilling this down to what you actually need to know about {topic} right now — a few things. One: it's real and worth tracking even if you don't need to act on it immediately. Two: the most useful thing to follow is not the hype but the actual use cases that are appearing in everyday contexts. And three: {angle}. That last point is the one that usually gets left out but is probably the most practically relevant.",
      "The quick version of everything I just said about {topic}: it's genuinely moving, the realistic timeline is longer than headlines suggest, and the thing most worth paying attention to is {angle}. You don't have to become an expert in this. You just have to understand it well enough to recognise when it becomes relevant to your actual life. And that threshold is lower than most people think."]),

    ("Ending", "4:30 – 5:00",
     ["Look at the camera. Easy close. Like wrapping up a good conversation.",
      "Warm and direct. Invite them in without being pushy."],
     ["Anyway — that's my honest breakdown of {topic}. Not an expert take, just someone who spent time reading past the headlines and wanted to share what actually made sense. If this was useful, subscribe — I do this kind of plain-language breakdown regularly. And drop a comment: what part of {topic} did you want more detail on? I actually use those to plan what I cover next.",
      "That's the real version of {topic} as I understand it today. If it helped, hit like — it genuinely helps this reach more people. And if you've got a different read on it or a follow-up question, drop it in the comments. I'll be there. See you in the next one."]),
]

T_EN_LINES = [
    "Everyone's talking about {topic}. But most explanations skip the part that actually matters.",
    "Once you understand {angle}, the whole picture makes a lot more sense.",
    "The hype version and the real version of {topic} are pretty different things.",
    "I'm not an expert. Just someone who read past the headline and wants to share what I found.",
    "The most useful question with any new tech is — what problem does it actually solve?",
    "{news0} — that's the part that's actually moving things forward right now.",
    "Technology is most useful when it quietly makes something easier. {topic} does that.",
    "The realistic timeline on {topic} is less dramatic than the coverage suggests — and that's okay.",
    "Understanding something well enough to know if it affects you is actually all most people need.",
    "{angle} — once you see that, you can't unsee it.",
    "The practical version of {topic} is more interesting than the theoretical one.",
    "Don't ignore it, don't panic about it. Just understand it. That's enough.",
]

T_TA_HOOKS = [
    "Okay so {topic}. இதை பத்தி நிறைய படிச்சேன். And honestly — hype நிறைய இருக்கு, simple explanation இல்ல. So let me just break this down friend-கிட்ட சொல்வது மாதிரி.",
    "So {topic} everywhere இருக்கு right now. Two reactions பாக்குறேன் — 'இது எல்லாத்தையும் change பண்ணும்' னு சொல்றவங்க, completely tune out பண்ணவங்க. More honest version இருக்கு middle-ல. Let me share it.",
    "{topic} பத்தி நான் இன்னிக்கு — {TODAY} — look into பண்ணினேன். And I want to give you the version I wish I'd found. Hype version இல்ல. Doom version இல்ல. Just clear, honest picture.",
    "{topic}. Tech world fast-ஆ move பண்றது — keep up பண்றது hard. So let me just spend a few minutes explaining what this actually is, what it means for you, and whether it's worth paying attention to.",
]

T_TA_SCENES = [
    ("Hook Setup", "0:00 – 0:30",
     ["Directly to camera. Relaxed. Friend-கிட்ட share பண்றது மாதிரி.",
      "Casual start. Clear-ஆ பேசுங்க."],
     ["Okay so {topic} பத்தி பேசணும். And I want to skip past all the hype because இதோட clear, useful version clearly சொல்லலன்னு நினைக்கிறேன். So that's what I'm going to do — what this actually is, why people are talking about it, and honestly what you actually need to know right now.",
      "So {topic}. நான் கொஞ்சம் actually படிச்சேன் — takes absorb பண்றதுக்கு பதிலா. And here's the thing — noise-ஐ கடந்தா, actually interesting and understandable. என்னோட goal — I wish I'd found this version first. Clear, honest, unnecessary jargon இல்ல."]),

    ("What It Actually Is", "0:30 – 1:30",
     ["Lean in. Clear-ஆ explain பண்றீங்க. Smart but non-technical friend கேக்குறது மாதிரி.",
      "Conversational. Step by step break down பண்ணுங்க."],
     ["So {topic} என்னன்னா — {news0}. Technical-ஆ sound ஆகுதுன்னு தெரியும். ஆனா basic idea பாத்தா rest actually make sense ஆகுது. எப்படி நான் think பண்றேன்னா — ஒரு problem already existed, இது அதை significantly faster, more accurate or accessible-ஆ solve பண்றது. That's usually what's actually new. Magic இல்ல — meaningful improvement.",
      "{topic} simplest-ஆ சொல்றேன். It does — {news0}. அப்படி சொன்னா simple-ஆ sound ஆகுது, right? Most articles-ல complicated-ஆ sound ஆகுறது என்னன்னா — mechanism-ஐ purpose-க்கு முன்னாடி explain பண்றாங்க. Problem solve பண்றதுக்கு start பண்ணா rest faster click ஆகுது. And அது சொல்றது — {angle}."]),

    ("Why It Matters Now", "1:30 – 3:00",
     ["Slower. Connecting dots in real time.",
      "More thoughtful. Bigger picture lands here."],
     ["{topic} specifically இப்போ attention get பண்றது ஏன்னா — {news1}. Tech-ல timing matters. இது ஒரு moment where several things converge-ஆகுது — underlying capability improved, cost come down, critical mass of people actually using it in daily life rather than just reading about it. That combination-தான் 'interesting'-ல இருந்து 'relevant'-ஆ shift பண்றது. And {topic} has crossed that line, or is very close.",
      "{topic} இப்போ relevant-ஆ இருக்குறது ஏன்னா — {news1}. இந்த part most coverage-ல miss ஆகுது — big claims-ஐ விட less dramatic. But this is the part that actually affects how people use their time, do work, or spend money. And those practical consequences matter most."]),

    ("Honest Assessment", "3:00 – 4:00",
     ["Direct. What's real vs what's overhyped.",
      "Honest and measured. Not dismissive, not breathless."],
     ["{topic} பத்தி என்னோட honest take — genuinely worth understanding. ஆனா most headlines-ல version either too optimistic or too pessimistic. Realistic version more like — {angle}. Real progress நடக்குது, some use cases genuinely useful for regular people, but timeline and impact for average person is more gradual than the big claims suggest. And knowing that realistic version actually helps you make better decisions.",
      "{topic} பத்தி நான் honestly summarise பண்ணா — genuinely significant, ஆனா apocalyptic or utopian-ஆ often frame ஆகுறது மாதிரி இல்ல. Actually true என்னன்னா — {angle}. And that realistic framing is more useful than the extremes."]),

    ("Quick Takeaway", "4:00 – 4:30",
     ["Simple and clear. One or two things they can actually use.",
      "Practical. Not a lecture."],
     ["{topic} பத்தி actually know பண்ணணும்னு distil பண்ணா — சில things. One: real, track பண்ணணும். Two: hype இல்ல, everyday contexts-ல appear ஆகுற actual use cases-ஐ follow பண்ணுங்க. Three: {angle}. Last point usually left out — but most practically relevant.",
      "{topic} பத்தி quick version — genuinely moving, realistic timeline is longer than headlines suggest, and most worth paying attention to is {angle}. Expert ஆக வேண்டாம். Just understand it well enough to recognise when it becomes relevant to your actual life."]),

    ("Ending", "4:30 – 5:00",
     ["Camera-கிட்ட பாருங்க. Easy close.",
      "Warm and direct. Invite them in."],
     ["Anyway — {topic} பத்தி என்னோட honest breakdown. Expert take இல்ல — just someone who headlines-ஐ கடந்து படிச்சு share பண்ணணும்னு நினைச்சவன். Useful-ஆ இருந்தா subscribe பண்ணுங்க — இது மாதிரி plain-language breakdowns regularly பண்றேன். And comment-ல சொல்லுங்க: {topic} பத்தி என்ன more detail வேணும்னு? நான் அதை plan பண்றதுக்கு use பண்றேன்.",
      "{topic} பத்தி real version இது — today நான் understand பண்ணதுக்கு. Helped-ஆ இருந்தா like பண்ணுங்க — genuinely more people-க்கு reach ஆக help பண்றது. Different read இருந்தா or follow-up question இருந்தா — comments-ல drop பண்ணுங்க. See you in the next one."]),
]

T_TA_LINES = [
    "{topic} பத்தி everybody பேசுறாங்க. ஆனா actually matter பண்ற part-ஐ most explanations skip பண்றது.",
    "{angle} புரிஞ்சா — whole picture makes a lot more sense.",
    "{topic}-ஓட hype version-உம் real version-உம் pretty different things.",
    "Expert இல்ல நான். Just headline-ஐ கடந்து படிச்சவன். Share பண்ணணும்னு நினைச்சேன்.",
    "Any new tech-ல most useful question — actually என்ன problem solve பண்றதுன்னு.",
    "{news0} — அதுதான் right now things-ஐ forward move பண்றது.",
    "Technology most useful when quietly something easier பண்றது. {topic} does that.",
    "{topic}-ஓட realistic timeline — coverage suggest-ஐ விட less dramatic. And that's okay.",
    "Something affects you-ஆன்னு know பண்ண sufficient-ஆ understand பண்றது — that's all most people need.",
    "{angle} — அது ஒரு தடவை பாத்தா, unsee பண்ண முடியாது.",
    "{topic}-ஓட practical version — theoretical version-ஐ விட more interesting.",
    "Ignore பண்ணாதீங்க, panic ஆகாதீங்க. Just understand it. That's enough.",
]

T_TE_HOOKS = [
    "Okay so {topic}. దీని గురించి చాలా చదివాను. And honestly — hype చాలా ఉంది, simple explanation లేదు. So let me just break this down friend కి చెప్పినట్టు.",
    "So {topic} ఇప్పుడు everywhere ఉంది. Two reactions చూస్తున్నాను — 'ఇది అన్నింటినీ change చేస్తుంది' అనే వాళ్ళు, completely tune out అయినవాళ్ళు. More honest version ఉంది middle లో. Let me share it.",
    "{topic} గురించి నేను ఈ రోజు — {TODAY} — look into చేశాను. నేను కనుగొనాలని కోరుకున్న version ఇవ్వాలనుకుంటున్నాను. Hype version కాదు. Doom version కాదు. Just clear, honest picture.",
    "{topic}. Tech world fast గా move అవుతోంది — keep up అవడం hard. So let me just spend a few minutes explaining what this actually is, what it means for you, and whether it's worth paying attention to.",
]

T_TE_SCENES = [
    ("Hook Setup", "0:00 – 0:30",
     ["Directly to camera. Relaxed. Friend కి share చేస్తున్నట్టు.",
      "Casual start. Clear గా మాట్లాడండి."],
     ["Okay so {topic} గురించి మాట్లాడాలి. And I want to skip past all the hype because దీని clear, useful version చక్కగా చెప్పబడట్లేదని అనిపిస్తోంది. So that's what I'm going to do — what this actually is, why people are talking about it, and honestly what you actually need to know right now.",
      "So {topic}. నేను కొంచెం actually చదివాను — takes absorb చేయడానికి బదులు. And here's the thing — noise దాటిన తర్వాత, actually interesting and understandable. నా goal — నేను first గా కనుగొనాలని కోరుకున్న version ఇవ్వడం. Clear, honest, unnecessary jargon లేకుండా."]),

    ("What It Actually Is", "0:30 – 1:30",
     ["Lean in. Clear గా explain చేస్తున్నారు. Smart but non-technical friend వినేట్టు.",
      "Conversational. Step by step break down చేయండి."],
     ["So {topic} అంటే — {news0}. Technical గా sound అవుతుందని తెలుసు. కానీ basic idea చూస్తే rest actually make sense అవుతుంది. నేను ఎలా think చేస్తానంటే — ఒక problem already existed, ఇది దాన్ని significantly faster, more accurate or accessible గా solve చేస్తోంది. అదే usually what's actually new. Magic కాదు — meaningful improvement.",
      "{topic} simplest గా చెప్తాను. It does — {news0}. అలా చెప్తే simple గా sound అవుతుంది, right? Most articles లో complicated గా sound అవడానికి కారణం — mechanism ని purpose కంటే ముందు explain చేస్తారు. Problem solve నుండి start చేస్తే rest faster click అవుతుంది. And అది చెప్పేది — {angle}."]),

    ("Why It Matters Now", "1:30 – 3:00",
     ["Slower. Connecting dots in real time.",
      "More thoughtful. Bigger picture lands here."],
     ["{topic} specifically ఇప్పుడు attention get చేస్తోందంటే — {news1}. Tech లో timing matters. ఇది ఒక moment where several things converge అవుతున్నాయి — underlying capability improved, cost come down, critical mass of people actually using it in daily life rather than just reading about it. That combination తానే 'interesting' నుండి 'relevant' కి shift చేసేది. And {topic} has crossed that line, or is very close.",
      "{topic} ఇప్పుడు relevant గా ఉందంటే — {news1}. ఈ part most coverage లో miss అవుతుంది — big claims కంటే less dramatic. కానీ ఇదే actually people time, work, money ని affect చేసేది. And those practical consequences matter most."]),

    ("Honest Assessment", "3:00 – 4:00",
     ["Direct. What's real vs what's overhyped.",
      "Honest and measured."],
     ["{topic} గురించి నా honest take — genuinely worth understanding. కానీ most headlines లో version either too optimistic or too pessimistic. Realistic version — {angle}. Real progress జరుగుతోంది, some use cases genuinely useful for regular people, కానీ timeline and impact for average person is more gradual than the big claims suggest. And knowing that realistic version actually helps you make better decisions.",
      "{topic} గురించి honestly summarise చేస్తే — genuinely significant, కానీ apocalyptic or utopian గా often frame అవుతున్నట్టు కాదు. Actually true ఏమిటంటే — {angle}. And that realistic framing is more useful than the extremes."]),

    ("Quick Takeaway", "4:00 – 4:30",
     ["Simple and clear.",
      "Practical. Not a lecture."],
     ["{topic} గురించి actually know అవ్వాల్సింది distil చేస్తే — కొన్ని things. One: real, track చేయాలి. Two: hype కాదు, everyday contexts లో appear అవుతున్న actual use cases follow చేయండి. Three: {angle}. Last point usually left out — but most practically relevant.",
      "{topic} గురించి quick version — genuinely moving, realistic timeline is longer than headlines suggest, and most worth paying attention to is {angle}. Expert అవ్వాల్సిన అవసరం లేదు. Just understand it well enough to recognise when it becomes relevant to your actual life."]),

    ("Ending", "4:30 – 5:00",
     ["Camera వైపు చూడండి. Easy close.",
      "Warm and direct."],
     ["Anyway — {topic} గురించి నా honest breakdown. Expert take కాదు — just headlines దాటి చదివి share చేయాలనుకున్న ఒక వ్యక్తి. Useful గా అనిపిస్తే subscribe చేయండి — ఇలాంటి plain-language breakdowns regularly చేస్తాను. And comment లో చెప్పండి: {topic} గురించి ఏ part లో more detail కావాలో? నేను దాన్ని plan చేసుకోవడానికి use చేస్తాను.",
      "{topic} గురించి real version ఇది — today నేను understand చేసుకున్నది. Helped అయితే like చేయండి — genuinely more people కి reach అవడానికి help చేస్తుంది. Different read ఉంటే or follow-up question ఉంటే — comments లో drop చేయండి. See you in the next one."]),
]

T_TE_LINES = [
    "{topic} గురించి everybody మాట్లాడుతున్నారు. కానీ actually matter అయ్యే part ని most explanations skip చేస్తాయి.",
    "{angle} అర్థమైతే — whole picture makes a lot more sense.",
    "{topic} యొక్క hype version, real version pretty different things.",
    "Expert కాదు నేను. Just headline దాటి చదివి share చేయాలనుకున్న వాడిని.",
    "Any new tech లో most useful question — actually ఏ problem solve చేస్తుందో.",
    "{news0} — అదే right now things ని forward move చేస్తోంది.",
    "Technology most useful when quietly something easier చేస్తుంది. {topic} does that.",
    "{topic} యొక్క realistic timeline — coverage suggest చేసేదానికంటే less dramatic. And that's okay.",
    "Something affects you అవుతోందా అని know చేసుకోవడానికి sufficient గా understand చేసుకోవడం — that's all most people need.",
    "{angle} — ఒకసారి చూస్తే, unsee చేయలేరు.",
    "{topic} యొక్క practical version — theoretical version కంటే more interesting.",
    "Ignore చేయకండి, panic అవ్వకండి. Just understand it. That's enough.",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  FITNESS SCENE BANKS
# ═══════════════════════════════════════════════════════════════════════════════

F_EN_HOOKS = [
    "Okay so {topic}. I want to talk about this in a way that's actually honest — not the motivational version, not the before-and-after version. Just the real version of what this actually looks like.",
    "So I've been on this {topic} journey for a while now and the thing I keep noticing is — the conversation around it is either extremely inspiring or extremely unrealistic. Neither version is that useful. So let me give you the actual, practical version.",
    "{topic}. I know you've heard a million opinions on this. But here's what I actually think after doing this for real — and some of it might be different from what you've been told.",
    "I want to talk about {topic} today — {TODAY}. Not because I have it all figured out. But because I've been through enough of the messy middle to have some honest thoughts about what actually helps.",
]

F_EN_SCENES = [
    ("Start", "0:00 – 0:30",
     ["Casual. Like you're talking to someone who's trying to figure out the same thing you were.",
      "Relaxed. No gym background needed. Just talk."],
     ["So I want to talk about {topic} honestly. Not the version you see in the polished posts — where everything clicks and the results come fast and the motivation never wavers. The real version. The one where it's messier and slower and the wins are smaller but more sustainable. Because that version is actually more useful for most people, and I think it gets talked about less.",
      "Okay so {topic}. This is something I've thought a lot about because I've been in the thick of it. And the thing I keep wanting to say to people is — the picture you have in your head of what this looks like might be making it harder than it needs to be. So let me just share what I've actually found to be true. Starting from the beginning."]),

    ("The Reality Check", "0:30 – 1:30",
     ["Lean in. Like you're telling someone something you wish someone had told you.",
      "Direct but not discouraging. Honest about the difficulty without making it sound impossible."],
     ["The honest truth about {topic} is that the gap between starting and seeing results is longer than almost anyone prepares you for. And that gap — not the hard workouts, not the diet changes — that gap is where most people quietly give up. Not dramatically. Just gradually. They miss a few days, they get back to it, they miss a few more, and at some point they've stopped without ever really deciding to stop. The thing that actually helps most in that gap is not motivation. It's having a system small enough that you can maintain it even when motivation is low. {angle} — that's the specific thing I've found matters most.",
      "Here's what nobody really tells you about {topic} before you start. The first couple of weeks feel like progress. Energy is up, you're being intentional, you feel different. And then week three hits and the novelty is gone and you're still doing the same thing and the results feel distant. And that's the moment that separates the people who build a real habit from the people who restart the cycle a few months later. The difference usually isn't discipline — it's expectations. {angle} is what shifts those expectations to something realistic and useful."]),

    ("What Actually Works", "1:30 – 3:00",
     ["Thoughtful. Like you're sharing something that took you time to figure out.",
      "Slow down a bit here. Let it land."],
     ["The thing I've come to understand about {topic} is that the approaches that stick are usually the ones that feel almost too simple. Not complicated plans. Not extreme changes. Just — one thing you can actually do consistently, in the context of your actual life. Not your ideal life. Your real life. With the busy schedule and the unpredictable days and the weeks where everything goes slightly sideways. And the key word in all of that is consistency. Not intensity. Consistency. Because a moderate thing done regularly almost always beats an intense thing done occasionally.",
      "What actually moved the needle for me with {topic} — and it took longer than I expected to find this — is that the whole thing got easier when I stopped treating it as a separate project and started building it into things I was already doing. That sounds vague so let me be specific. {angle} is the version of this that actually lasted. Because it worked with my life instead of requiring my life to work around it. And I think that reframe — from 'what do I add' to 'what can I attach this to' — is genuinely underrated."]),

    ("Practical Steps", "3:00 – 4:00",
     ["Clear and direct. Give them something they can actually use.",
      "Like a friend who's been through it giving you the actual advice."],
     ["If you're starting with {topic} or starting again — which is totally valid — here's how I'd approach it. First: make the bar lower than feels right. The goal in the beginning is not to see results. The goal is to build the identity of someone who does this consistently. That means the first wins are not physical, they're behavioural. Second: track consistency, not performance. Did you do the thing or not. That's it. And third: {angle}. That third one is the one that made the biggest practical difference for me, so don't skip it.",
      "The practical version of {topic} that I'd actually recommend is this: start smaller than you think you need to, stay in it longer than feels productive, and pay attention to what makes it easy to repeat rather than what makes individual sessions impressive. And specifically — {angle}. Not as a hack, but as a sustainable reality. Because the version of {topic} that you can actually maintain for months is worth infinitely more than the version you do perfectly for two weeks."]),

    ("Progress Moment", "4:00 – 4:30",
     ["Quieter. A genuine moment. Not a highlight reel.",
      "Simple and honest. Not motivational — just real."],
     ["And here's the thing I actually want to say about progress with {topic}. The version in your head — where there's a clear before and after, where you hit a milestone and everything feels different — that version exists. But it usually doesn't look the way you imagine it will. The progress is mostly quiet. It's the day you do the thing without thinking about it much. It's the week where it stopped feeling like a task and started feeling like just something you do. That shift is subtle. And it's the actual goal. Not the result. The shift.",
      "The honest thing about making progress with {topic} is that it comes in such small increments that you often don't notice it happening. And then one day you look back at where you started and the distance surprises you. That's what the process actually looks like. Not a dramatic turning point. Just a lot of quiet, small, consistent things adding up over time. And that's actually worth more than any single result."]),

    ("Ending", "4:30 – 5:00",
     ["Camera. Warm close. No pressure.",
      "Like wrapping up a conversation with someone you want to succeed."],
     ["Anyway. {topic} — that's my honest version of it. No perfection, no secret formula, just the real practical version of what's worked for me. If you're in the middle of it right now, you're doing fine. Keep going. If this was useful, subscribe — I do honest content like this regularly. And leave a comment: where are you at with {topic} right now? I genuinely want to know.",
      "That's everything I have on {topic} today. If it was useful, hit like — it helps others find this kind of content. And I'd love to know — what's the specific thing you've been struggling with? Drop it below. I read all of them and sometimes it becomes the next video. See you in the next one."]),
]

F_EN_LINES = [
    "{topic} looks different in real life than it does in the posts. And that difference matters.",
    "The version that actually sticks is usually the one that feels almost too simple.",
    "Consistency beats intensity almost every time. Not occasionally — almost every time.",
    "{angle} — that's the specific thing that changed everything for me.",
    "The goal in the beginning is not results. It's building the identity of someone who shows up.",
    "Week three is where most people quietly stop. Knowing that changes how you approach it.",
    "Track consistency, not performance. Did you do the thing? That's the only question.",
    "A moderate thing done regularly beats an intense thing done occasionally.",
    "Progress is mostly quiet. And then one day you look back and the distance surprises you.",
    "{topic} works best when it works with your life, not when your life works around it.",
    "The shift from 'have to' to 'just do' — that's the actual goal.",
    "You don't have to have it figured out to start. You just have to start.",
]

F_TA_HOOKS = [
    "Okay so {topic}. இதை honestly பேசணும் — motivational version இல்ல, before-and-after version இல்ல. Just real version of what this actually looks like.",
    "So {topic} journey-ல நான் இருக்கேன். And I keep noticing — இதை பத்தி conversation either extremely inspiring or extremely unrealistic. Neither version that useful. So let me give you the actual, practical version.",
    "{topic}. நிறைய opinions கேட்டிருப்பீங்க. ஆனா நான் actually இதை பண்ணி என்ன find பண்ணேன்னு சொல்றேன் — some of it might be different from what you've been told.",
    "இன்னிக்கு {topic} பத்தி பேசணும் — {TODAY}. எல்லாம் figure out பண்ணிவிட்டேன்னு இல்ல. ஆனா messy middle-ஐ enough போச்சேன் — honest thoughts வந்திருக்கு.",
]

F_TA_SCENES = [
    ("Start", "0:00 – 0:30",
     ["Casual. Same thing figure out பண்ற ஒருத்தர்கிட்ட பேசுவது மாதிரி.",
      "Relaxed. Just talk."],
     ["So {topic} பத்தி honestly பேசணும். Polished posts-ல பாக்குற version இல்ல — everything clicks, results fast, motivation never wavers. Real version. Messier, slower, wins smaller but more sustainable. அந்த version most people-க்கு actually more useful. And I think it gets talked about less.",
      "Okay so {topic}. இதை நான் நிறைய யோசிச்சிருக்கேன். And the thing I keep wanting to say is — you have in your head of what this looks like might be making it harder than it needs to be. So let me just share what I've actually found to be true."]),

    ("The Reality Check", "0:30 – 1:30",
     ["Lean in. யாரோ உனக்கு சொல்லியிருந்தா நலமா இருக்கும்னு நினைக்குற விஷயம் சொல்வது மாதிரி.",
      "Direct but not discouraging."],
     ["{topic} பத்தி honest truth — starting-ல இருந்து results பாக்குற வரைக்கும் gap — almost anyone prepares you for அதை விட longer. And that gap — hard workouts இல்ல, diet changes இல்ல — அந்த gap-தான் most people quietly give up பண்ற இடம். Dramatically இல்ல. Just gradually. Miss a few days, back to it, miss more, சில point-ல decided பண்ணாமலேயே stopped. Actually most help பண்றது motivation இல்ல. Motivation low-ஆ இருக்கும்போதும் maintain பண்ண முடிற system. {angle} — அதுதான் I've found matters most.",
      "{topic} ஆரம்பிக்கும் முன்னாடி யாரும் really சொல்லாத விஷயம். First couple of weeks — progress feel ஆகுது. Energy up, intentional-ஆ இருக்கீங்க, different feel ஆகுது. Then week three hits — novelty gone, same thing doing, results feel distant. That's the moment. Discipline இல்ல usually difference — expectations. {angle} is what shifts those expectations."]),

    ("What Actually Works", "1:30 – 3:00",
     ["Thoughtful. Figure out பண்ண time எடுத்தது share பண்றது மாதிரி.",
      "Slow down. Let it land."],
     ["{topic} பத்தி நான் understand பண்றது — stick பண்ற approaches usually almost too simple-ஆ feel ஆகும். Complicated plans இல்ல. Extreme changes இல்ல. Just — one thing you can actually do consistently, in the context of your actual life. Ideal life இல்ல. Real life. With busy schedule, unpredictable days, weeks where everything goes sideways. And key word — consistency. Not intensity. Consistency. Moderate thing done regularly almost always beats intense thing done occasionally.",
      "{topic}-ல actually needle move பண்ணது — expect பண்ணதை விட longer time எடுத்தது find பண்ண — whole thing easier ஆனது when I stopped treating it as a separate project and started building it into things already doing. Vague-ஆ sound ஆகுது so specific-ஆ சொல்றேன். {angle} is the version of this that actually lasted. Because it worked with my life instead of requiring my life to work around it."]),

    ("Practical Steps", "3:00 – 4:00",
     ["Clear and direct. Actually use பண்ண முடிற விஷயம் கொடுங்க.",
      "Been through it-ன்னு சொல்ற friend's actual advice மாதிரி."],
     ["{topic} ஆரம்பிக்குறீங்களா or again ஆரம்பிக்குறீங்களா — totally valid — என்னோட approach: First: bar-ஐ feel right-ஆ இருக்குறதை விட lower பண்ணுங்க. Beginning-ல goal results பாக்குறது இல்ல. Goal — consistently இதை பண்ற ஒருத்தரோட identity build பண்றது. Second: consistency track பண்ணுங்க, performance இல்ல. Did you do the thing or not. Third: {angle}. That third one made the biggest practical difference — don't skip it.",
      "{topic}-ஓட practical version recommend பண்றேன்: think பண்றதை விட smaller-ஆ start பண்ணுங்க, productive feel ஆகுற நேரத்தை விட longer-ஆ in it இருங்க, individual sessions impressive பண்றதை விட what makes it easy to repeat-ஐ pay attention. And specifically — {angle}. Not a hack — sustainable reality. Months maintain பண்ண முடிற version — two weeks perfectly பண்றதை விட infinitely worth more."]),

    ("Progress Moment", "4:00 – 4:30",
     ["Quieter. Genuine moment.",
      "Simple and honest."],
     ["{topic}-ல progress பத்தி actually சொல்லணும்னு நினைக்குறது: உங்க head-ல version — clear before and after, milestone hit பண்ணா everything different feel ஆகுது — that version exists. ஆனா usually imagine பண்றது மாதிரி look ஆகல. Progress mostly quiet. The day you do the thing without thinking much about it. The week where it stopped feeling like a task and started feeling like just something you do. That shift is subtle. And it's the actual goal. Not the result. The shift.",
      "{topic}-ல progress பண்றதோட honest thing — such small increments-ல வருது that you often don't notice. And then one day look back — the distance surprises you. That's what the process looks like. Not dramatic turning point. Just a lot of quiet, small, consistent things adding up. And that's actually worth more than any single result."]),

    ("Ending", "4:30 – 5:00",
     ["Camera. Warm close.",
      "Success வேணும்னு நினைக்குற ஒருத்தர்கிட்ட conversation end பண்றது மாதிரி."],
     ["Anyway. {topic} — என்னோட honest version இது. Perfection இல்ல, secret formula இல்ல, just real practical version of what's worked. இப்போ middle-ல இருக்கீங்களா — you're doing fine. Keep going. Useful-ஆ இருந்தா subscribe பண்ணுங்க. And comment-ல சொல்லுங்க: {topic}-ல நீங்க right now எங்க இருக்கீங்க? Genuinely want to know.",
      "{topic} பத்தி today-க்கு இது தான் எல்லாமே. Useful-ஆ இருந்தா like பண்ணுங்க — இது மாதிரி content others-க்கு find பண்ண help பண்றது. Specifically என்ன struggle பண்றீங்க? Below drop பண்ணுங்க. I read all of them. See you in the next one."]),
]

F_TA_LINES = [
    "{topic} real life-ல posts-ல பாக்குறதை விட different. And that difference matters.",
    "Actually stick ஆகுற version usually almost too simple-ஆ feel ஆகும்.",
    "Consistency beats intensity almost every time.",
    "{angle} — அதுதான் specifically everything change பண்ணது.",
    "Beginning-ல goal results இல்ல. Consistently show up பண்ற ஒருத்தரோட identity build பண்றது.",
    "Week three-ல most people quietly stop. அது தெரிஞ்சா approach-ஐ change பண்ணலாம்.",
    "Consistency track பண்ணுங்க, performance இல்ல. Did you do the thing? That's the only question.",
    "Moderate thing done regularly beats intense thing done occasionally.",
    "Progress mostly quiet. One day look back — distance surprises you.",
    "{topic} — உங்க life-கூட work பண்ணும்போது best-ஆ work பண்றது.",
    "'Have to' to 'just do' shift — that's the actual goal.",
    "Figure out பண்ணியிருக்கணும்னு இல்ல. Just start பண்றது enough.",
]

F_TE_HOOKS = [
    "Okay so {topic}. దీని గురించి honestly మాట్లాడాలనుకుంటున్నాను — motivational version కాదు, before-and-after version కాదు. Just real version of what this actually looks like.",
    "So {topic} journey లో నేను ఉన్నాను. And I keep noticing — దీని గురించి conversation either extremely inspiring or extremely unrealistic. Neither version that useful. So let me give you the actual, practical version.",
    "{topic}. చాలా opinions విన్నారు. కానీ నేను actually దీన్ని చేసి ఏం find చేశానో చెప్తాను — some of it might be different from what you've been told.",
    "ఈ రోజు {topic} గురించి మాట్లాడాలి — {TODAY}. అన్నీ figure out చేశాననుకోలేదు. కానీ messy middle లో enough గా వెళ్ళాను — honest thoughts వచ్చాయి.",
]

F_TE_SCENES = [
    ("Start", "0:00 – 0:30",
     ["Casual. Same thing figure out చేస్తున్న ఒక్కరితో మాట్లాడినట్టు.",
      "Relaxed. Just talk."],
     ["So {topic} గురించి honestly మాట్లాడాలి. Polished posts లో చూసే version కాదు — everything clicks, results fast, motivation never wavers. Real version. Messier, slower, wins smaller but more sustainable. ఆ version most people కి actually more useful. And I think it gets talked about less.",
      "Okay so {topic}. దీన్ని నేను చాలా ఆలోచించాను. And the thing I keep wanting to say is — మీ head లో ఉన్న version అది అవసరమైనదానికంటే harder చేస్తుండవచ్చు. So let me just share what I've actually found to be true."]),

    ("The Reality Check", "0:30 – 1:30",
     ["Lean in. ఎవరైనా చెప్పి ఉంటే బాగుండేదని అనిపించే విషయం చెప్తున్నట్టు.",
      "Direct but not discouraging."],
     ["{topic} గురించి honest truth — start నుండి results చూసే వరకు gap — almost anyone prepares you కంటే longer. And that gap — hard workouts కాదు, diet changes కాదు — ఆ gap లోనే most people quietly give up చేస్తారు. Dramatically కాదు. Just gradually. Miss a few days, back to it, miss more, ఒక point లో decide చేయకుండా stopped అయిపోతారు. Actually most help చేసేది motivation కాదు. Motivation low గా ఉన్నప్పుడు కూడా maintain చేయగలిగే system. {angle} — అదే I've found matters most.",
      "{topic} start చేయడానికి ముందు ఎవరూ really చెప్పనిది. First couple of weeks — progress feel అవుతుంది. Energy up, intentional గా ఉన్నారు, different feel అవుతుంది. Then week three hits — novelty gone, same thing doing, results feel distant. That's the moment. Usually difference discipline కాదు — expectations. {angle} is what shifts those expectations."]),

    ("What Actually Works", "1:30 – 3:00",
     ["Thoughtful. Figure out చేయడానికి time తీసుకున్నది share చేస్తున్నట్టు.",
      "Slow down. Let it land."],
     ["{topic} గురించి నేను understand చేసుకున్నది — stick అయ్యే approaches usually almost too simple గా feel అవుతాయి. Complicated plans కాదు. Extreme changes కాదు. Just — one thing you can actually do consistently, in the context of your actual life. Ideal life కాదు. Real life. With busy schedule, unpredictable days, weeks where everything goes sideways. And key word — consistency. Not intensity. Consistency. Moderate thing done regularly almost always beats intense thing done occasionally.",
      "{topic} లో actually needle move చేసింది — expect చేసినదానికంటే longer time తీసుకుంది find చేయడానికి — whole thing easier అయింది when I stopped treating it as a separate project and started building it into things already doing. Specific గా చెప్తాను. {angle} is the version of this that actually lasted. Because it worked with my life instead of requiring my life to work around it."]),

    ("Practical Steps", "3:00 – 4:00",
     ["Clear and direct. Actually use చేయగలిగేది ఇవ్వండి.",
      "Been through it అని చెప్పే friend's actual advice లాగా."],
     ["{topic} start చేస్తున్నారా or again start చేస్తున్నారా — totally valid — నా approach: First: bar ని feel right అనిపించేదానికంటే lower చేయండి. Beginning లో goal results కాదు. Goal — consistently దీన్ని చేసే ఒకరి identity build చేయడం. Second: consistency track చేయండి, performance కాదు. Did you do the thing or not. Third: {angle}. That third one made the biggest practical difference — don't skip it.",
      "{topic} యొక్క practical version recommend చేస్తాను: think చేసేదానికంటే smaller గా start చేయండి, productive feel అయ్యే దానికంటే longer గా in it ఉండండి, individual sessions impressive చేయడం కంటే what makes it easy to repeat కి pay attention. And specifically — {angle}. Not a hack — sustainable reality. Months maintain చేయగలిగే version — two weeks perfectly చేయడం కంటే infinitely worth more."]),

    ("Progress Moment", "4:00 – 4:30",
     ["Quieter. Genuine moment.",
      "Simple and honest."],
     ["{topic} లో progress గురించి actually చెప్పాలనుకుంటున్నది: మీ head లో version — clear before and after, milestone hit చేసినప్పుడు everything different feel అవుతుంది — that version exists. కానీ usually imagine చేసినట్టు look అవదు. Progress mostly quiet. The day you do the thing without thinking much about it. The week where it stopped feeling like a task and started feeling like just something you do. That shift is subtle. And it's the actual goal.",
      "{topic} లో progress చేయడం గురించి honest thing — such small increments లో వస్తుంది that you often don't notice. And then one day look back — the distance surprises you. That's what the process looks like. Not dramatic turning point. Just a lot of quiet, small, consistent things adding up. And that's actually worth more than any single result."]),

    ("Ending", "4:30 – 5:00",
     ["Camera. Warm close.",
      "Success కావాలనుకునే ఒకరితో conversation end చేస్తున్నట్టు."],
     ["Anyway. {topic} — నా honest version ఇది. Perfection లేదు, secret formula లేదు, just real practical version of what's worked. ఇప్పుడు middle లో ఉన్నారా — you're doing fine. Keep going. Useful గా అనిపిస్తే subscribe చేయండి. And comment లో చెప్పండి: {topic} లో మీరు right now ఎక్కడ ఉన్నారు? Genuinely want to know.",
      "{topic} గురించి today కి ఇంతే. Useful గా అనిపిస్తే like చేయండి — ఇలాంటి content others కి find అవడానికి help చేస్తుంది. Specifically మీరు ఏమి struggle చేస్తున్నారు? Below drop చేయండి. I read all of them. See you in the next one."]),
]

F_TE_LINES = [
    "{topic} real life లో posts లో చూసేదానికంటే different. And that difference matters.",
    "Actually stick అయ్యే version usually almost too simple గా feel అవుతుంది.",
    "Consistency beats intensity almost every time.",
    "{angle} — అదే specifically everything change చేసింది.",
    "Beginning లో goal results కాదు. Consistently show up చేసే ఒకరి identity build చేయడం.",
    "Week three లో most people quietly stop అవుతారు. అది తెలిస్తే approach change చేయవచ్చు.",
    "Consistency track చేయండి, performance కాదు. Did you do the thing? That's the only question.",
    "Moderate thing done regularly beats intense thing done occasionally.",
    "Progress mostly quiet. One day look back — distance surprises you.",
    "{topic} — మీ life తో work చేసినప్పుడు best గా work అవుతుంది.",
    "'Have to' to 'just do' shift — that's the actual goal.",
    "Figure out చేయాల్సిన అవసరం లేదు. Just start చేయడం enough.",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  LIFESTYLE SCENE BANKS
# ═══════════════════════════════════════════════════════════════════════════════

L_EN_HOOKS = [
    "Okay so {topic}. I want to talk about this in a way that feels actually real — not the curated version, not the aesthetically perfect version. The actual version, with all the parts that don't make it into the posts.",
    "So I've been thinking about {topic} a lot lately. And I keep noticing the same thing — the way it's usually presented makes it look way more seamless than it actually is. So let me give you the real version.",
    "{topic}. There's so much content about this. But I feel like most of it is the highlight reel. What I want to do is fill in the gaps — the parts that aren't shown but are completely normal and actually really useful to hear.",
    "I want to talk about something I've been working on — {topic}. Not because I have it perfected. But because I've been in the process long enough to have some honest thoughts about what works and what doesn't.",
]

L_EN_SCENES = [
    ("Start", "0:00 – 0:30",
     ["Relaxed and genuine. Like you're picking up a conversation you've wanted to have.",
      "Casual. Just start talking. No big setup needed."],
     ["So {topic}. I've wanted to talk about this for a while because I feel like the conversation around it is kind of missing something. Everyone's either showing you the perfect version or the total failure version. And the part that's actually most relatable — the middle bit, the gradual bit, the 'still figuring it out' bit — that rarely gets talked about honestly. So let me try to do that. Starting from where I actually am with this.",
      "Okay so I want to have an honest conversation about {topic}. Because I've been doing this for long enough now to have moved past the initial excitement and into the part where you find out what's actually real about it. And that part — the part after the excitement — is usually the more useful part to talk about. So that's what I'm going to do."]),

    ("The Before", "0:30 – 1:30",
     ["Honest about where you were. No need to dramatise it.",
      "Like telling a friend what your life looked like before you made this change."],
     ["Before I got into {topic}, the honest version is — I was in a pattern that wasn't working for me and I could feel it. Not in a dramatic way. Just in that quiet, low-level way where things feel slightly off for long enough that you can't remember what normal feels like. And I think that state is actually really common and really underreported. People don't talk about the 'slightly off' period. They talk about the rock bottom version or the perfectly fine version. The 'slightly off' version — where you're functioning but not great — that's usually where most change actually starts.",
      "The honest starting point with {topic} for me was — I had a version of this in my head that I wanted, and then I had the version I was actually living, and the gap between those two things was getting louder. Not in a way that caused a crisis. Just in a way that kept nudging me. And I think that nudge — that quiet persistent feeling that something could be different — is actually the most honest reason most people start making changes. Not inspiration. Just a nudge they eventually listened to."]),

    ("The Change I Made", "1:30 – 3:00",
     ["Thoughtful. Like recounting something you actually did, not something you're performing.",
      "Slow and genuine here. The details matter."],
     ["So what I actually did with {topic} — and this is the part that always gets left out because it's not dramatic — is that I started really small. And I mean embarrassingly small. Not because I planned it that way but because every other version I'd tried had eventually collapsed. And something I'd read had made me think: the problem isn't motivation, the problem is the starting threshold being too high. So I lowered it. Drastically. And the thing that happened was — {angle}. That specific shift is what made the difference. Not a big change. A small, sustainable one.",
      "The change I made with {topic} wasn't the sweeping, everything-at-once version. It was one thing. One small thing, done consistently. And the reason that worked when bigger attempts hadn't is what I want to talk about. Because I think it comes down to — {angle}. That's the version I've come to believe is actually true after doing this for real rather than just thinking about doing it."]),

    ("The Detail That Matters", "3:00 – 4:00",
     ["Clear and specific. Give them the actual thing, not just the idea.",
      "Like sharing the one insight that made something click."],
     ["The specific thing about {topic} that I think makes the biggest difference — and that I almost never see discussed — is that how you talk to yourself about it matters as much as what you actually do. Not in a toxic positivity way. In a practical way. If the story you're telling yourself is 'I'm the kind of person who always fails at this', then every difficult moment confirms that story. And it becomes self-fulfilling. But if the story shifts to 'I'm building a new pattern and that takes time' — the difficult moments stop feeling like failures and start feeling like normal parts of the process. And {angle} is the specific moment where that shift happened for me.",
      "Here's the detail about {topic} that actually made it work long-term for me. It's not about the content of what I was doing. It's about how I defined success. I had been defining it as 'doing this perfectly and seeing results quickly'. And I changed that definition to 'doing this consistently and measuring over months, not days'. That single reframe — {angle} — changed everything. Because suddenly I was succeeding almost every day, even when things weren't perfect. And that feeling of succeeding is what keeps you going."]),

    ("Being Honest", "4:00 – 4:30",
     ["Quiet. Drop the performance here if there's been any. Just say the honest thing.",
      "Like the end of a long conversation where you finally say the real thing."],
     ["And the honest part of all of this is — I still don't have it perfectly sorted. Some days are significantly better than others. Some weeks I completely drop the thread and have to pick it back up. And I used to feel bad about that. Like it meant the change wasn't real or wasn't working. But I've come to understand that the dropping and picking back up is just part of the process, not evidence that the process is failing. And I think that reframe is actually really important. Especially with {topic}.",
      "The part I want to be honest about is that {topic} — the version I have now — is still a work in progress. It doesn't look the way I thought it would look when I started. Some parts are better than I expected. Some parts are harder. And I've stopped waiting for the version where it's all sorted to talk about it, because I think the 'still in progress' version is actually the most useful one to hear. Because that's where most people are too."]),

    ("Ending", "4:30 – 5:00",
     ["Camera. Warm close. Simple.",
      "Like ending a good honest conversation."],
     ["Anyway. That's my real, honest version of {topic}. Not the polished version — the in-progress one. If something in here landed for you, I'd love to know which part. Drop it in the comments — I genuinely use those to understand what people want more of. And if you want to keep having these honest conversations, subscribe. I'll see you in the next one.",
      "That's everything I had to say about {topic} today. If it was useful, hit like. And leave a comment — I'd genuinely love to know: what's your honest version of where you are with {topic} right now? I read everything. See you soon."]),
]

L_EN_LINES = [
    "The 'slightly off' period before big change — that's the part nobody talks about honestly.",
    "{topic} looks different in progress than it does in the finished version.",
    "The version you're working toward doesn't have to look like anyone else's version.",
    "Small and sustainable almost always outlasts big and dramatic.",
    "{angle} — that specific shift made everything else easier.",
    "Dropping the thread and picking it back up is part of the process, not failure.",
    "Redefining what success means was more useful than trying harder.",
    "I still don't have it perfectly sorted. And that's actually fine.",
    "The middle part — the gradual, messy middle — is where most of the real work happens.",
    "How you talk to yourself about this matters as much as what you actually do.",
    "Most people are in the 'still figuring it out' phase. It's the most normal phase.",
    "Progress doesn't announce itself. You look back and notice it.",
]

L_TA_HOOKS = [
    "Okay so {topic}. இதை actually real-ஆ பேசணும் — curated version இல்ல, aesthetically perfect version இல்ல. Actual version, posts-ல வராத parts உட்பட.",
    "So {topic} பத்தி நிறைய யோசிக்கிறேன் lately. And I keep noticing — usually present பண்றது way more seamless-ஆ look ஆகுது than it actually is. So let me give you the real version.",
    "{topic}. நிறைய content இருக்கு. ஆனா most of it highlight reel மாதிரி feel ஆகுது. Gaps fill பண்ணணும் — show ஆகாத parts, but completely normal and useful to hear.",
    "{topic} பத்தி honest-ஆ பேசணும். Perfect-ஆ இல்ல. ஆனா process-ல long enough இருக்கேன் — what works and what doesn't பத்தி honest thoughts இருக்கு.",
]

L_TA_SCENES = [
    ("Start", "0:00 – 0:30",
     ["Relaxed and genuine. Pick up பண்ண want பண்ற conversation continue பண்றது மாதிரி.",
      "Casual. Just start talking."],
     ["So {topic}. இதை பத்தி நிறைய நாளா பேசணும்னு இருந்தேன். Because conversation-ல something missing-ஆ feel ஆகுது. Perfect version-ஓ total failure version-ஓ show பண்றாங்க. Actually most relatable part — middle bit, gradual bit, 'still figuring it out' bit — honestly talk ஆகல. So let me try to do that. Starting from where I actually am.",
      "Okay so {topic} பத்தி honest conversation வேணும். Long enough பண்ணிட்டேன் — initial excitement கடந்து what's actually real-ஆ இருக்குன்னு part-க்கு வந்திருக்கேன். And that part — excitement-க்கு பிறகு — usually more useful part to talk about. So that's what I'm going to do."]),

    ("The Before", "0:30 – 1:30",
     ["Honest about where you were. No dramatics needed.",
      "Friend-கிட்ட change பண்றதுக்கு முன்னாடி life மாதிரி இருந்துன்னு சொல்வது மாதிரி."],
     ["{topic}-க்கு முன்னாடி — honest version — நான் ஒரு pattern-ல இருந்தேன் that wasn't working. Dramatic-ஆ இல்ல. Just quietly, low-level-ஆ, things slightly off feel ஆகுது long enough-ஆ that you can't remember normal. And that state actually really common and really underreported. 'Slightly off' period பத்தி people talk பண்றதில்ல. Rock bottom version-ஓ perfectly fine version-ஓ. 'Slightly off' version — functioning but not great — that's usually where most change actually starts.",
      "{topic} honest starting point — head-ல ஒரு version வேணும்னு இருந்தது, actually living version different, and gap between those two things was getting louder. Not causing a crisis. Just nudging. And that nudge — quiet persistent feeling something could be different — actually most honest reason most people start making changes. Not inspiration. Just a nudge they eventually listened to."]),

    ("The Change I Made", "1:30 – 3:00",
     ["Thoughtful. Actually பண்ணதை recounting பண்றது மாதிரி.",
      "Slow and genuine. Details matter."],
     ["{topic}-ல actually பண்ணது — always left out part because not dramatic — really small-ஆ start பண்ணினேன். Embarrassingly small. Plan பண்ணி இல்ல — every other version I'd tried had eventually collapsed. Problem motivation இல்ல — starting threshold too high. So lowered it. Drastically. And the thing that happened was — {angle}. That specific shift made the difference. Not a big change. A small, sustainable one.",
      "{topic}-ல change sweeping, everything-at-once version இல்ல. One thing. One small thing, done consistently. And the reason that worked when bigger attempts hadn't — {angle}. That's the version I've come to believe is actually true after doing this for real."]),

    ("The Detail That Matters", "3:00 – 4:00",
     ["Clear and specific. Actual thing கொடுங்க.",
      "Something click ஆன insight share பண்றது மாதிரி."],
     ["{topic} பத்தி biggest difference பண்ற specific thing — almost never discussed — how you talk to yourself matters as much as what you actually do. Toxic positivity இல்ல. Practical way. 'I'm the kind of person who always fails at this'ன்னு story tell பண்ணா — every difficult moment confirms that story. Self-fulfilling ஆகுது. But if story shifts to 'I'm building a new pattern and that takes time' — difficult moments failures-ஆ feel ஆகல, normal parts of the process-ஆ feel ஆகுது. And {angle} is the specific moment where that shift happened for me.",
      "{topic} long-term work பண்ண actually பண்ணது detail — doing-ஓட content இல்ல. How I defined success. 'Doing this perfectly and seeing results quickly'ன்னு define பண்ணினேன். Changed to 'doing this consistently and measuring over months, not days'. That single reframe — {angle} — changed everything. Suddenly succeeding almost every day, even when not perfect. And that feeling of succeeding is what keeps you going."]),

    ("Being Honest", "4:00 – 4:30",
     ["Quiet. Honest thing சொல்லுங்க.",
      "Long conversation-ஓட end-ல real thing சொல்வது மாதிரி."],
     ["And honest part of all of this — I still don't have it perfectly sorted. Some days significantly better than others. Some weeks completely drop the thread. Before feel bad about it. Like change wasn't real. But I've come to understand — dropping and picking back up is just part of the process, not evidence that the process is failing. And that reframe is actually really important. Especially with {topic}.",
      "{topic} — version I have now — still a work in progress. Start பண்ணும்போது நினைச்சது மாதிரி look ஆகல. Some parts better than expected. Some parts harder. Sorted version வரும்வரை wait பண்றது stop பண்ணினேன் — because 'still in progress' version is actually the most useful one to hear. Because that's where most people are too."]),

    ("Ending", "4:30 – 5:00",
     ["Camera. Warm close.",
      "Good honest conversation end பண்றது மாதிரி."],
     ["Anyway. {topic} பத்தி real, honest version இது. Polished version இல்ல — in-progress one. Something landed-ஆ — which part-ன்னு comments-ல சொல்லுங்க. Genuinely use பண்றேன் people என்ன more want பண்றாங்கன்னு understand பண்ண. இது மாதிரி honest conversations வேணும்னா subscribe பண்ணுங்க. See you in the next one.",
      "இன்னிக்கு {topic} பத்தி எல்லாமே இது தான். Useful-ஆ இருந்தா like பண்ணுங்க. And comment-ல சொல்லுங்க: {topic} பத்தி right now நீங்க honest-ஆ எங்க இருக்கீங்க? I read everything. See you soon."]),
]

L_TA_LINES = [
    "Big change-க்கு முன்னாடி 'slightly off' period — honestly talk ஆகாத part அது.",
    "{topic} — finished version-ஐ விட progress-ல different-ஆ look ஆகுது.",
    "நீங்க work பண்ற version யாரோட version-ஆவது மாதிரி இருக்கணும்னு இல்ல.",
    "Small and sustainable almost always outlasts big and dramatic.",
    "{angle} — that specific shift made everything else easier.",
    "Thread drop பண்ணி pick back up பண்றது — process-ஓட part. Failure இல்ல.",
    "Success என்னன்னு redefine பண்றது — harder try பண்றதை விட more useful.",
    "I still don't have it perfectly sorted. And that's actually fine.",
    "Middle part — gradual, messy middle — அதுல தான் most of the real work நடக்குது.",
    "How you talk to yourself about this matters as much as what you actually do.",
    "Most people 'still figuring it out' phase-ல இருக்காங்க. It's the most normal phase.",
    "Progress announce பண்றதில்ல. Look back பண்ணும்போது notice ஆகுது.",
]

L_TE_HOOKS = [
    "Okay so {topic}. దీన్ని actually real గా మాట్లాడాలనుకుంటున్నాను — curated version కాదు, aesthetically perfect version కాదు. Actual version, posts లో రాని parts తో సహా.",
    "So {topic} గురించి lately చాలా ఆలోచిస్తున్నాను. And I keep noticing — usually present చేసే way actually అయినదానికంటే way more seamless గా look అవుతుంది. So let me give you the real version.",
    "{topic}. చాలా content ఉంది. కానీ most of it highlight reel లా feel అవుతుంది. Gaps fill చేయాలి — show కాని parts, but completely normal and useful to hear.",
    "{topic} గురించి honest గా మాట్లాడాలి. Perfect గా లేదు. కానీ process లో long enough ఉన్నాను — what works and what doesn't గురించి honest thoughts ఉన్నాయి.",
]

L_TE_SCENES = [
    ("Start", "0:00 – 0:30",
     ["Relaxed and genuine. Pick up చేయాలనుకున్న conversation continue చేస్తున్నట్టు.",
      "Casual. Just start talking."],
     ["So {topic}. దీని గురించి చాలా కాలంగా మాట్లాడాలనుకుంటున్నాను. Because conversation లో something missing గా feel అవుతుంది. Perfect version చూపిస్తున్నారు లేదా total failure version. Actually most relatable part — middle bit, gradual bit, 'still figuring it out' bit — honestly talk అవట్లేదు. So let me try to do that. Starting from where I actually am.",
      "Okay so {topic} గురించి honest conversation కావాలి. Long enough చేశాను — initial excitement దాటి what's actually real అయింది అనే part కి వచ్చాను. And that part — excitement తర్వాత — usually more useful part to talk about. So that's what I'm going to do."]),

    ("The Before", "0:30 – 1:30",
     ["Honest about where you were. No dramatics.",
      "Friend కి change చేయడానికి ముందు life ఎలా ఉందో చెప్తున్నట్టు."],
     ["{topic} కి ముందు — honest version — నేను ఒక pattern లో ఉన్నాను that wasn't working. Dramatic గా కాదు. Just quietly, low-level గా, things slightly off feel అవుతున్నాయి long enough గా that you can't remember normal. And that state actually really common and really underreported. 'Slightly off' period గురించి people మాట్లాడరు. Rock bottom version లేదా perfectly fine version. 'Slightly off' version — functioning but not great — that's usually where most change actually starts.",
      "{topic} honest starting point — head లో ఒక version కావాలని ఉంది, actually living version different, and gap between those two things was getting louder. Crisis కాదు. Just nudging. And that nudge — quiet persistent feeling something could be different — actually most honest reason most people start making changes. Not inspiration. Just a nudge they eventually listened to."]),

    ("The Change I Made", "1:30 – 3:00",
     ["Thoughtful. Actually చేసింది recounting చేస్తున్నట్టు.",
      "Slow and genuine. Details matter."],
     ["{topic} లో actually చేసింది — always left out part because not dramatic — really small గా start చేశాను. Embarrassingly small. Plan చేసి కాదు — every other version I'd tried had eventually collapsed. Problem motivation కాదు — starting threshold too high. So lowered it. Drastically. And the thing that happened was — {angle}. That specific shift made the difference. Not a big change. A small, sustainable one.",
      "{topic} లో change sweeping, everything-at-once version కాదు. One thing. One small thing, done consistently. And the reason that worked when bigger attempts hadn't — {angle}. That's the version I've come to believe is actually true after doing this for real."]),

    ("The Detail That Matters", "3:00 – 4:00",
     ["Clear and specific. Actual thing ఇవ్వండి.",
      "Something click అయిన insight share చేస్తున్నట్టు."],
     ["{topic} గురించి biggest difference చేసే specific thing — almost never discussed — how you talk to yourself matters as much as what you actually do. Toxic positivity కాదు. Practical way. 'I'm the kind of person who always fails at this' అని story చెప్తే — every difficult moment confirms that story. Self-fulfilling అవుతుంది. But if story shifts to 'I'm building a new pattern and that takes time' — difficult moments failures లా feel అవ్వవు, normal parts of the process లా feel అవుతాయి. And {angle} is the specific moment where that shift happened for me.",
      "{topic} long-term work చేసిన detail — doing యొక్క content కాదు. How I defined success. 'Doing this perfectly and seeing results quickly' గా define చేశాను. Changed to 'doing this consistently and measuring over months, not days'. That single reframe — {angle} — changed everything. Suddenly succeeding almost every day, even when not perfect. And that feeling of succeeding is what keeps you going."]),

    ("Being Honest", "4:00 – 4:30",
     ["Quiet. Honest thing చెప్పండి.",
      "Long conversation చివర real thing చెప్పినట్టు."],
     ["And honest part of all of this — I still don't have it perfectly sorted. Some days significantly better than others. Some weeks completely drop the thread. Before feel bad about it. Like change wasn't real. కానీ నేను understand చేసుకున్నది — dropping and picking back up is just part of the process, not evidence that the process is failing. And that reframe is actually really important. Especially with {topic}.",
      "{topic} — version I have now — still a work in progress. Start చేసినప్పుడు అనుకున్నట్టు look అవట్లేదు. Some parts better than expected. Some parts harder. Sorted version వచ్చే వరకు wait చేయడం stop చేశాను — because 'still in progress' version is actually the most useful one to hear. Because that's where most people are too."]),

    ("Ending", "4:30 – 5:00",
     ["Camera. Warm close.",
      "Good honest conversation end చేస్తున్నట్టు."],
     ["Anyway. {topic} గురించి real, honest version ఇది. Polished version కాదు — in-progress one. Something landed అయితే — which part అని comments లో చెప్పండి. Genuinely use చేస్తాను people ఏం more want చేస్తున్నారో understand చేసుకోవడానికి. ఇలాంటి honest conversations కావాలంటే subscribe చేయండి. See you in the next one.",
      "ఈ రోజు {topic} గురించి ఇంతే. Useful గా అనిపిస్తే like చేయండి. And comment లో చెప్పండి: {topic} గురించి right now మీరు honestly ఎక్కడ ఉన్నారు? I read everything. See you soon."]),
]

L_TE_LINES = [
    "Big change కి ముందు 'slightly off' period — honestly talk అవని part అది.",
    "{topic} — finished version కంటే progress లో different గా look అవుతుంది.",
    "మీరు work చేస్తున్న version ఎవరి version లాగా అయినా ఉండాల్సిన అవసరం లేదు.",
    "Small and sustainable almost always outlasts big and dramatic.",
    "{angle} — that specific shift made everything else easier.",
    "Thread drop చేసి pick back up చేయడం — process యొక్క part. Failure కాదు.",
    "Success అంటే ఏమిటో redefine చేయడం — harder try చేయడం కంటే more useful.",
    "I still don't have it perfectly sorted. And that's actually fine.",
    "Middle part — gradual, messy middle — అందులోనే most of the real work జరుగుతుంది.",
    "How you talk to yourself about this matters as much as what you actually do.",
    "Most people 'still figuring it out' phase లో ఉంటారు. It's the most normal phase.",
    "Progress announce అవ్వదు. Look back చేసినప్పుడు notice అవుతుంది.",
]

NO_FACE_OPTS = {
    "personal": [
        [("Scene 1","Hands on table. Cup of tea in frame. Voice only."),
         ("Scene 2","B-roll — desk, window, ceiling fan, street view outside."),
         ("Scene 3","Walking shot from behind. Or just your feet on the floor."),
         ("Scene 4","Looking out a window. Or sitting against a wall. Silhouette works."),
         ("Scene 5","Hold the silence. Just a still visual — sky, plants, light through curtains."),
         ("Scene 6","Back to Scene 1 setup. Voice over. No face needed at all.")],
        [("Scene 1","Phone propped on a surface. Just your voice. Hands in frame if you want."),
         ("Scene 2","B-roll of your room, kitchen, or wherever you're sitting right now."),
         ("Scene 3","Close-up of your hands. Or a slow walking shot from the knees down."),
         ("Scene 4","An open notebook on the table. Nothing has to be written in it."),
         ("Scene 5","One still shot of something in your space — a cup, a plant, light coming in."),
         ("Scene 6","Voice over any slow b-roll. Simple. Clean. No face.")],
    ],
    "news": [
        [("Scene 1","Sit at a desk. Hands visible. Voice only — no face needed."),
         ("Scene 2","Slow pan of a newspaper, phone screen showing headlines, or a map."),
         ("Scene 3","Walking shot outdoors or in a corridor. Voice over the footage."),
         ("Scene 4","A window view. City street or sky. Simple and neutral."),
         ("Scene 5","Hold on a still image or graphic — just ambient sound underneath."),
         ("Scene 6","Back to desk setup. Simple close. Same visual as Scene 1.")],
        [("Scene 1","Phone propped up. Just your voice and your hands gesturing."),
         ("Scene 2","B-roll of any public space — street, market, office exterior."),
         ("Scene 3","Close-up on hands flipping through content or pointing at a screen."),
         ("Scene 4","Overhead shot of a desk with notes, a pen, a cup. No face needed."),
         ("Scene 5","Pause on a still visual — clouds, traffic, a quiet room."),
         ("Scene 6","Voice over any slow, neutral footage. Clean close. No face.")],
    ],
    "tech": [
        [("Scene 1","Laptop or phone screen in frame. Your hands typing or swiping. Voice only."),
         ("Scene 2","Close-up of a screen showing relevant content. Slow zoom."),
         ("Scene 3","Hands gesturing over a desk — notebook, device, pen. B-roll."),
         ("Scene 4","Screen recording or app walkthrough — no face, just narration."),
         ("Scene 5","Still shot of a device on a clean surface. Ambient sound only."),
         ("Scene 6","Back to Scene 1. Hands on keyboard. Close with voice over.")],
        [("Scene 1","Phone or tablet propped up. Voice narrating. Screen visible if relevant."),
         ("Scene 2","Slow pan across a clean desk setup — monitor, keyboard, notebook."),
         ("Scene 3","Hands pointing at or scrolling through relevant UI or interface."),
         ("Scene 4","Overhead desk shot with device in frame. Clean and minimal."),
         ("Scene 5","One still — a glowing screen in a dark room. No face needed."),
         ("Scene 6","Voice over a slow pan of any tech surface. Simple and clean.")],
    ],
    "fitness": [
        [("Scene 1","Standing shot — waist down showing shoes or workout gear. Voice only."),
         ("Scene 2","B-roll of workout space — mat, weights, shoes lined up."),
         ("Scene 3","Slow walking shot outdoors. Feet on pavement or trail. Voice over."),
         ("Scene 4","Hands holding a water bottle or writing in a journal. Close-up."),
         ("Scene 5","Still shot of workout gear laid out flat. Calm. No movement."),
         ("Scene 6","Back to Scene 1 setup. Simple close. No face at all.")],
        [("Scene 1","Phone propped at gym or at home. Hands in frame. Voice only."),
         ("Scene 2","Close-up B-roll — lacing shoes, adjusting gear, pouring water."),
         ("Scene 3","Outdoor walking or running shot from behind. No face."),
         ("Scene 4","Overhead shot of a journal, meal prep, or workout plan."),
         ("Scene 5","One still — a mat, a pair of shoes, a sunrise. Quiet."),
         ("Scene 6","Voice over any calm b-roll. Warm and grounded close.")],
    ],
    "lifestyle": [
        [("Scene 1","Morning table setup — coffee, journal, phone face down. Voice only."),
         ("Scene 2","B-roll of your space — shelves, a tidy corner, light through a window."),
         ("Scene 3","Hands doing something intentional — writing, making tea, folding."),
         ("Scene 4","Walking shot through your home or outside. Just the ambience."),
         ("Scene 5","A still — open book, a plant, a candle. Quiet and warm."),
         ("Scene 6","Back to morning table. Voice over. Simple, warm close.")],
        [("Scene 1","Slow pan of a minimal, tidy space. Voice narrating over it."),
         ("Scene 2","Close-up of hands doing something calm — journal, coffee, phone."),
         ("Scene 3","Window light falling on a surface. Slow zoom. Ambient sound."),
         ("Scene 4","Overhead shot of a flat-lay — items from your daily routine."),
         ("Scene 5","One still visual with natural light. No face needed at all."),
         ("Scene 6","Voice over a slow pan of your space. Warm close. Simple.")],
    ],
}

def generate_confidence(bank):
    return {
        "personal": [
            {"label": "Hook Strength",        "value": "High — relatable from the first sentence"},
            {"label": "Engagement Potential", "value": "Very High — personal topics drive comments"},
            {"label": "Content Safety",       "value": "High — no controversy, just honest feelings"},
            {"label": "Growth Potential",     "value": "Strong — repeat viewers who feel understood"},
        ],
        "news": [
            {"label": "Hook Strength",        "value": "High — current topic, clear angle"},
            {"label": "Engagement Potential", "value": "High — people share news breakdowns"},
            {"label": "Content Safety",       "value": "High — informative, not inflammatory"},
            {"label": "Growth Potential",     "value": "Strong — news drives discoverability"},
        ],
        "tech": [
            {"label": "Hook Strength",        "value": "High — tech curiosity is universal"},
            {"label": "Engagement Potential", "value": "Very High — tech audiences are active"},
            {"label": "Content Safety",       "value": "Very High — factual and balanced"},
            {"label": "Growth Potential",     "value": "Very Strong — evergreen + trending mix"},
        ],
        "fitness": [
            {"label": "Hook Strength",        "value": "High — relatable journey framing"},
            {"label": "Engagement Potential", "value": "Very High — community-driven niche"},
            {"label": "Content Safety",       "value": "Very High — positive, no controversy"},
            {"label": "Growth Potential",     "value": "Very Strong — loyal repeat audience"},
        ],
        "lifestyle": [
            {"label": "Hook Strength",        "value": "High — 'real version' angle hooks fast"},
            {"label": "Engagement Potential", "value": "Very High — lifestyle drives saves & shares"},
            {"label": "Content Safety",       "value": "Very High — positive, aspirational tone"},
            {"label": "Growth Potential",     "value": "Very Strong — strong subscriber retention"},
        ],
    }.get(bank, [
        {"label": "Topic Clarity",     "value": "High — clear and specific"},
        {"label": "Script Difficulty", "value": "Easy — just talk naturally"},
        {"label": "Content Safety",    "value": "High — balanced and honest"},
        {"label": "Growth Potential",  "value": "Strong — engaging topic"},
    ])

# ═══════════════════════════════════════════════════════════════════════════════
#  NEWS FETCHING  (topic-specific, date-aware)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_news_for_topic(topic):
    today_str = date.today().strftime("%Y-%m-%d")
    query     = f"{topic} {today_str}"
    search_url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )
    fallback_feeds = [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "https://www.thehindu.com/news/feeder/default.rss",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    results = []

    try:
        r    = requests.get(search_url, headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item")[:10]:
            t = item.find("title")
            if t and t.text.strip():
                clean = re.split(r"\s+[-–|]\s+", t.text.strip())[0].strip()
                if len(clean) > 20:
                    results.append(clean)
            if len(results) >= 5:
                break
    except Exception as e:
        print(f"  ⚠️  Google News search error: {e}")

    # Fallback: scan general feeds by keyword
    if len(results) < 2:
        kw = [w for w in topic.lower().split() if len(w) > 3][:4]
        for url in fallback_feeds:
            try:
                r    = requests.get(url, headers=headers, timeout=8)
                soup = BeautifulSoup(r.text, "xml")
                for item in soup.find_all("item")[:30]:
                    t = item.find("title")
                    if t and t.text.strip() and any(k in t.text.lower() for k in kw):
                        clean = re.split(r"\s+[-–|]\s+", t.text.strip())[0].strip()
                        results.append(clean)
                    if len(results) >= 5:
                        break
            except Exception:
                continue
            if len(results) >= 5:
                break

    return results[:5]


def fetch_trending_topic():
    print("  🌐 Fetching today's trending topic...")
    today_str = date.today().strftime("%B %d %Y")
    try:
        url  = f"https://news.google.com/rss/search?q={quote_plus('India news '+today_str)}&hl=en-IN&gl=IN&ceid=IN:en"
        r    = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        if items:
            raw   = items[0].find("title").text.strip()
            clean = re.split(r"\s+[-–|]\s+", raw)[0].strip()
            print(f"  ✅ Topic: {clean[:70]}")
            return clean
    except Exception:
        pass
    fb = random.choice([
        "feeling stuck doing the same thing every single day",
        "trying to save money but always finding a reason to spend",
        "overthinking at 2am when everything is quiet",
        "waking up late and the whole day feeling off",
    ])
    print(f"  ℹ️  Fallback: {fb}")
    return fb

# ── History & angle ────────────────────────────────────────────────────────────
def load_history():
    if HISTORY.exists():
        try:
            return _json.loads(HISTORY.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_to_history(topic, angle, user_input):
    h = load_history()
    h.append({"date": TODAY, "input": user_input, "topic": topic, "angle": angle})
    HISTORY.write_text(_json.dumps(h[-50:], indent=2, ensure_ascii=False), encoding="utf-8")

_ANGLE_POOLS = {
    "personal":  None,   # resolved per-cat from PERSONAL_ANGLES
    "news":      NEWS_ANGLES,
    "tech":      TECH_ANGLES,
    "fitness":   FIT_ANGLES,
    "lifestyle": LIFE_ANGLES,
}

def get_angle(topic, cat, history):
    used  = {e["angle"] for e in history if e.get("topic","").lower()==topic.lower()}
    bank  = cat_to_bank(cat)
    pool  = PERSONAL_ANGLES.get(cat, NEWS_ANGLES) if bank == "personal" else _ANGLE_POOLS.get(bank, NEWS_ANGLES)
    avail = [a for a in pool if a not in used] or pool
    return random.choice(avail)

# ── Script generation ──────────────────────────────────────────────────────────
def _fmt(s, topic, angle, news_ctx):
    s = s.replace("{topic}", topic).replace("{angle}", angle).replace("{TODAY}", TODAY)
    for i, n in enumerate(news_ctx):
        s = s.replace(f"{{news{i}}}", n)
    s = re.sub(r"\{news\d+\}", f"the situation around {topic}", s)
    return s

def _build_scenes(banks, topic, angle, news_ctx):
    scenes = []
    for name, time, dirs, dlgs in banks:
        scenes.append({
            "name":      name,
            "time":      time,
            "direction": random.choice(dirs),
            "dialogue":  _fmt(random.choice(dlgs), topic, angle, news_ctx),
        })
    return scenes

def _pick_lines(pool, topic, angle, news_ctx, n=10):
    raw = random.sample(pool, min(n, len(pool)))
    return [_fmt(l, topic, angle, news_ctx) for l in raw]

def _title(topic, cat, lang):
    t    = topic.title()
    bank = cat_to_bank(cat)
    titles = {
        "personal": {
            "English": [f"That Feeling Of {t}", f"Let's Just Talk About {t}",
                        f"Why {t} Hits Different", f"Can We Be Honest About {t}", f"Real Talk: {t}"],
            "Tamil":   [f"{t} Pathi Pesalama?", f"Real-Aga Sollanum: {t}",
                        f"{t} — Naan Sollanumna Intha Vishayam"],
            "Telugu":  [f"{t} Gurinchi Matladadam", f"Real Talk: {t}", f"Honest గా చెప్పాలంటే: {t}"],
        },
        "news": {
            "English": [f"My Honest Take On {t}", f"Let's Talk About {t} Simply",
                        f"What's Really Happening With {t}", f"A Regular Person's View On {t}",
                        f"{t} — Explained Simply"],
            "Tamil":   [f"{t} Pathi En Honest Take", f"Simply Pesalama: {t}",
                        f"{t} — Normal Person-oda View", f"Naan Paakuradhu: {t}"],
            "Telugu":  [f"{t} Gurinchi Naa Honest Take", f"Simply Matladadam: {t}",
                        f"{t} — Normal Person View", f"నా చూపు: {t}"],
        },
        "tech": {
            "English": [f"{t} — What It Actually Means For You", f"Let's Actually Understand {t}",
                        f"{t} Simply Explained", f"The Honest Truth About {t}",
                        f"{t} — Beyond The Hype"],
            "Tamil":   [f"{t} — Actually என்னன்னு பாக்கலாம்", f"Simply புரியும்: {t}",
                        f"{t} — Hype இல்ல, Real பாக்கலாம்"],
            "Telugu":  [f"{t} — నిజంగా అర్థం చేసుకుందాం", f"Simply అర్థమవుతుంది: {t}",
                        f"{t} — Hype కాదు, Real గా చూద్దాం"],
        },
        "fitness": {
            "English": [f"The Honest Truth About {t}", f"What {t} Actually Looks Like",
                        f"{t} — The Real Version", f"My Honest Journey With {t}",
                        f"{t} — What Nobody Tells You First"],
            "Tamil":   [f"{t} — Real-ஆ என்னன்னு பாக்கலாம்", f"Honest-ஆ சொல்றேன்: {t}",
                        f"{t} — யாரும் சொல்லாத விஷயம்"],
            "Telugu":  [f"{t} — నిజంగా ఎలా ఉంటుందో చూద్దాం", f"Honest గా చెప్తాను: {t}",
                        f"{t} — ఎవరూ చెప్పని విషయం"],
        },
        "lifestyle": {
            "English": [f"My Honest Version Of {t}", f"What {t} Actually Looks Like In Progress",
                        f"{t} — The Real Story", f"Still Figuring Out {t}",
                        f"{t} — Not The Highlight Reel"],
            "Tamil":   [f"{t} — En Real Version", f"Honest-ஆ: {t}",
                        f"{t} — Highlight Reel இல்ல"],
            "Telugu":  [f"{t} — నా Real Version", f"Honest గా: {t}",
                        f"{t} — Highlight Reel కాదు"],
        },
    }
    opts = titles.get(bank, titles["news"])
    return random.choice(opts.get(lang, opts["English"]))

_SCENE_BANKS = {
    "personal": {"English": P_EN_SCENES, "Tamil": P_TA_SCENES, "Telugu": P_TE_SCENES},
    "news":     {"English": N_EN_SCENES, "Tamil": N_TA_SCENES, "Telugu": N_TE_SCENES},
    "tech":     {"English": T_EN_SCENES, "Tamil": T_TA_SCENES, "Telugu": T_TE_SCENES},
    "fitness":  {"English": F_EN_SCENES, "Tamil": F_TA_SCENES, "Telugu": F_TE_SCENES},
    "lifestyle":{"English": L_EN_SCENES, "Tamil": L_TA_SCENES, "Telugu": L_TE_SCENES},
}
_HOOK_BANKS = {
    "personal": {"English": P_EN_HOOKS, "Tamil": P_TA_HOOKS, "Telugu": P_TE_HOOKS},
    "news":     {"English": N_EN_HOOKS, "Tamil": N_TA_HOOKS, "Telugu": N_TE_HOOKS},
    "tech":     {"English": T_EN_HOOKS, "Tamil": T_TA_HOOKS, "Telugu": T_TE_HOOKS},
    "fitness":  {"English": F_EN_HOOKS, "Tamil": F_TA_HOOKS, "Telugu": F_TE_HOOKS},
    "lifestyle":{"English": L_EN_HOOKS, "Tamil": L_TA_HOOKS, "Telugu": L_TE_HOOKS},
}
_LINE_BANKS = {
    "personal": {"English": P_EN_LINES, "Tamil": P_TA_LINES, "Telugu": P_TE_LINES},
    "news":     {"English": N_EN_LINES, "Tamil": N_TA_LINES, "Telugu": N_TE_LINES},
    "tech":     {"English": T_EN_LINES, "Tamil": T_TA_LINES, "Telugu": T_TE_LINES},
    "fitness":  {"English": F_EN_LINES, "Tamil": F_TA_LINES, "Telugu": F_TE_LINES},
    "lifestyle":{"English": L_EN_LINES, "Tamil": L_TA_LINES, "Telugu": L_TE_LINES},
}

def generate_language_data(topic, angle, cat, news_ctx, lang):
    bank = cat_to_bank(cat)
    scenes = _SCENE_BANKS.get(bank, _SCENE_BANKS["news"])[lang]
    hooks  = _HOOK_BANKS.get(bank,  _HOOK_BANKS["news"])[lang]
    lpool  = _LINE_BANKS.get(bank,  _LINE_BANKS["news"])[lang]
    nf_opt = random.choice(NO_FACE_OPTS.get(bank, NO_FACE_OPTS["news"]))
    return {
        "title":         _title(topic, cat, lang),
        "hook":          _fmt(random.choice(hooks), topic, angle, news_ctx),
        "scenes":        _build_scenes(scenes, topic, angle, news_ctx),
        "talking_lines": _pick_lines(lpool, topic, angle, news_ctx),
        "no_face":       [{"scene":sc,"tip":tip} for sc,tip in nf_opt],
    }

def generate_seo(topic, angle, cat, news_ctx):
    t   = topic.title()
    bank= cat_to_bank(cat)
    n0  = news_ctx[0] if news_ctx else topic

    title_opts = {
        "personal":  [f"Why {t} Is More Common Than You Think",
                      f"Let's Be Honest About {t}",
                      f"The Real Side Of {t} Nobody Talks About"],
        "news":      [f"{t} Simply Explained — What It Means For You",
                      f"Understanding {t}: A Regular Person's Take",
                      f"{t} — The Part That Actually Matters"],
        "tech":      [f"{t} Explained Simply — What You Actually Need To Know",
                      f"Is {t} Really That Big A Deal? My Honest Take",
                      f"{t} — Beyond The Hype"],
        "fitness":   [f"What {t} Actually Looks Like In Real Life",
                      f"The Honest Truth About {t} Nobody Tells You",
                      f"{t} — The Sustainable Version"],
        "lifestyle": [f"My Honest Experience With {t}",
                      f"{t} — The Real Version, Not The Highlight Reel",
                      f"What {t} Actually Changed For Me"],
    }.get(bank, [f"My Take On {t}", f"Let's Talk About {t}", f"Understanding {t}"])

    comment_q = {
        "personal":  f"Have you ever felt this way about {topic}? Drop your experience below — I read every comment.",
        "news":      f"What's your take on {topic}? Is there a part of the story you think is being missed? Let me know below.",
        "tech":      f"Have you actually tried {topic} yet? What was your experience? Tell me in the comments.",
        "fitness":   f"Where are you at with {topic} right now? Starting out, in the middle, or restarting? Comment below.",
        "lifestyle": f"What does {topic} honestly look like for you right now? I'd love to hear your real version.",
    }.get(bank, f"What do you think about {topic}? Leave your thoughts below.")

    tags_map = {
        "personal":  [topic, angle, "mental health", "self improvement", "honest talk",
                      "personal growth", "real talk", "relatable", "daily life", "mindset",
                      "emotional health", "life advice", "authentic content", "feelings", "wellbeing"],
        "news":      [topic, "news explained", "current events", "world news", n0[:40],
                      "news breakdown", "simple explanation", "regular person", "honest take",
                      "India news", "global news", "news analysis", "what's happening", "updates", "explained"],
        "tech":      [topic, "tech explained", "technology", "tech news", "AI", "gadgets",
                      "tech for beginners", "simple tech", "honest tech review", "tech breakdown",
                      "digital life", "future tech", "tech tips", "innovation", "tech update"],
        "fitness":   [topic, "fitness journey", "workout tips", "healthy lifestyle", "real fitness",
                      "fitness motivation", "gym tips", "health and fitness", "beginner fitness",
                      "sustainable fitness", "fitness advice", "exercise", "fitness goals", "wellness", "body health"],
        "lifestyle": [topic, "lifestyle", "daily routine", "self care", "lifestyle tips",
                      "minimalism", "productivity", "honest lifestyle", "real life", "morning routine",
                      "life tips", "personal development", "lifestyle change", "habits", "slow living"],
    }.get(bank, [topic, "explained", "honest take"])

    hashtags = {
        "personal":  ["#RealTalk", "#MentalHealth", "#SelfImprovement", "#HonestConversation",
                      "#PersonalGrowth", "#Relatable", "#DailyLife", "#Wellbeing"],
        "news":      ["#NewsExplained", "#CurrentEvents", "#WorldNews", "#HonestTake",
                      "#SimpleExplanation", "#StayInformed", "#IndiaNews", "#NewsBreakdown"],
        "tech":      ["#TechExplained", "#Technology", "#TechNews", "#AIExplained",
                      "#TechForEveryone", "#Innovation", "#DigitalLife", "#TechTips"],
        "fitness":   ["#FitnessJourney", "#RealFitness", "#HealthyLifestyle", "#WorkoutMotivation",
                      "#FitnessTips", "#SustainableFitness", "#GymLife", "#HealthAndFitness"],
        "lifestyle": ["#Lifestyle", "#DailyRoutine", "#SelfCare", "#LifestyleTips",
                      "#PersonalDevelopment", "#Minimalism", "#Productivity", "#SlowLiving"],
    }.get(bank, ["#Explained", "#HonestTake", "#Relatable"])

    thumbnail = {
        "personal":  f'\"{t}\" — are you feeling this too?',
        "news":      f"What {t} actually means for YOU",
        "tech":      f"Is {t} really worth it? (honest answer)",
        "fitness":   f"The REAL side of {t}",
        "lifestyle": f"My honest {t} update (not a highlight reel)",
    }.get(bank, f"My honest take on {t}")

    desc_start = (
        f"In this video I'm talking about {topic} — not the expert version, "
        f"not the headline version, just an honest, straightforward conversation "
        f"about {angle}. If you've been looking for a simple, real take on this — this is it.\n\n"
        f"00:00 Hook\n00:30 What's actually happening\n01:30 Why it matters\n"
        f"03:00 My honest take\n04:00 Key takeaway\n04:30 Wrap up\n\n"
        f"Drop a comment below — {comment_q}"
    )

    return {
        "title_options":   title_opts,
        "comment_question": comment_q,
        "tags":            tags_map[:15],
        "hashtags":        hashtags[:8],
        "thumbnail_text":  thumbnail,
        "description_start": desc_start,
    }

def generate_structured(topic, angle, cat, news_ctx, default_lang="English"):
    return {
        "meta": {
            "topic":        topic,
            "angle":        angle,
            "date":         TODAY,
            "generated_at": datetime.now().isoformat(),
            "category":     cat,
            "news_context": news_ctx,
            "default_lang": default_lang,
        },
        "confidence": generate_confidence(cat_to_bank(cat)),
        "seo": generate_seo(topic, angle, cat, news_ctx),
        "languages": {
            "English": generate_language_data(topic, angle, cat, news_ctx, "English"),
            "Tamil":   generate_language_data(topic, angle, cat, news_ctx, "Tamil"),
            "Telugu":  generate_language_data(topic, angle, cat, news_ctx, "Telugu"),
        }
    }

def save_data(data):
    SCRIPT_JSON.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    m  = data["meta"]
    en = data["languages"]["English"]
    md = [f"# {en['title']}",
          f"\n**Topic:** {m['topic']}  |  **Angle:** {m['angle']}  |  **Date:** {m['date']}\n",
          f"**Hook:** {en['hook']}\n", "---"]
    for s in en["scenes"]:
        md += [f"\n## {s['name']}  `{s['time']}`", f"*{s['direction']}*",
               f"\n{s['dialogue']}\n"]
    SCRIPT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"  ✅ Saved → {SCRIPT_JSON.name}")

def read_json():
    if SCRIPT_JSON.exists():
        try:
            return _json.loads(SCRIPT_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _parse_lang(raw):
    r = (raw or "").strip().lower()
    if r in ("ta","tamil"):  return "Tamil"
    if r in ("te","telugu"): return "Telugu"
    return "English"

# ═══════════════════════════════════════════════════════════════════════════════
#  EMBEDDED HTML
# ═══════════════════════════════════════════════════════════════════════════════

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Script Viewer</title>
<style>
:root{--bg:#0f0f0f;--sb:#141414;--card:#1c1c1c;--card2:#232323;
  --acc:#e84040;--acc2:#c03030;--txt:#f0f0f0;--dim:#888;--bdr:#2a2a2a;--grn:#22c55e;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  height:100vh;display:flex;flex-direction:column;overflow:hidden;}
.hdr{display:flex;align-items:center;justify-content:space-between;
  padding:13px 24px;border-bottom:1px solid var(--bdr);flex-shrink:0;}
.hdr-l{display:flex;align-items:center;gap:14px;}
.logo{font-size:12px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:var(--acc);}
.logo::before{content:'▶ ';}
.sub{color:var(--dim);font-size:12px;border-left:1px solid var(--bdr);padding-left:14px;}
.hdr-r{display:flex;gap:6px;}
.lb{background:transparent;border:1px solid var(--bdr);color:var(--dim);
  padding:5px 14px;border-radius:20px;font-size:12px;cursor:pointer;transition:.15s;}
.lb:hover{border-color:var(--acc);color:var(--acc);}
.lb.on{background:var(--acc);border-color:var(--acc);color:#fff;}
.layout{display:flex;flex:1;overflow:hidden;}
.sb{width:252px;background:var(--sb);border-right:1px solid var(--bdr);
  overflow-y:auto;flex-shrink:0;display:flex;flex-direction:column;}
.gen-box{padding:14px;border-bottom:1px solid var(--bdr);}
.gi{width:100%;background:var(--card);border:1px solid var(--bdr);color:var(--txt);
  padding:8px 10px;border-radius:7px;font-size:12px;margin-bottom:8px;outline:none;}
.gi:focus{border-color:var(--acc);}
.gi::placeholder{color:var(--dim);}
.gb{width:100%;background:var(--acc);border:none;color:#fff;
  padding:9px;border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;transition:.15s;}
.gb:hover{background:var(--acc2);}
.gb:disabled{opacity:.5;cursor:not-allowed;}
.sb-lbl{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;
  color:var(--dim);padding:18px 14px 8px;}
.vi{padding:11px 14px;cursor:pointer;border-radius:6px;margin:2px 8px;transition:.15s;}
.vi:hover{background:var(--card);}
.vi.on{background:var(--card);border-left:3px solid var(--acc);padding-left:11px;}
.vt{font-size:13px;font-weight:500;line-height:1.4;margin-bottom:3px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.vm{font-size:11px;color:var(--dim);}
.main{flex:1;overflow-y:auto;padding:28px 36px;}
.badge{display:inline-flex;align-items:center;gap:6px;background:var(--acc);
  color:#fff;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
  padding:4px 10px;border-radius:20px;margin-bottom:12px;}
.badge::before{content:'▶';font-size:8px;}
.mtitle{font-size:24px;font-weight:700;line-height:1.35;margin-bottom:20px;max-width:820px;}
.tabs{display:flex;border-bottom:1px solid var(--bdr);margin-bottom:26px;gap:0;}
.tab{padding:10px 18px;font-size:13px;font-weight:500;color:var(--dim);
  cursor:pointer;border-bottom:2px solid transparent;transition:.15s;white-space:nowrap;}
.tab:hover{color:var(--txt);}
.tab.on{color:var(--txt);border-bottom-color:var(--acc);}
.tc{display:none;} .tc.on{display:block;}
.chap{background:var(--card);border:1px solid var(--bdr);border-radius:10px;
  padding:18px 20px;margin-bottom:26px;max-width:680px;}
.chap-h{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;
  color:var(--dim);margin-bottom:14px;}
.cr{display:flex;align-items:center;gap:18px;padding:5px 0;}
.ct{font-size:13px;font-weight:700;color:var(--acc);min-width:42px;}
.cn{font-size:13px;}
.sg-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;}
.sg-ttl{font-size:15px;font-weight:600;}
.sg-cnt{font-size:12px;color:var(--dim);}
.progress{height:3px;background:var(--bdr);border-radius:2px;margin-bottom:14px;}
.progress-bar{height:100%;background:var(--acc);border-radius:2px;transition:width .3s;}
.dots{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap;}
.dot{width:36px;height:36px;border-radius:50%;background:var(--card);
  border:1px solid var(--bdr);display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:600;color:var(--dim);cursor:pointer;transition:.15s;}
.dot:hover{border-color:var(--acc);color:var(--acc);}
.dot.on{background:var(--acc);border-color:var(--acc);color:#fff;}
.scard{background:var(--card);border:1px solid var(--bdr);border-radius:12px;
  overflow:hidden;max-width:820px;}
.sc-hdr{display:flex;align-items:center;justify-content:space-between;
  padding:15px 20px;border-bottom:1px solid var(--bdr);}
.sc-tag{display:flex;align-items:center;gap:10px;}
.sc-num{width:28px;height:28px;border-radius:50%;background:var(--acc);
  color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;}
.sc-name{font-size:14px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;}
.sc-time{font-size:12px;color:var(--acc);font-weight:600;}
.sc-sec{padding:18px 22px;}
.sc-sec+.sc-sec{border-top:1px solid var(--bdr);}
.slbl{font-size:10px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;
  color:var(--dim);margin-bottom:10px;}
.sdir{font-size:13px;color:var(--dim);line-height:1.75;}
.sdlg{font-size:16px;line-height:1.9;color:var(--txt);}
.sc-nav{display:flex;align-items:center;justify-content:space-between;
  padding:13px 20px;border-top:1px solid var(--bdr);}
.nbtn{background:transparent;border:1px solid var(--bdr);color:var(--txt);
  padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer;transition:.15s;}
.nbtn:hover{border-color:var(--acc);color:var(--acc);}
.nbtn:disabled{opacity:.3;cursor:not-allowed;}
.nbtn:disabled:hover{border-color:var(--bdr);color:var(--txt);}
.cbtn{background:transparent;border:1px solid var(--acc);color:var(--acc);
  padding:8px 16px;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;transition:.15s;}
.cbtn:hover{background:var(--acc);color:#fff;}
.lines{display:flex;flex-direction:column;gap:10px;max-width:780px;}
.li{background:var(--card);border:1px solid var(--bdr);border-left:3px solid var(--acc);
  border-radius:8px;padding:15px 18px;font-size:15px;line-height:1.75;cursor:pointer;transition:.15s;}
.li:hover{background:var(--card2);}
.nf{background:var(--card);border:1px solid var(--bdr);border-radius:10px;
  padding:20px;max-width:720px;}
.nf-row{display:flex;gap:14px;padding:10px 0;border-bottom:1px solid var(--bdr);}
.nf-row:last-child{border-bottom:none;}
.nf-sc{font-size:12px;font-weight:700;color:var(--acc);min-width:64px;}
.nf-txt{font-size:13px;line-height:1.7;}
.ov-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:820px;margin-bottom:18px;}
.ic{background:var(--card);border:1px solid var(--bdr);border-radius:10px;padding:15px 18px;}
.il{font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:var(--dim);margin-bottom:8px;}
.iv{font-size:15px;font-weight:500;line-height:1.5;}
.hook-c{background:var(--card);border:1px solid var(--bdr);border-left:3px solid var(--acc);
  border-radius:10px;padding:20px 22px;max-width:820px;margin-bottom:18px;}
.news-c{background:var(--card);border:1px solid var(--bdr);border-radius:10px;
  padding:16px 18px;max-width:820px;}
.ni{font-size:13px;color:var(--dim);padding:8px 0;border-bottom:1px solid var(--bdr);line-height:1.6;}
.ni:last-child{border-bottom:none;}
.conf-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:620px;}
.ci{background:var(--card);border:1px solid var(--bdr);border-radius:8px;padding:15px 18px;}
.cl{font-size:11px;color:var(--dim);margin-bottom:6px;}
.cv{font-size:14px;font-weight:600;color:var(--grn);}
.updated-bar{background:#22c55e18;border:1px solid #22c55e44;border-radius:8px;
  padding:10px 16px;font-size:13px;color:var(--grn);margin-bottom:20px;max-width:820px;
  display:none;align-items:center;gap:8px;}
.updated-bar.show{display:flex;}
.empty{text-align:center;padding:80px 20px;color:var(--dim);}
.empty h3{font-size:18px;margin-bottom:8px;color:var(--txt);}
.empty p{font-size:14px;line-height:1.7;}
.spin{display:inline-block;width:13px;height:13px;border:2px solid rgba(255,255,255,.3);
  border-top-color:#fff;border-radius:50%;animation:sp .7s linear infinite;
  vertical-align:middle;margin-right:6px;}
@keyframes sp{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:22px;right:22px;background:var(--grn);color:#fff;
  padding:10px 16px;border-radius:8px;font-size:13px;font-weight:500;
  opacity:0;transform:translateY(8px);transition:.25s;pointer-events:none;z-index:999;}
.toast.show{opacity:1;transform:translateY(0);}
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--bdr);border-radius:3px;}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-l">
    <div class="logo">Content Generator</div>
    <div class="sub" id="hdr-date">Script Viewer</div>
  </div>
  <div class="hdr-r">
    <button class="lb on" onclick="setLang('English')">EN</button>
    <button class="lb"    onclick="setLang('Tamil')">TA</button>
    <button class="lb"    onclick="setLang('Telugu')">TE</button>
  </div>
</div>

<div class="layout">
  <div class="sb">
    <div class="gen-box">
      <input class="gi" id="ti" placeholder="Topic… (empty = trending)"
             onkeydown="if(event.key==='Enter')gen()">
      <button class="gb" id="gb" onclick="gen()">▶ Generate Script</button>
    </div>
    <div class="sb-lbl">Current Script</div>
    <div id="sb-list"></div>
  </div>
  <div class="main" id="main">
    <div class="empty">
      <h3>Loading…</h3>
      <p>Fetching your script.</p>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
let D=null, lang='English', scene=0, _lastGen=null;

window.addEventListener('load', loadScript);

async function loadScript(){
  try{
    const r = await fetch('/api/script?t='+Date.now());
    const d = await r.json();
    if(d && d.meta){
      D=d; _lastGen=d.meta.generated_at||null;
      lang=d.meta.default_lang||'English';
      syncLangBtns(); render(false);
    } else {
      document.getElementById('main').innerHTML=
        '<div class="empty"><h3>No script yet</h3><p>Enter a topic and click Generate.</p></div>';
    }
  }catch(e){
    document.getElementById('main').innerHTML=
      '<div class="empty"><h3>Loading…</h3><p>Script will appear here.</p></div>';
  }
}

// Poll every 1.5s — re-render on new generated_at
setInterval(async()=>{
  try{
    const r = await fetch('/api/script?t='+Date.now());
    const d = await r.json();
    if(!d||!d.meta) return;
    const g = d.meta.generated_at||null;
    if(g && g!==_lastGen){
      _lastGen=g; D=d; scene=0;
      lang=d.meta.default_lang||lang;
      syncLangBtns(); render(true);
    }
  }catch(e){}
}, 1500);

async function gen(){
  const btn=document.getElementById('gb');
  const topic=document.getElementById('ti').value.trim();
  btn.disabled=true; btn.innerHTML='<span class="spin"></span>Generating…';
  try{
    const r=await fetch('/api/generate',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({topic,lang})
    });
    const d=await r.json();
    if(d&&d.meta){D=d;scene=0;_lastGen=d.meta.generated_at||null;render(true);toast('✅ Script generated!');}
    else toast('Error generating',1);
  }catch(e){toast('Error: '+e.message,1);}
  btn.disabled=false; btn.innerHTML='▶ Generate Script';
}

function setLang(l){lang=l;scene=0;syncLangBtns();render(false);}

function syncLangBtns(){
  const m={'English':'EN','Tamil':'TA','Telugu':'TE'};
  document.querySelectorAll('.lb').forEach(b=>b.classList.toggle('on',b.textContent===m[lang]));
}

function render(isNew){
  if(!D) return;
  const m=D.meta, L=D.languages[lang];
  document.getElementById('hdr-date').textContent='Script Viewer — '+m.date;
  document.getElementById('sb-list').innerHTML=`
    <div class="vi on">
      <div class="vt">${esc(L.title)}</div>
      <div class="vm">${esc(m.date)} · ${esc(m.category)}</div>
    </div>`;
  const cat=(m.category||'topic').replace(/_/g,' ').toUpperCase();
  const updBar=isNew?`<div class="updated-bar show">✅ Script updated — ${esc(m.topic)}</div>`:'';
  document.getElementById('main').innerHTML=`
    ${updBar}
    <div class="badge">${cat}</div>
    <div class="mtitle">${esc(L.title)}</div>
    <div class="tabs">
      <div class="tab on" onclick="tab(this,'t-script')">Script</div>
      <div class="tab" onclick="tab(this,'t-over')">Overview</div>
      <div class="tab" onclick="tab(this,'t-lines')">Easy Lines</div>
      <div class="tab" onclick="tab(this,'t-noface')">No-Face</div>
      <div class="tab" onclick="tab(this,'t-conf')">Confidence</div>
      <div class="tab" onclick="tab(this,'t-seo')">SEO</div>
    </div>
    <div id="t-script" class="tc on">${scriptTab(L)}</div>
    <div id="t-over"   class="tc">${overTab(m,L)}</div>
    <div id="t-lines"  class="tc">${linesTab(L)}</div>
    <div id="t-noface" class="tc">${nofaceTab(L)}</div>
    <div id="t-conf"   class="tc">${confTab(D.confidence)}</div>
    <div id="t-seo"    class="tc">${seoTab(D.seo)}</div>`;
  if(isNew) setTimeout(()=>{
    const b=document.querySelector('.updated-bar');
    if(b) b.style.opacity='0';
  },4000);
}

function scriptTab(L){
  const rows=L.scenes.map(s=>`
    <div class="cr">
      <span class="ct">${s.time.split('–')[0].trim()}</span>
      <span class="cn">${s.name.toUpperCase()}</span>
    </div>`).join('');
  const dots=L.scenes.map((_,i)=>
    `<div class="dot ${i===scene?'on':''}" onclick="goScene(${i})">${i+1}</div>`
  ).join('');
  const pct=((scene+1)/L.scenes.length*100).toFixed(0);
  const s=L.scenes[scene];
  return `
    <div class="chap">
      <div class="chap-h">⏱ YouTube Chapters — Paste into Description</div>${rows}
    </div>
    <div class="sg-hdr">
      <div class="sg-ttl">Step-by-Step Scene Guide</div>
      <div class="sg-cnt">Scene ${scene+1} of ${L.scenes.length}</div>
    </div>
    <div class="progress"><div class="progress-bar" style="width:${pct}%"></div></div>
    <div class="dots">${dots}</div>
    <div class="scard">
      <div class="sc-hdr">
        <div class="sc-tag">
          <div class="sc-num">${scene+1}</div>
          <div class="sc-name">${esc(s.name)}</div>
        </div>
        <div class="sc-time">${esc(s.time)}</div>
      </div>
      <div class="sc-sec">
        <div class="slbl">📷 What to Film</div>
        <div class="sdir">${esc(s.direction)}</div>
      </div>
      <div class="sc-sec">
        <div class="slbl">✏️ Say This</div>
        <div class="sdlg">${esc(s.dialogue)}</div>
      </div>
      <div class="sc-nav">
        <button class="nbtn" onclick="goScene(${scene-1})" ${scene===0?'disabled':''}>← Prev</button>
        <button class="cbtn" onclick="copyScene()">Copy Scene</button>
        <button class="nbtn" onclick="goScene(${scene+1})" ${scene===L.scenes.length-1?'disabled':''}>Next →</button>
      </div>
    </div>`;
}

function overTab(m,L){
  const news=m.news_context&&m.news_context.length
    ?`<div class="il" style="margin-top:20px;margin-bottom:10px;">📰 Real-World News Used</div>
      <div class="news-c">${m.news_context.map(n=>`<div class="ni">📰 ${esc(n)}</div>`).join('')}</div>`:''
  return `
    <div class="ov-grid">
      <div class="ic"><div class="il">Topic</div><div class="iv">${esc(m.topic)}</div></div>
      <div class="ic"><div class="il">Angle</div><div class="iv">${esc(m.angle)}</div></div>
      <div class="ic"><div class="il">Date</div><div class="iv">${esc(m.date)}</div></div>
      <div class="ic"><div class="il">Language</div><div class="iv">${esc(m.default_lang)}</div></div>
    </div>
    <div class="il" style="margin-bottom:10px;">🎯 Hook Line</div>
    <div class="hook-c">
      <div style="font-size:16px;line-height:1.85;font-style:italic;">"${esc(L.hook)}"</div>
    </div>${news}`;
}

function linesTab(L){
  return `
    <div style="margin-bottom:14px;font-size:13px;color:var(--dim);">
      Punchy lines to use while filming or as captions. Click any line to copy it.
    </div>
    <div class="lines">
      ${L.talking_lines.map(l=>`
        <div class="li" onclick="copyTxt(${JSON.stringify(l)})">"${esc(l)}"</div>
      `).join('')}
    </div>`;
}

function nofaceTab(L){
  return `
    <div style="margin-bottom:14px;font-size:13px;color:var(--dim);">
      No need to show your face. Here's how to film each scene without one:
    </div>
    <div class="nf">
      ${L.no_face.map(r=>`
        <div class="nf-row">
          <div class="nf-sc">${esc(r.scene)}</div>
          <div class="nf-txt">${esc(r.tip)}</div>
        </div>`).join('')}
    </div>`;
}

function confTab(conf){
  return `
    <div style="margin-bottom:16px;font-size:13px;color:var(--dim);">
      Before you hit record — check these:
    </div>
    <div class="conf-grid">
      ${(conf||[]).map(c=>`
        <div class="ci">
          <div class="cl">${esc(c.label)}</div>
          <div class="cv">${esc(c.value)}</div>
        </div>`).join('')}
    </div>`;
}

function seoTab(s){
  if(!s) return '<div class="empty"><h3>No SEO data</h3><p>Generate a script first.</p></div>';
  const titles=s.title_options||[];
  const tags=s.tags||[];
  const htags=s.hashtags||[];
  return `
    <div style="max-width:820px;">
      <div class="il" style="margin-bottom:10px;">🎯 Title Options <span style="font-size:11px;color:var(--dim);font-weight:400;text-transform:none;letter-spacing:0">(click to copy)</span></div>
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:24px;">
        ${titles.map(t=>`
          <div class="li" style="font-size:14px;font-weight:500;" onclick="copyTxt(${JSON.stringify(t)})">${esc(t)}</div>
        `).join('')}
      </div>
      <div class="il" style="margin-bottom:10px;">💬 Comment Prompt <span style="font-size:11px;color:var(--dim);font-weight:400;text-transform:none;letter-spacing:0">(pin this as your top comment)</span></div>
      <div class="hook-c" style="margin-bottom:24px;cursor:pointer;" onclick="copyTxt(${JSON.stringify(s.comment_question||'')})">
        <div style="font-size:14px;line-height:1.75;">${esc(s.comment_question||'')}</div>
      </div>
      <div class="il" style="margin-bottom:10px;">🖼️ Thumbnail Text</div>
      <div class="hook-c" style="margin-bottom:24px;cursor:pointer;" onclick="copyTxt(${JSON.stringify(s.thumbnail_text||'')})">
        <div style="font-size:16px;font-weight:600;line-height:1.5;">${esc(s.thumbnail_text||'')}</div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px;">
        <div>
          <div class="il" style="margin-bottom:10px;">🏷️ Tags <span style="font-size:11px;color:var(--dim);font-weight:400;text-transform:none;letter-spacing:0">(click to copy all)</span></div>
          <div class="nf" style="cursor:pointer;" onclick="copyTxt(${JSON.stringify(tags.join(', '))})">
            ${tags.map(tg=>`<div class="nf-row" style="padding:7px 0;"><div class="nf-txt">${esc(tg)}</div></div>`).join('')}
          </div>
        </div>
        <div>
          <div class="il" style="margin-bottom:10px;"># Hashtags <span style="font-size:11px;color:var(--dim);font-weight:400;text-transform:none;letter-spacing:0">(click to copy all)</span></div>
          <div class="nf" style="cursor:pointer;" onclick="copyTxt(${JSON.stringify(htags.join(' '))})">
            ${htags.map(h=>`<div class="nf-row" style="padding:7px 0;"><div class="nf-txt" style="color:var(--acc);">${esc(h)}</div></div>`).join('')}
          </div>
        </div>
      </div>
      <div class="il" style="margin-bottom:10px;">📝 Description Starter <span style="font-size:11px;color:var(--dim);font-weight:400;text-transform:none;letter-spacing:0">(click to copy)</span></div>
      <div class="hook-c" style="cursor:pointer;white-space:pre-wrap;font-size:13px;line-height:1.8;" onclick="copyTxt(${JSON.stringify(s.description_start||'')})">${esc(s.description_start||'')}</div>
    </div>`;
}

function goScene(i){
  if(!D) return;
  const L=D.languages[lang];
  if(i<0||i>=L.scenes.length) return;
  scene=i;
  const t=document.getElementById('t-script');
  if(t) t.innerHTML=scriptTab(L);
}

function tab(el,id){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.tc').forEach(t=>t.classList.remove('on'));
  el.classList.add('on');
  document.getElementById(id).classList.add('on');
}

function copyScene(){
  if(!D) return;
  const s=D.languages[lang].scenes[scene];
  copyTxt(`Scene ${scene+1}: ${s.name}\n\nFilm: ${s.direction}\n\nSay:\n"${s.dialogue}"`);
}

function copyTxt(t){
  navigator.clipboard.writeText(t).then(()=>toast('Copied!')).catch(()=>{
    const ta=document.createElement('textarea');
    ta.value=t; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta); toast('Copied!');
  });
}

function esc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function toast(msg,err=0){
  const t=document.getElementById('toast');
  t.textContent=msg; t.style.background=err?'#ef4444':'var(--grn)';
  t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2800);
}
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════════════════════════
#  HTTP SERVER  (always fresh — kills old instance first)
# ═══════════════════════════════════════════════════════════════════════════════

_server_ref = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            b = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate")
            self.send_header("Content-Length",len(b))
            self.end_headers(); self.wfile.write(b)
        elif p == "/api/script":
            self._json(read_json())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/generate":
            n    = int(self.headers.get("Content-Length",0))
            body = _json.loads(self.rfile.read(n) or b"{}") if n else {}
            raw  = body.get("topic","").strip()
            dl   = _parse_lang(body.get("lang","English"))
            topic = raw or fetch_trending_topic()
            print(f"  📌 Generating: {topic} [{dl}]")
            news  = fetch_news_for_topic(topic)
            print(f"  📰 News: {len(news)} headline(s)" + (f" — {news[0][:55]}…" if news else ""))
            cat   = detect_category(topic)
            angle = get_angle(topic, cat, load_history())
            data  = generate_structured(topic, angle, cat, news, default_lang=dl)
            save_data(data)
            save_to_history(topic, angle, raw)
            self._json(data)
        else:
            self.send_error(404)

    def _json(self, obj):
        b = _json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store, no-cache, must-revalidate")
        self.send_header("Content-Length",len(b))
        self.end_headers(); self.wfile.write(b)

    def log_message(self,*_): pass


def run_server(port=8080):
    global _server_ref
    if not _port_free(port):
        print(f"  ♻️  Port {port} in use — killing old instance...")
        _kill_port(port)

    HTTPServer.allow_reuse_address = True
    srv = HTTPServer(("",port), Handler)
    _server_ref = srv
    url = f"http://localhost:{port}"
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print(f"  🌐 Open UI at: {url}")
    print("  Press Ctrl+C to stop\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Stopped.")
    finally:
        srv.server_close()

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    args      = sys.argv[1:]
    raw_topic = args[0].strip() if len(args) >= 1 else ""
    lang      = _parse_lang(args[1] if len(args) >= 2 else "English")

    print("\n  🎬 Content Script Generator")
    print("  " + "─" * 44)

    topic = raw_topic if raw_topic else fetch_trending_topic()
    print(f"  📌 Topic    : {topic}")
    print(f"  🌍 Language : {lang}")
    print(f"  📅 Date     : {TODAY}")

    news  = fetch_news_for_topic(topic)
    if news:
        print(f"  📰 News     : {len(news)} headline(s) — {news[0][:55]}…")
    else:
        print("  📰 News     : none found (using topic context)")

    cat   = detect_category(topic)
    print(f"  📂 Category : {cat} ({'personal' if is_personal(cat) else 'news/events'})")

    angle = get_angle(topic, cat, load_history())
    print(f"  🎯 Angle    : {angle}")

    data  = generate_structured(topic, angle, cat, news, default_lang=lang)
    save_data(data)
    save_to_history(topic, angle, raw_topic)

    run_server()


if __name__ == "__main__":
    main()
