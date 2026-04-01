<<<<<<< HEAD
# content
Content Generation for Social Media
=======
# YouTube Content Generator — 3-Channel End-to-End Pipeline

**Tamil Channel | Telugu Channel | English Channel**
Lifestyle Couple + Data Engineer | Viral strategy + full scripts + legal protection

---

## Requirements

- Python 3.9 or higher
- No external packages — pure Python standard library

---

## Daily Workflow

```
Step 1 — Notice what is trending today (1-2 words)
Step 2 — Run the script for your channel(s)
Step 3 — Read the script, check content safety rules, film, upload
```

---

## Commands

### Single channel

```bash
# Telugu channel
python3 content_generator.py -t "ai layoffs" --channel telugu

# Tamil channel
python3 content_generator.py -t "recession"  --channel tamil

# English channel
python3 content_generator.py -t "burnout"    --channel english
```

### All 3 channels at once

```bash
python3 content_generator.py -t "diwali"  --channel all
python3 content_generator.py -t "cricket" --channel all -n 2
```

### Any topic — works with literally anything

```bash
python3 content_generator.py -t "ipl"              --channel telugu
python3 content_generator.py -t "elon musk"        --channel all
python3 content_generator.py -t "stock market"     --channel tamil
python3 content_generator.py -t "taylor swift"     --channel english
python3 content_generator.py -t "interest rates"   --channel all
python3 content_generator.py -t "wedding season"   --channel telugu
python3 content_generator.py -t "monsoon"          --channel tamil
python3 content_generator.py -t "chatgpt"          --channel all
```

### Other options

```bash
# Preview without saving to history
python3 content_generator.py -t "burnout" --channel telugu --no-save

# Export all packages to JSON
python3 content_generator.py -t "ai" --channel all --export today.json

# Stats per channel
python3 content_generator.py --stats --channel all
python3 content_generator.py --stats --channel telugu

# Random generation (no topic)
python3 content_generator.py --channel tamil

# JSON output
python3 content_generator.py -t "gym" --channel english --output json
```

---

## What You Get Per Video

Each generated package includes:

| Section | What it contains |
|---|---|
| **3 Titles** | English + Telugu + Tamil versions |
| **Viral Hook** | Proven hook formula for opening line |
| **Viral Title Formula** | Click-optimized title structure |
| **Thumbnail Guide** | Text overlay, visual concept, no-face version |
| **Thumbnail Tips** | 4 platform-proven design rules |
| **Full Script** | 5 scenes, timed, with spoken lines in channel language |
| **Description** | Copy-paste ready, SEO hashtags + disclaimer included |
| **Pinned Comment** | Post within 1 minute of upload |
| **Growth Tips** | Channel-specific upload days, Shorts strategy, cross-posting |
| **Content Safety** | 8 legal rules to follow before every upload |

---

## Channel Configuration

| Channel | Language | History File | Best Upload Days |
|---|---|---|---|
| `telugu` | Telugu (TE) | `history_telugu.json` | Tuesday & Friday |
| `tamil` | Tamil (TA) | `history_tamil.json` | Wednesday & Saturday |
| `english` | English (EN) | `history_english.json` | Monday & Thursday |

Each channel has its own separate history — no cross-contamination of titles.

---

## Script Structure

### Couple Vlog (6 minutes)

| Scene | Time | What to film |
|---|---|---|
| HOOK | 0:00 – 0:15 | Phone propped, ambient sound, no face needed |
| SET THE SCENE | 0:15 – 1:00 | B-roll: kitchen, coffee, window, hands |
| MAIN MOMENT | 1:00 – 4:30 | Follow the activity naturally |
| HONEST REFLECTION | 4:30 – 5:30 | Static shot or voice-over |
| OUTRO + CTA | 5:30 – 6:00 | 30 seconds, one subscriber ask |

### Tech Video (8 minutes)

| Scene | Time | What to film |
|---|---|---|
| HOOK | 0:00 – 0:20 | Face cam or screen record, cut straight in |
| CONTEXT | 0:20 – 1:30 | Why this topic matters to you personally |
| 3 POINTS | 1:30 – 6:00 | Screen record + face cam commentary |
| HONEST TAKE | 6:00 – 7:30 | Face cam, unscripted, say what you think |
| OUTRO + CTA | 7:30 – 8:00 | One question, one subscribe ask |

---

## Viral Strategy (Built In)

Every video gets:

**4 Hook Types** — engine picks the right one per category:
- Curiosity: *"Nobody is talking about this side of {topic}"*
- Emotion: *"{topic} hit different this week — we need to talk about it"*
- Relatability: *"Every couple going through {topic} needs to hear this"*
- Safe controversy: *"Unpopular opinion about {topic} — we might get hate for this"*

**Thumbnail rules** included per video:
- Candid expression, not posed smile
- 3 words max on thumbnail
- High contrast background
- Genuine emotion only

---

## Disclaimer System (Auto-Generated)

Disclaimers are automatically selected based on your topic and added to the description:

| Topic keyword | Disclaimers added |
|---|---|
| `layoffs`, `career` | General + Career + Copyright |
| `recession`, `money`, `inflation` | General + Financial + Copyright |
| `health`, `gym`, `fitness` | General + Health + Copyright |
| `war`, `gaza`, `election`, `conflict` | General + Geopolitical + Fair Use + Copyright |
| `ai`, `chatgpt` | General + Career + Copyright |
| Everything else | General + Copyright |

You never need to add disclaimers manually — they are already in the description output.

---

## Content Safety Rules (Shown Every Upload)

These 8 rules appear in every generated package:

1. Never make specific financial predictions or guarantees
2. Never use copyrighted music — use YouTube Audio Library only
3. Never use other creators' footage — create your own B-roll
4. Never make medical claims — share personal experience only
5. Never name specific individuals negatively — share situations, not people
6. Label opinions clearly as opinions, not facts
7. Avoid sensational titles your video cannot deliver on
8. For geopolitical topics: share your personal response, not political analysis

---

## Supported Topic Keywords (Rich Scripts)

These get specific, curated titles:

| Keyword | Content angle |
|---|---|
| `ai`, `chatgpt`, `llm`, `copilot` | AI tools + couple reaction |
| `layoffs`, `fired`, `job loss` | Career anxiety + couple finance |
| `recession`, `inflation`, `money` | Budget lifestyle + simple living |
| `remote`, `wfh`, `rto` | WFH couple setup + deep work |
| `burnout`, `mental health`, `tired` | Slow living + recovery weekend |
| `war`, `gaza`, `election`, `conflict` | News detox + grounding vlog |
| `gym`, `fitness`, `health` | Couple wellness |
| `travel`, `trip`, `road trip` | Couple travel vlog |
| `startup`, `building`, `saas` | Build in public + partner support |
| `routine`, `habit`, `morning` | Couple morning routine |
| `rain`, `weather`, `cold` | Indoor cozy vlog |

**Any other topic** (cricket, IPL, Eid, Diwali, Pongal, weddings, elections, etc.) generates dynamic scripts automatically.

---

## History Files

| File | Channel |
|---|---|
| `history_telugu.json` | Telugu channel history |
| `history_tamil.json` | Tamil channel history |
| `history_english.json` | English channel history |

Each channel tracks its own titles independently. To reset a channel: delete its history file.

---

## Week Planner Example

```bash
# Monday
python3 content_generator.py -t "monday motivation" --channel all

# Tuesday
python3 content_generator.py -t "ai tools"  --channel telugu

# Wednesday
python3 content_generator.py -t "recession" --channel tamil

# Thursday
python3 content_generator.py -t "burnout"   --channel english

# Friday
python3 content_generator.py -t "weekend"   --channel all

# Saturday
python3 content_generator.py -t "cooking"   --channel telugu

# Sunday
python3 content_generator.py -t "slow day"  --channel tamil
```
>>>>>>> 2799e5f (Initial commit)
