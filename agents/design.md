# Design System: HelmRig Dashboard

> Övervakningspanel för AI-agent-pipelines — LangGraph-agenter, cron-scheman, Overlord-daemon, realtidsloggar via SSE.

---

## 1. Visual Theme & Atmosphere

En monitor/operations-dashboard i mörkt tema — "Cockpit Dense" med kontrollerad symmetri för snabb scannability. Atmosfären är teknisk och precis, som en övervakningscentral i ett modernt serverrum. Låg färgmättnad med strategiska accentfärger för statusindikering. Allt är byggt för att läsas på avstånd och uppdateras i realtid.

- **Density:** 7/10 — Cockpit Dense
- **Variance:** 3/10 — Predictable Symmetric
- **Motion:** 5/10 — Fluid CSS (SSE-strömning, status-övergångar)

---

## 2. Color Palette & Roles

### Neutrals (Zinc-bas, varm ton)
| Token | Hex | Roll |
|-------|-----|------|
| `--bg-canvas` | `#0B0B0F` | Primär bakgrund (yttersta lagret) |
| `--bg-surface` | `#141418` | Kort- och containeryta |
| `--bg-surface-raised` | `#1C1C24` | Förhöjda ytor (modaler, hover) |
| `--bg-surface-hover` | `#24242E` | Hover-tillstånd på klickbara kort |
| `--border-subtle` | `rgba(255,255,255,0.06)` | Standard 1px border |
| `--border-raised` | `rgba(255,255,255,0.10)` | Kantlinjer på förhöjda element |

### Text
| Token | Hex | Roll |
|-------|-----|------|
| `--text-primary` | `#F1F1F3` | Rubriker, agentnamn, etiketter |
| `--text-secondary` | `#8B8B9E` | Brödtext, metadata, tidsstämplar |
| `--text-muted` | `#5C5C72` | Mindre viktig info, placeholder |
| `--text-inverse` | `#0B0B0F` | Text på accent-färgade badges |

### Accent (singel — låg mättnad)
| Token | Hex | Roll |
|-------|-----|------|
| `--accent` | `#6C8BFF` | Primär accent: CTA, aktiva state, focus-ring, run-knapp |
| `--accent-hover` | `#8BA4FF` | Hover på accent-element |
| `--accent-muted` | `rgba(108,139,255,0.12)` | Soft highlight, subtle selection |

### Semantiska färger
| Token | Hex | Roll |
|-------|-----|------|
| `--status-ok` | `#34D399` | Status: ok, running, success |
| `--status-error` | `#F87171` | Status: error, failed, timeout |
| `--status-warning` | `#FBBF24` | Status: warning, degraded |
| `--status-never` | `#3D3D50` | Status: never run (inaktiv) |
| `--status-running` | `#60A5FA` | Status: pågående körning |

### Bakgrundsfärger för statusbadges
| Token | Hex |
|-------|-----|
| `--badge-ok-bg` | `rgba(52,211,153,0.15)` |
| `--badge-error-bg` | `rgba(248,113,113,0.15)` |
| `--badge-never-bg` | `rgba(61,61,80,0.5)` |
| `--badge-running-bg` | `rgba(96,165,250,0.15)` |

---

## 3. Typography Rules

- **Display/Headings:** `Satoshi` — track-tight, vikt-driven hierarki, ingen storleks-eskalation
- **Body/UI:** `Satoshi` — relaxed leading (1.5), 65ch max-width
- **Mono (kod, tidsstämplar, stdout, cron):** `JetBrains Mono` — alla siffror och tekniska data
- **Scale:** `clamp(0.75rem, 1vw, 1rem)` för body, stegvis för rubriker
- **Banned:** Inter, system fonts, Times New Roman, Georgia, Garamond. Serif är alltid bannat i dashboards.

### Skalning
| Nivå | Storlek | Vikt | Användning |
|------|---------|------|------------|
| h1 | `1.5rem` | 600 | Sidrubrik |
| h2 | `1.25rem` | 600 | Avdelningstitel |
| agent-name | `1rem` | 600 | Agentkortets namn |
| body | `0.875rem` | 400 | Brödtext, metadata |
| small | `0.75rem` | 400 | Tidsstämplar, cron, sekundär info |
| mono | `0.8rem` | 400 | Kod, stdout, duration |

---

## 4. Component Stylings

### Agent Cards
- **Bakgrund:** `--bg-surface` (`#141418`)
- **Border:** `--border-subtle` — färgad per status via semantisk kant
- **Border-radius:** `10px`
- **Padding:** `1rem`
- **Transition:** `border-color 0.3s ease, background 0.2s ease`
- **Hover:** `--bg-surface-hover` + translateY(-1px) shadow boost
- **Status-border:** vänsterkant 3px solid i statusfärg (istället för hela border)
  - ok → `--status-ok`
  - error → `--status-error`
  - never → `--status-never`
  - running → `--status-running`

### Status Badges
- **Padding:** `0.15rem 0.6rem`
- **Border-radius:** `5px`
- **Font:** `0.75rem`, 500 weight, uppercase tracking 0.05em
- **Text:** vit på färgad bakgrund (badge-bg)
- **Ingen ikon/emoji** — endast text

### Buttons
- **Primary (Run):** `--accent` fill, `--accent-hover` hover, white text
- **Ghost (Historik-länk):** transparent bg, `--text-secondary` text, `--accent` hover text
- **Border-radius:** `6px`
- **Padding:** `0.4rem 0.9rem`
- **Font:** `0.8rem`, 500 weight
- **Active state:** `scale(0.97)` — ingen layout-shift
- **Ingen yttre glow** — ingen neon

### stdout-preview (loggutskrift)
- **Bakgrund:** `#0D0D12`
- **Border-radius:** `6px`
- **Padding:** `0.75rem`
- **Font:** `JetBrains Mono`, `0.75rem`
- **Overflow:** auto scroll, max-height `180px`
- **Text color:** `--text-secondary`

### Toast Notifications (SSE-events)
- **Fixed position:** bottom-right, 1rem offset
- **Bakgrund:** `--bg-surface-raised`
- **Border:** `--border-raised`
- **Border-radius:** `8px`
- **Animation:** fade-in 0.3s, auto-remove after 4s
- **Ingen ikon/emoji** — endast text

### Agent History (agent.html)
- **Entries:** samma som cards — `--bg-surface` med status-färgad vänsterkant
- **Gap:** `0.75rem` mellan entries
- **Header:** tidsstämpel + duration + status på en rad, `--text-muted`
- **stdout:** `--bg-canvas` för kontrast mot entry-bakgrunden

### SSE Indicator
- **Punkt:** `8px` diameter, `--status-ok` när ansluten, `--status-error` när frånkopplad
- **Animation:** subtilt pulse (`opacity` 1→0.6→1, 2s) när ansluten

---

## 5. Layout Principles

### Dashboard (dashboard.html)
- **Max-width:** `1400px`, centered
- **Grid:** `repeat(auto-fill, minmax(340px, 1fr))` — responsivt anpassat
- **Page padding:** `2rem` desktop, `1rem` mobile
- **Title area:** h1 + subtitle + SSE-indikator i en flex-rad
- **Empty state:** centered, muted text — "Inga agenter hittades" med hint om `harness scaffold`

### Agent History (agent.html)
- **Back-länk:** subtil, `--text-secondary`
- **Entries:** `100%` bredd, staplade vertikalt
- **Ingen grid** — kronologisk flöde

### Responsiv
- **< 768px:** Grid → single column. Page-padding → `1rem`. Cards full-width.
- **Ingen horizontal scroll** tillåten
- **Touch targets:** minimum `44px` för alla interaktiva element

---

## 6. Motion & Interaction

- **SSE-realtidsuppdateringar:** Statusbadges och metadata uppdateras utan full re-render (htmx)
- **Status transition:** border-color fade 0.3s ease
- **Toast:** fade-in translateY(10px) → fade-out opacity 0, 0.3s
- **Hover på cards:** background transition 0.2s
- **Knapptryck:** `transform: scale(0.97)` 0.1s
- **Inga spinners** — skeletala laddningsindikatorer vid behov
- **Reduced motion:** respektera `prefers-reduced-motion` — alla animationer ska vara ickeblockerande

---

## 7. Anti-Patterns (Banned)

- ❌ **Inga emojis** som UI-element (används ej i strukturella ikoner, badges eller knappar)
- ❌ **Ingen Inter** — Satoshi + JetBrains Mono endast
- ❌ **Ingen pure black** (`#000000`) — använd `#0B0B0F` som mörkaste ton
- ❌ **Ingen neon glow** på knappar eller kort
- ❌ **Inga AI-clichéer** i copy: "Elevate", "Seamless", "Unleash", "Next-Gen", "Supercharge"
- ❌ **Inga 3-column equal grids** — använd auto-fill med min-width
- ❌ **Inga generiska placeholder-namn** — agentnamn är verkliga
- ❌ **Inga överlappande element** — varje element har sin egen spatiala zon
- ❌ **Ingen horizontal scroll** på mobil
- ❌ **Inga circular spinners** — använd skeleton/status-text istället
- ❌ **Inga centrerade Hero-sektioner** — detta är en dashboard, inte en landing page
