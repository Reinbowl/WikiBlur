# [WikiBlur](https://reinbowl.github.io/WikiBlur/)

**Guess Wikipedia articles from blurry images — a new category every day.**

WikiBlur is a daily browser-based guessing game. Each day, everyone worldwide gets the same Wikipedia category and must identify blurred article images across 8 rounds of escalating difficulty.

---

## How to Play

1. Click **Start Today's Challenge** to begin.
2. Each round shows a blurred image from a Wikipedia article in today's category.
3. Pick the correct article from the 4 options shown.
4. Survive all 8 rounds without losing all your lives!

---

## Rules

- **3 lives** — each wrong answer costs one life. Lose all three and the game ends early.
- **8 rounds** split into three difficulty tiers:
  - 🟢 **Easy** (Rounds 1–3) — no blur, 5 pts per correct answer
  - 🟡 **Medium** (Rounds 4–6) — minimal blur, 10 pts per correct answer
  - 🔴 **Hard** (Rounds 7–8) — more blur, 15 pts per correct answer
- **Reveal** — on Medium and Hard rounds, spend 5 pts to reduce the blur and get a better look.
- **Daily reset** — the category and image assignments reset at midnight. Come back tomorrow for a new challenge!

---

## Scoring

| Difficulty | Points (correct) |
|------------|-----------------|
| 🟢 Easy    | 5               |
| 🟡 Medium  | 10              |
| 🔴 Hard    | 15              |

Using the Reveal costs **−5 pts**. Maximum possible score is **75 pts**.

---

## Endless Mode
 
A separate mode where the goal is to survive as long as possible across randomly selected categories.
 
**Starting a run:** Press the **Endless** button and choose a difficulty — Easy, Medium, or Hard (same blur levels as the daily challenge). The selected difficulty applies to the entire run with no escalation and no Reveal option.
 
**Each round:** A random valid category is chosen, and 4 articles from it are presented as options. Every round uses a different category.
 
**Lives:** You start with 3 lives. A wrong answer costs one life — lose all three and the run ends.
 
**Trackers:**
- ✅ **Total rounds** — how many rounds you survived for that run
- 🔥 **Longest streak** — the longest sequence of correct answers without losing a life

---

## Files

| File | Description |
|------|-------------|
| `index.html` | The complete game (single file, no dependencies) |
| `validate_categories.py` | Script to verify which Wikipedia categories have enough image-rich articles for a full game |
| `valid_categories.json` | Output of the validation script — the pool of categories the game picks from |

---

## Refresh

To refresh the category pool, run:

```bash
python validate_categories.py
```

This regenerates `valid_categories.json` with categories confirmed to have enough articles with images.
