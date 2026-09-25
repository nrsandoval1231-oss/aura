# Renzo — Studio UI Kit

> Tell Renzo what you want. He'll make it, gently.

A complete UI/UX design system for **Renzo**, a quiet local-first software for solo builders. The user describes what they want in plain English; Renzo plans, builds, and quietly delivers the result.

---

## 📦 What's inside

```
renzo-ui/
├── renzo.css                 # shared design system
├── renzo.js                  # motion & interactivity
├── home.html                 # I   — "What would you like to build?"
├── building.html             # II  — "Working on it." (auto-advances)
├── done.html                 # III — "Here you go."
├── first-visit.html          # IV  — first-visit onboarding
├── manifesto.html            # II  — long-scroll brand voice
├── journal.html              # III — dated ledger of past work
├── landing.html              # I   — marketing landing
├── card.html                 # press kit / A4 print card
├── README.md                 # you are here
│
├── *-standalone.html         # fully inlined versions for direct file:// open
└── renzo-card.pdf            # rendered A4 PDF of card.html
```

Open `*-standalone.html` files directly in a browser — no server needed. For full motion + suggestion fill across pages, serve via `python3 -m http.server`.

---

## 🎨 Design system

| Token | Value | Use |
|------|-------|-----|
| `--ivory` | `#FAF7F2` | Primary background |
| `--champagne` | `#E9E3D6` | Card surfaces |
| `--gold-soft` | `#D4AF37` | The accent — used sparingly |
| `--brown` | `#2E2A24` | Primary text |
| Font serif | EB Garamond | Headlines, body, italic emphasis |
| Font sans | Outfit | Small uppercase labels, nav only |
| Font mono | JetBrains Mono | File names, code |

**Required structural elements on every page:**
- `.paper` texture (radial gradients at 2-3% opacity)
- Four `.corner` hairline gold L-shapes
- Topbar: `Renzo · STUDIO` brand · English nav · Roman numeral page marker
- Italic serif for emphasis, never bold-sans
- Generous whitespace

---

## 🧠 UX thesis

**The user never sees internal jargon.** Three moments cover the whole experience:

1. **A question** — *"What would you like to build?"*
2. **A waiting** — *"Working on it."*
3. **A delivery** — *"Here you go."*

There are **no settings**. The user does not pick models, configure agents, or choose providers. The studio knows what to use — that's the point. Renzo picks the agents, runs them, and reports back.

---

## ✨ Motion

- **`.rise` + `.rise-N`** — gentle fade-up on load with cascading delays
- **Page-turn transitions** — links fade out (blur + translate) over 420ms before navigation
- **Breathing dot** — gold pulse on the building screen (no spinner)
- **Suggestion auto-fill** — clicking a suggestion on `first-visit.html` pre-fills `home.html`'s input via `sessionStorage`

---

## 🇮🇹 Italian influence

Dialed back to a quiet nod — the name **Renzo** (after Renzo Piano, the architect) carries it. Roman numerals (I, II, III, IV) on each page. Hairline gold corner brackets like a fine binding. That's it. Everything else is plain English, plainly.

---

## 🖨 The Renzo Card (`card.html` + `renzo-card.pdf`)

A single A4 page, like a menu or press kit card. Prints beautifully, fits in a presentation folder. Uses the print-friendly CSS (`@page A4 portrait`). Generated as `renzo-card.pdf` (63KB, 1 page).

---

## 🚀 Quick start

```bash
# Option A: just open the standalone
open home-standalone.html

# Option B: serve locally (for cross-page motion)
cd renzo-ui
python3 -m http.server 8765
# visit http://localhost:8765/home.html
```

Flow: `home.html` → `building.html` (auto-advances after 5.5s) → `done.html`. Other pages accessible from topbar nav.

---

## 📐 Screens

| Page | Roman | What it does |
|------|-------|--------------|
| `home.html` | I | The "what would you like to build?" input |
| `building.html` | II | "Working on it." — auto-redirects to done after 5.5s |
| `done.html` | III | "Here you go." — small result card, three text actions |
| `first-visit.html` | IV | First-visit onboarding, three-step explainer, clickable suggestions |
| `manifesto.html` | II | Long-scroll: on making things, on attention, on locality, on being small |
| `journal.html` | III | Journal of past work, dated entries |
| `landing.html` | I | Marketing landing page |
| `card.html` | — | Press kit / A4 print card (also as `renzo-card.pdf`) |

---

## 🛠 Built with

- HTML5
- Vanilla CSS (one shared file)
- Vanilla JS (one shared file)
- EB Garamond, Outfit, JetBrains Mono from Google Fonts

---

## 📐 The skill

The Renzo Studio design system is also captured as a reusable skill at `.skills/renzo-atelier/SKILL.md`. Load it any time to rebuild this aesthetic from scratch.

*with care.*
