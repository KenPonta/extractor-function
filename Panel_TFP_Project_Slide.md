# Cross-Country TFP in ASEAN — Full Slide-by-Slide Markdown

> Ground-truth transcription of `Panel_TFP_Project_Slide.pptx` (16 slides).
> Body text is verbatim. Lines marked **[Visual]** describe charts, diagrams, equations, and
> layout that are *not* recoverable from python-pptx text extraction (they are embedded as
> images/vector shapes, not as PICTURE or chart objects). Speaker notes are included verbatim.

---

## Slide 1

**[Visual — background]** Full-bleed decorative background: a soft, flowing wood-grain / marble-like abstract texture in cream, beige, and pale grey. No data content.

**Cross-Country TFP in ASEAN** *(large bold centered title)*

A Panel-Data Analysis Using World Development Indicators

*(horizontal divider line)*

By: Atitaya Pongpanngam
Submitted to: Assoc. Prof. Monthien Satimanon
Faculty of Economics, Thammasat University — May 2026

*Speaker notes:* 1

---

## Slide 2

`MOTIVATION: WHY STUDY ASEAN PRODUCTIVITY?` *(eyebrow tag, pale-pink pill)*

**ASEAN growth differs by productivity, not only capital and labour** *(headline)*

**Why This Study?**

ASEAN economies show very different growth paths over 2000-2023. Singapore and Malaysia maintain high income and productivity levels, while Vietnam and Cambodia show rapid industrialization and catch-up.

**[Visual — layout]** Clean editorial layout on white: eyebrow tag, large headline, bold sub-head, single body paragraph. No chart. Page number "2" bottom-right.

*Speaker notes:* 2

---

## Slide 3

`RESEARCH QUESTION` *(eyebrow tag)*

**Central Research Question** *(headline)*

**[Visual — callout box, peach/tan, with a small note icon]**
Which ASEAN economies have driven productivity growth between 2000 and 2023, and how does the answer depend on whether we estimate or calibrate the capital share parameter alpha?

**[Visual — two comparison cards, each with a dark left accent bar]**

- **Estimated α** — Obtained from panel-data regression on WDI data
- **Calibrated α** — Standard macroeconomic assumption: α = 1/3

*Speaker notes:* 3

---

## Slide 4

**TFP is recovered from the Cobb-Douglas framework** *(headline)*

**[Visual — four definition cards in a row]**

- **Y** — Real GDP
- **K** — Capital stock
- **L** — Labour force
- **A** — Total factor productivity

**[Visual — callout box, peach, with note icon]**
TFP (A) measures the part of output not explained by capital and labour inputs. It captures technology, efficiency, and institutions.

*Speaker notes:* 4

---

## Slide 5

**GDP per worker shows large cross-country differences** *(headline)*

**Key Summary Statistics**

**[Visual — two large stat callouts on the left]**

- **9.27** — Avg. log GDP/worker (Std. dev. = 1.24)
- **9.98** — Avg. log capital/worker (Std. dev. = 1.43)

- Highest: Singapore and Brunei
- Lowest: Cambodia and Laos
- Highest investment: Indonesia

**[Visual — line chart, right side]** Title: **"Log GDP Per Worker Trends (2000-2023)."** X-axis = Year (2000–2025); Y-axis = `lny` (log GDP per worker), range ~7 to ~12. One line per country (legend: Cambodia, Thailand, Indonesia, Brunei, Lao, Malaysia, Myanmar, Philippines, Singapore, Vietnam). Reading the chart:
  - **Singapore** (cyan) highest, rising from ~11.1 to ~11.6.
  - **Brunei** (yellow) starts highest at ~11.3 but drifts down to ~10.9.
  - **Malaysia** (salmon) ~9.7 → ~10.0.
  - **Thailand** (pink) ~8.5 → ~9.3; **Philippines** (maroon) and **Indonesia** (green) ~8.3–8.5 → ~9.0.
  - **Lao** (purple) ~7.8 → ~8.6 (series ends ~2016); **Vietnam** (gold) ~7.8 → ~8.8; **Myanmar** (light blue) rising mid-pack.
  - **Cambodia** (blue) lowest, ~7.2 → ~8.2.
  - Overall: wide gaps that persist, with a steep climb for Vietnam.

Caption: Clear divergence between high-income (Singapore, Brunei) and developing ASEAN economies, with Vietnam showing a strong upward trajectory.

*Speaker notes:* 5

---

## Slide 6

`DATA CONSTRUCTION` *(eyebrow tag, outlined)*

**Capital stock is constructed using the Perpetual Inventory Method** *(headline)*

WDI does not directly provide capital stock data. We construct it using the Perpetual Inventory Method (PIM), a standard approach in macroeconomics.

**Two Key Equations**

**[Visual — two equations rendered as math (not in the text layer)]**

- K₀ = I₀ / (g + δ)
- Kₜ = (1 − δ) × Kₜ₋₁ + Iₜ

**Where:**

- I = gross capital formation (investment)
- δ = depreciation rate
- g = long-run growth rate

**Key assumption:** Baseline depreciation rate = 6% (robustness checks use 4% and 8%)

*Speaker notes:* 6

---

## Slide 7

`DESCRIPTIVE EVIDENCE` *(eyebrow tag)*

**Singapore leads ASEAN productivity** *(headline)*

**Average TFP Levels (log)**

Rankings are broadly stable under both estimated and calibrated α.

- → Singapore (SGP): lntfp_est = 7.51 | lntfp_cal = 8.03 — highest in ASEAN
- → Brunei (BRN): lntfp_est = 7.34 | lntfp_cal = 7.84 — advanced production structure
- → Malaysia (MYS): lntfp_est = 6.62 | lntfp_cal = 7.06 — strong technological adoption

Cambodia (KHM), Laos (LAO), and Vietnam (VNM) sit at the bottom of the regional TFP distribution.

**[Visual — horizontal bar chart, right side]** Title: **"Average Annual TFP Growth."** Two series toggled by legend pills: **Estimated α** and **Calibrated α** (two brown shades). Y-axis = Country; X-axis = TFP growth %, range -2 to +2. Two bars per country. Reading the chart (ordered top to bottom):
  - **Vietnam** ~+2.1 to +2.3 (longest positive bars).
  - **Singapore** ~+1.7; **Indonesia** ~+1.6–1.7; **Cambodia** ~+1.5–1.9; **Laos** ~+1.3–1.7.
  - **Thailand** ~+1.3–1.5; **Malaysia** ~+1.0–1.2; **Philippines** ~+1.0–1.3.
  - **Brunei** the only negative, ~ -2.0 to -2.2 (bars extend left of zero).

Caption: Average annual TFP growth rates (%) under estimated and calibrated α. Vietnam leads; Brunei is the only economy with negative TFP growth.

*Speaker notes:* 7

---

## Slide 8

`GROWTH DYNAMICS` *(eyebrow tag)*

**Vietnam records the fastest TFP growth** *(headline)*

While Singapore leads in absolute productivity levels, Vietnam shows the strongest productivity growth over 2000-2023. This reflects rapid industrialization and integration into global value chains.

**[Visual — grid of 5 items, each with a small flag/chart icon above a divider]**

- **Vietnam** — 2.08% average annual TFP growth (estimated alpha)
- **Singapore** — 1.74% (second highest)
- **Indonesia** — 1.68% (third highest)
- **Malaysia, Philippines, Thailand** — Moderate growth (1.1-1.4%)
- **Brunei** — -2.27% (only economy with negative TFP growth)

**[Visual — blue callout box with info icon]** Level leader = Singapore; Growth leader = Vietnam

Growth leadership is concentrated in economies undergoing faster structural change, while mature frontier economies expand more gradually.

*Speaker notes:* 8

---

## Slide 9

`ECONOMETRIC METHODS` *(eyebrow tag)*

**Four panel estimators are used to estimate alpha** *(headline)*

To estimate the capital share parameter alpha, we use four different panel data methods. Each has different assumptions and controls for different sources of bias.

**[Visual — three cards in a row plus one wide card below]**

- **Pooled OLS** — Ignores country heterogeneity. Likely upward biased.
- **Fixed Effects** — Controls for time-invariant country differences. Removes country-specific intercepts.
- **Random Effects** — Intermediate approach. Assumes country effects are uncorrelated with regressors.
- **Two-Way Fixed Effects** — Controls both country and year effects. Most comprehensive specification.

*Speaker notes:* 9

---

## Slide 10

`ECONOMETRIC RESULTS` *(eyebrow tag)*

**Estimated alpha falls after controlling for country and year effects** *(headline)*

The per-worker Cobb-Douglas production function is estimated using four panel methods. Cluster-robust standard errors are clustered at the country level.

**[Visual — results table]**

| Model | Estimated α | Interpretation |
|---|---|---|
| Pooled OLS | 0.852*** | Likely upward biased; ignores country heterogeneity |
| Fixed Effects | 0.507*** | Controls for time-invariant country differences |
| Random Effects | 0.612*** | Intermediate; assumes RE uncorrelated with regressors |
| **Two-Way Fixed Effects** | **0.385**\*\* | **Most plausible; controls country + year effects** |

**[Visual — green callout box with checkmark]** **Key Takeaway:** The TWFE estimate of 0.385 falls within the standard theoretical range of 0.25-0.45, making it the most economically credible specification.

*Speaker notes:* 10

---

## Slide 11

`ECONOMETRIC VALIDATION` *(eyebrow tag)*

**Country-specific effects bias simple regressions** *(headline)*

**Why Pooled OLS Overstates α**

Countries with persistently high productivity also tend to have high capital accumulation. Ignoring this causes an upward bias — the capital share rises from 0.385 to 0.852 in the pooled regression.

**Hausman Specification Test**

**[Visual — three cards, each with a dark left accent bar]**

- **Test Statistic** — chi-square(1) = 1520.76
- **p-value** — 0.0000 — rejects H₀ at all significance levels
- **Conclusion** — Random effects is inconsistent. Fixed effects methods are preferred.

*Speaker notes:* 11

---

## Slide 12

`TFP DYNAMICS` *(eyebrow tag)*

**TFP trajectories reveal partial convergence across ASEAN** *(headline)*

TFP trajectories for all 10 ASEAN countries from 2000-2023, comparing results using estimated alpha versus a calibrated alpha of 1/3.

**[Visual — two side-by-side line charts]** Legend (both): BRN, IDN, KHM, LAO, MYS, PHL, SGP, THA, VNM. X-axis = Year (2000–2025); Y-axis = Log TFP.

- **Left — "TFP Trajectories — Estimated α"** (Y range ~5 to ~8):
  - SGP (light blue) highest, ~7.3 → ~7.7; BRN (blue) ~7.7 declining to ~7.2.
  - MYS (purple) ~6.5 → ~6.75; THA (maroon) ~5.9 → ~6.25; PHL (orange) ~5.85 → ~6.1; IDN (pink) ~6.0 roughly flat.
  - LAO (yellow) ~5.5 → ~5.7 (ends ~2016); VNM (teal) ~5.4 → ~5.85 (steep rise); KHM (green) lowest ~5.1 → ~5.45.
- **Right — "TFP Trajectories — Calibrated α = 1/3"** (Y range ~5.5 to ~8+): same ordering shifted upward — BRN ~8.2 highest, SGP ~7.8 → ~8.2, MYS ~6.9 → ~7.2, and so on down to KHM ~5.45 → ~5.8.
- The two panels show very similar shapes.

**[Visual — four summary cards]**

- **Singapore** — Highest TFP, stable upward trend
- **Brunei** — High initial level but gradual decline
- **Vietnam** — Steepest upward trajectory
- **Cambodia and Laos** — Start low, show moderate improvement

**[Visual — blue callout box with info icon]** Both specifications produce similar patterns, confirming that the main productivity findings are robust to the choice of capital share parameter.

*Speaker notes:* 12

---

## Slide 13

`ROBUSTNESS ANALYSIS` *(eyebrow tag)*

**Productivity, not only capital accumulation, drives long-run ASEAN growth** *(headline)*

The two-way fixed effects model is re-estimated using capital stocks constructed under three different depreciation rates. The estimated α remains virtually unchanged across all specifications.

**[Visual — table]**

| Depreciation Rate | Estimated α (TWFE) |
|---|---|
| 4% | 0.382 |
| **6% (Baseline)** | **0.385** |
| 8% | 0.389 |

**[Visual — green callout box with checkmark]** **Key Finding:** All estimates remain close to 0.38 and within the theoretically plausible range of 0.25-0.45.

*Speaker notes:* 13

---

## Slide 14

`GROWTH DYNAMICS` *(eyebrow tag)*

**Convergence Analysis: Evidence of Beta-Convergence** *(headline)*

To examine ASEAN-level convergence, initial TFP levels in 2000 were plotted against cumulative TFP growth during 2000-2023.

**[Visual — scatter plot, left side]** Title: **"Cumulative TFP Growth (2000-2023)."** X-axis = Initial TFP (2000), range ~35 to ~95; Y-axis = Cumulative TFP Growth, range ~20 to ~80. About six brown points forming a clear downward (negative) pattern:
  - top-left (low initial TFP, high growth): ~(38, 70) and ~(42, 75)
  - middle: ~(56, 57), ~(68, 47), ~(76, 38)
  - bottom-right (high initial TFP, low growth): ~(92, 22)

Caption: Lower initial TFP levels are associated with faster cumulative growth, consistent with beta-convergence and catch-up dynamics across ASEAN.

**Key Findings**

- Negative relationship: Initial TFP vs. growth
- Lower-productivity economies grow faster
- Partial convergence occurring in ASEAN
- Technological catch-up is measurable

**[Visual — green callout box with checkmark]** The relationship appears generally negative, suggesting evidence of β-convergence within ASEAN economies. Countries with relatively low initial TFP levels, such as Vietnam and Cambodia, tended to experience faster productivity growth over the sample period.

*Speaker notes:* 14

---

## Slide 15

`CONCLUSION` *(eyebrow tag)*

**Productivity, not only capital accumulation, drives long-run ASEAN growth** *(headline)*

**[Visual — two columns]**

**Acknowledged Limitations**

- Labour input does not account for human capital quality or hours worked
- Capacity utilization is unobserved
- Informal-sector activity may bias GDP and labour measurements

**Main Conclusions**

1. Estimated alpha = 0.385 is the most plausible
2. Singapore leads in TFP levels, Vietnam leads in TFP growth
3. ASEAN shows partial beta-convergence
4. Findings are robust under both estimated and calibrated alpha

**[Visual — green callout box with checkmark]** Capital accumulation matters, but sustained growth depends on productivity. ASEAN economies must invest in technology, human capital, and institutional quality to maintain long-run growth.

*Speaker notes:* 15

---

## Slide 16

**[Visual]** Single large centered word on a blank white slide:

**Q&A**

*(no speaker notes)*
