# aura · brand kit

Complete visual identity for the aura CLI, built around the **Deep Tide** palette
(`#173D45`) and one warm honey-gold accent (`#E8B86D`).

## structure

```
brand/
├── logo/                  ← SVG logo system
│   ├── aura-wordmark.svg          (primary · cream on dark)
│   ├── aura-wordmark-light.svg    (teal on light)
│   ├── aura-monogram.svg          (just the "a")
│   ├── aura-icon.svg              (512px app icon)
│   ├── aura-icon-light.svg        (light variant)
│   └── aura-mark.svg              (concentric ring alternative)
├── favicon/
│   └── favicon.svg                (modern SVG favicon)
├── tokens/                ← for developers
│   ├── design-tokens.css          (CSS custom properties)
│   ├── design-tokens.json         (W3C DTCG format)
│   └── tailwind.config.js         (Tailwind preset)
├── og/
│   └── og-image.svg               (1200×630 Open Graph card)
├── brand-guidelines.html          (full brand book · open in browser)
├── aura-cli.html                  (interactive CLI demo using the brand)
├── deep-tide-palette.html         (palette reference · the color system)
└── README.md
```

## quick start

### HTML / CSS

Drop `tokens/design-tokens.css` into your project, import it, and use the variables:

```html
<link rel="stylesheet" href="brand/tokens/design-tokens.css">

<style>
  body {
    background: var(--aura-bg);
    color: var(--aura-ink);
    font-family: var(--aura-font-sans);
  }
  .cta {
    background: var(--aura-accent);
    color: var(--aura-bg-2);
  }
</style>
```

### Tailwind

Extend your config with the preset:

```js
// tailwind.config.js
module.exports = {
  presets: [require('./brand/tokens/tailwind.config.js')],
};
```

Then use `bg-aura-bg`, `text-aura-ink`, `text-aura-accent`, etc.

### Logo

```html
<!-- dark background -->
<img src="brand/logo/aura-wordmark.svg" alt="aura" height="48">

<!-- light background -->
<img src="brand/logo/aura-wordmark-light.svg" alt="aura" height="48">

<!-- app icon / favicon -->
<link rel="icon" type="image/svg+xml" href="brand/favicon/favicon.svg">
```

### Open Graph

```html
<meta property="og:image" content="https://yourdomain.com/brand/og/og-image.svg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
```

## the anchor

`#173D45` — Deep Tide. The single non-negotiable. Every other color in this
system exists to support it.

## the accent

`#E8B86D` — warm honey gold. The only bold color. Use it sparingly — primary
actions, the prompt, the wordmark accent. When in doubt, less.

## fonts

All assets reference Google Fonts via `@import`:
- **DM Serif Display** — headlines, brand voice
- **Instrument Serif** — italic accents, quotes
- **Outfit** — UI body
- **JetBrains Mono** — code, terminal output, metadata

System fallbacks (Georgia, system-ui, SF Mono) ship with the SVGs so they
render sensibly even without web access.

## voice

> *"The interface that disappears is the one that understood you."*

Short. Verbs. Present tense. No emoji. No superlatives.

See `brand-guidelines.html` for the full brand book.
