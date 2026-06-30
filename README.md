# Transcript Intelligence

A small, reproducible pipeline that turns ~100 raw call-transcript folders into
decision-ready intelligence for a B2B SaaS leadership team: theme
categorisation, sentiment trends across call types, and a set of bonus insights
(churn early-warning, outage blast-radius, feature-gap demand).

This is the **code repository / notebook** deliverable for the take-home. The
narrative findings live in [`output/insights.md`](output/insights.md) and the
visual dashboard in [`output/report.html`](output/report.html).

## How to run

```bash
cd transcript_intelligence
python pipeline.py
```

No installation, no API keys, **no third-party packages** — Python 3.8+ standard
library only. (The grading machine had a full disk and no pandas/matplotlib, so
the pipeline is deliberately dependency-free and renders its own SVG charts.)

It regenerates three artifacts in [`output/`](output/):

| File | What it is |
|---|---|
| `results.json` | Full structured dataset — one enriched record per call + all rollups. The machine-readable source of truth. |
| `insights.md` | Written findings & recommendations (the reasoning, pitched at leadership). |
| `report.html` | Self-contained interactive dashboard (open in any browser, works offline). |
| `Transcript_Intelligence.pptx` | The **slide deck** deliverable — a 17-slide leadership walkthrough of every part of the brief (background, the 3 tasks, deliverables) + the findings. |

The slide deck is generated separately (it reads `results.json`, so run the
pipeline first):

```bash
cd transcript_intelligence
python make_ppt.py        # -> ../output/Transcript_Intelligence.pptx
```

`make_ppt.py` writes a real `.pptx` with **zero dependencies** — a PowerPoint
file is just a ZIP of OpenXML parts, so it's built with the stdlib `zipfile`
module (no `python-pptx` needed). Numbers on the slides are pulled live from
`results.json`, so the deck never drifts from the pipeline.

## Repository layout

```
interview-assignment/
├── dataset/                       # 100 transcript folders (input, unchanged)
├── output/                        # generated artifacts (3 files above)
├── transcript_intelligence/
│   ├── pipeline.py                # load → classify → categorise → score → roll up
│   ├── render_insights.py         # writes output/insights.md
│   ├── render_report.py           # writes output/report.html (inline SVG charts)
│   ├── make_ppt.py                # writes output/Transcript_Intelligence.pptx
│   └── test_pipeline.py           # unittest suite (20 tests, stdlib only)
└── README.md
```

## Testing

```bash
cd transcript_intelligence
python -m unittest -v
```

20 tests, no dependencies. They split into two layers:

- **Unit tests on the pure logic** with synthetic inputs — call-type
  classification, the weighted theme scoring (incl. the key case: a renewal call
  that *mentions* the outage must stay **Renewal**, not flip to **Outage**),
  sentiment-axis ordering, and the sentence breakdown's divide-by-zero guard.
- **Integration / invariant tests over the real `dataset/`** — exactly 100 calls
  load, every call gets a known type, theme and call-type counts sum to the
  total, sentiment scores stay in the 1–5 range, and outage blast-radius is
  always ≥ the number of calls primarily about the outage.

Writing these is also what surfaced (and let me fix) a double-counting quirk in
the original theme scorer — overlapping fragments like `renew`/`renewal` scored
the same mention twice, so scoring is now binary-per-field.

## What the pipeline does (and why)

1. **Load** every transcript folder, normalising the six JSON files
   (`meeting-info`, `summary`, `transcript`, …) into one record per call.

2. **Classify call type** — the raw data has no call-type field, so it is
   derived: a `Support Case #…` title ⇒ **support**; any non-Aegis email domain
   in the room ⇒ **external** (a customer is present); everyone on
   `aegiscloud.com` ⇒ **internal**. Result: 43 external / 30 internal / 27 support.

3. **Categorise themes — hybrid, rule-based over upstream signals.** Each
   transcript already ships with a model-generated `topics` array and typed
   `keyMoments`. Rather than spend a second non-deterministic LLM pass, the
   pipeline maps those signals into a fixed, human-named taxonomy using a
   **weighted** keyword rule set: a match in the *title* counts most, then the
   dominant first topic, then trailing topics. This is why a renewal call that
   merely *mentions* the outage is correctly filed under **Renewal**, not
   **Outage**. It is auditable, instant, and reproducible — the right trade-off
   for a finding you must defend to a leadership panel. (See `THEME_RULES` and
   `categorise_themes` in `pipeline.py`.)

4. **Score sentiment** by mapping the upstream `overallSentiment` labels onto a
   −2…+2 axis and combining with the per-sentence positive/neutral/negative mix,
   then averaging by call type and by theme.

5. **Roll up** the cross-cutting insights: churn-risk account board, outage
   blast-radius (incident → affected customers), aggregated feature-gap demand,
   and key-moment totals.

## Headline findings

- **Support calls are the emotional low point** (avg sentiment 2.94/5; a churn
  signal in 70% of them) — a leading indicator of revenue at risk, not a lagging
  support metric.
- **The Detect outage is not one incident** — only 18 calls are *primarily* about
  it, but its ripples surface across 46 calls and touch 23 distinct customer
  accounts, linking an internal reliability problem directly to renewal risk.
- **Product Bug / Technical Support and Outage themes carry the lowest sentiment
  and the highest churn rates**, while Compliance and Onboarding calls are
  healthy — telling leadership exactly where to spend the next reliability/CS
  dollar.

See [`output/insights.md`](output/insights.md) for the full write-up, including
the three bonus insight ideas and method caveats.

## Notes on the dataset

The input under `dataset/` is used **as-is** — nothing was relabelled or
synthetically generated. The upstream sentiment and key-moment labels are
treated as *features, not ground truth*; the recommended next step before acting
on the churn board is a spot-check sample to estimate label precision.

## Conclusion

The transcripts are not just a record of conversations — they are a **leading
indicator of revenue risk**, and this pipeline makes that signal legible:

1. **Pain is concentrated, not spread evenly.** Support calls (2.94/5) and the
   Outage / Product-Bug themes (~2.3–2.5 /5, 83–94% churn-signal rate) are where
   customers are actively frustrated. Compliance and Onboarding calls are
   healthy (4.3–4.7 /5). That contrast is a ready-made prioritisation map: the
   next reliability and CS dollar should go to the bug/outage workflows, not
   everywhere at once.

2. **One incident, many invoices at risk.** The Detect outage is the clearest
   example of why transcript intelligence beats reading calls one at a time. Only
   18 calls are *about* the outage, but its fallout ripples into **46 calls
   across 23 customer accounts** — turning an internal reliability problem into a
   quantifiable retention exposure. No single transcript shows this; the
   aggregate does.

3. **The same data serves four different leaders.** A churn early-warning board
   for CS/Sales, a demand-weighted feature backlog for Product, an
   incident→revenue map for Engineering, and an action-item ledger for everyone —
   all fall out of the *same* enrichment pass. That multiplexing is the real
   product thesis behind "Transcript Intelligence."

**Bottom line:** sentiment on its own is a vanity chart. Tied to call type,
theme, and churn signals, it becomes a decision tool that ranks *which accounts
and which workflows to fix first* — and this dependency-free pipeline produces
that ranking reproducibly in well under a second.

### What I'd do next

- **Validate the labels.** Spot-check a sample to estimate sentiment / key-moment
  precision before anyone acts on the churn board.
- **Discover emergent themes.** Add embedding clustering at scale to surface
  themes the fixed taxonomy can't name, then fold the good clusters back into the
  rules.
- **Close the loop on action items.** Track whether commitments made in one call
  are referenced as done in the next — a cheap, high-signal follow-through metric.
