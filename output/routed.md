## Slide 1  (vision)

# Cross-Country TFP in ASEAN

*A Panel-Data Analysis Using World Development Indicators*

---

By: Atitaya Pongpanngam  
Submitted to: Assoc. Prof. Monthien Satimanon  
Faculty of Economics, Thammasat University — May 2026

---

*Background: Abstract, flowing layered pattern in neutral colors.*

*No charts, diagrams, tables, or additional visual data presented.*

---

## Slide 2  (vision)

# MOTIVATION: WHY STUDY ASEAN PRODUCTIVITY?

ASEAN growth differs by productivity, not only capital and labour

## Why This Study?

ASEAN economies show very different growth paths over 2000-2023. Singapore and Malaysia maintain high income and productivity levels, while Vietnam and Cambodia show rapid industrialization and catch-up.

2

---

## Slide 3  (vision)

# RESEARCH QUESTION

## Central Research Question

Which ASEAN economies have driven productivity growth between 2000 and 2023, and how does the answer depend on whether we estimate or calibrate the capital share parameter alpha?

---

- **Estimated α**  
  Obtained from panel-data regression on WDI data

- **Calibrated α**  
  Standard macroeconomic assumption: α = 1/3

---

3

---

## Slide 4  (vision)

TFP is recovered from the Cobb-Douglas 
framework

Y  
Real GDP

K  
Capital stock

L  
Labour force

A  
Total factor 
productivity

TFP (A) measures the part of output not explained by capital and labour inputs. It captures technology, 
efficiency, and institutions.

---

4

---

## Slide 5  (vision)

# GDP per worker shows large cross-country differences
**Key Summary Statistics**

**9.27**  
Avg. log GDP/worker  
Std. dev. = 1.24

**9.9**  
Avg. log capital/worker  
Std. dev. = 1.43

- Highest: Singapore and Brunei
- Lowest: Cambodia and Laos
- Highest investment: Indonesia

## Log GDP Per Worker Trends (2000–2023)

_Chart: Line graph depicting trends in log GDP per worker for ten ASEAN countries from 2000 to 2023._

Legend (color coded):
- Cambodia
- Thailand
- Indonesia
- Brunei
- Lao
- Malaysia
- Myanmar
- Philippines
- Singapore
- Vietnam

**Y-axis**: ln(y)  
**X-axis**: Year (2000 to 2025)

**Trends:**
- Singapore and Brunei show the highest and relatively stable log GDP per worker.
- Vietnam shows a strong upward trend.
- Cambodia and Lao are at the lower end throughout the period.
- Other countries (Malaysia, Thailand, Indonesia, Philippines, Myanmar) are distributed between these extremes.

Clear divergence between high-income (Singapore, Brunei) and developing ASEAN economies, with Vietnam showing a strong upward trajectory.

5

---

## Slide 6  (vision)

DATA CONSTRUCTION

# Capital stock is constructed using the Perpetual Inventory Method

WDI does not directly provide capital stock data. We construct it using the Perpetual Inventory Method (PIM), a standard approach in macroeconomics.

## Two Key Equations

K₀ = I₀ / (g + δ)

Kₜ = (1 − δ) × Kₜ₋₁ + Iₜ

**Where**:  
• I = gross capital formation (investment)  
• δ = depreciation rate  
• g = long-run growth rate

**Key assumption:** Baseline depreciation rate = 6% (robustness checks use 4% and 8%)

6

---

## Slide 7  (vision)

# DESCRIPTIVE EVIDENCE

## Singapore leads ASEAN productivity

### Average TFP Levels (log)

Rankings are broadly stable under both estimated and calibrated α.

- Singapore (SGP): lntfp_est = 7.51 | lntfp_cal = 8.03 — highest in ASEAN
- Brunei (BRN): lntfp_est = 7.34 | lntfp_cal = 7.84 — advanced production structure
- Malaysia (MYS): lntfp_est = 6.62 | lntfp_cal = 7.06 — strong technological adoption

Cambodia (KHM), Laos (LAO), and Vietnam (VNM) sit at the bottom of the regional TFP distribution.

---

### Average Annual TFP Growth

#### [Image: Horizontal bar chart]

- Title: Average Annual TFP Growth
- Legend:
  - ■ Estimated α
  - ■ Calibrated α
- The chart displays average annual TFP growth rates (%) for ASEAN countries, under estimated and calibrated α.

#### Y-axis (Countries, top to bottom):
- Vietnam
- Singapore
- Indonesia
- Cambodia
- Laos
- Thailand
- Malaysia
- Philippines
- Brunei

#### X-axis:
- Ranges from approximately -2% to +2%

#### Data/Trends (as depicted by bar lengths):
- Vietnam has the highest positive TFP growth (around 2%).
- Singapore and Indonesia have strong positive TFP growth (slightly below Vietnam).
- Cambodia, Laos, and Thailand show moderate positive TFP growth.
- Malaysia and the Philippines have lower positive TFP growth.
- Brunei is the only country with negative TFP growth, near -1.5%.

Caption below chart:
> Average annual TFP growth rates (%) under estimated and calibrated α.  
> Vietnam leads; Brunei is the only economy with negative TFP growth.

---

Page number: 7

---

## Slide 8  (vision)

# GROWTH DYNAMICS

## Vietnam records the fastest TFP growth

While Singapore leads in absolute productivity levels, Vietnam shows the strongest productivity growth over 2000-2023. This reflects rapid industrialization and integration into global value chains.

---

### Vietnam
2.08% average annual TFP growth (estimated alpha)

### Singapore
1.74% (second highest)

### Indonesia
1.68% (third highest)

### Malaysia, Philippines, Thailand
Moderate growth (1.1-1.4%)

### Brunei
-2.27% (only economy with negative TFP growth)

---

> **Level leader = Singapore; Growth leader = Vietnam**

Growth leadership is concentrated in economies undergoing faster structural change, while mature frontier economies expand more gradually.

---

Page number: 8

---

### Slide structure and visual elements:

- The slide is text-based, comparing Total Factor Productivity (TFP) growth rates for different Southeast Asian economies, listing annual growth percentages.
- There is a blue-highlighted information box:  
    - "Level leader = Singapore; Growth leader = Vietnam"
- No charts, tables, or other complex visuals are present.

---

## Slide 9  (vision)

# ECONOMETRIC METHODS

Four panel estimators are used to estimate  
alpha

To estimate the capital share parameter alpha, we use four different panel data methods. Each has different assumptions and controls for different sources of bias.

- **Pooled OLS**  
  Ignores country heterogeneity. Likely upward biased.

- **Fixed Effects**  
  Controls for time-invariant country differences. Removes country-specific intercepts.

- **Random Effects**  
  Intermediate approach. Assumes country effects are uncorrelated with regressors.

- **Two-Way Fixed Effects**  
  Controls both country and year effects. Most comprehensive specification.

9

---

## Slide 10  (vision)

# ECONOMETRIC RESULTS

**Estimated alpha falls after controlling for country and year effects**

The per-worker Cobb-Douglas production function is estimated using four panel methods. Cluster-robust standard errors are clustered at the country level.

| Model                | Estimated α | Interpretation                                             |
|----------------------|-------------|-----------------------------------------------------------|
| Pooled OLS           | 0.852***    | Likely upward biased; ignores country heterogeneity        |
| Fixed Effects        | 0.507***    | Controls for time-invariant country differences            |
| Random Effects       | 0.612***    | Intermediate; assumes RE uncorrelated with regressors      |
| Two-Way Fixed Effects| 0.385**     | Most plausible; controls country + year effects            |

**Key Takeaway:** The TWFE estimate of 0.385 falls within the standard theoretical range of 0.25-0.45, making it the most economically credible specification.

10

---

## Slide 11  (vision)

# ECONOMETRIC VALIDATION

---

## Country-specific effects bias simple regressions

### Why Pooled OLS Overstates α

Countries with persistently high productivity also tend to have high capital accumulation. Ignoring this causes an upward bias — the capital share rises from 0.385 to 0.852 in the pooled regression.

---

### Hausman Specification Test

- **Test Statistic:** chi-square(1) = 1520.76
- **p-value:** 0.0000 — rejects H₀ at all significance levels

---

### Conclusion

Random effects is inconsistent. Fixed effects methods are preferred.

---

## Slide 12  (vision)

# TFP DYNAMICS

## TFP trajectories reveal partial convergence across ASEAN
*TFP for all 10 ASEAN countries from 2000-2023, comparing results using estimated alpha versus a calibrated alpha of 1/3.*

### TFP Trajectories — Estimated α          TFP Trajectories — Calibrated α = 1/3

#### [Two side-by-side line charts:]

- **Left chart: TFP Trajectories Est**
  - Y-axis: Log TFP (approximate range 5 to 8)
  - X-axis: Year (2000 to 2025)
  - Countries represented by colored lines:
    - BRN (Brunei)
    - IDN (Indonesia)
    - KHM (Cambodia)
    - LAO (Laos)
    - MYS (Malaysia)
    - PHL (Philippines)
    - SGP (Singapore)
    - THA (Thailand)
    - VNM (Vietnam)
  - Key trends:
    - Singapore has the highest TFP with a stable, upward trend.
    - Brunei starts at a high level but declines gradually.
    - Vietnam shows the steepest upward trajectory.
    - Cambodia and Laos start low and show moderate improvement.

- **Right chart: TFP Trajectories Cal**
  - Y-axis: Log TFP (approximate range 5.5 to 8)
  - X-axis: Year (2000 to 2025)
  - Same countries and color coding as the left chart.
  - Key trends and comparisons similar to those on the left chart.

---

#### Country-specific summaries (boxes below graphs):

- **Singapore**  
  Highest TFP, stable upward trend

- **Brunei**  
  High initial level but gradual decline

- **Vietnam**  
  Steepest upward trajectory

- **Cambodia and Laos**  
  Start low, show moderate improvement

---

> **Both specifications produce similar patterns, confirming that the main productivity findings are robust to the choice of capital share parameter.**

---

12

---

## Slide 13  (vision)

# ROBUSTNESS ANALYSIS

**Productivity, not only capital accumulation,  
drives long-run ASEAN growth**

The two-way fixed effects model is re-estimated using capital stocks constructed under three different depreciation rates.  
The estimated $\alpha$ remains virtually unchanged across all specifications.

**Depreciation Rate | Estimated (TWFE) $\alpha$**
- 4%: 0.382
- 6% (Baseline): 0.385
- 8%: 0.389

**Key Finding:** All estimates remain close to 0.38 and within the theoretically plausible range of 0.25-0.45.

13

---

## Slide 14  (vision)

# GROWTH DYNAMICS

## Convergence Analysis: Evidence of Beta-Convergence

To examine ASEAN-level convergence, initial TFP levels in 2000 were plotted against cumulative TFP growth during 2000-2023.

Lower initial TFP levels are associated with faster cumulative growth, consistent with beta-convergence and catch-up dynamics across ASEAN.

---

### Chart: Cumulative TFP Growth (2000-2023) vs. Initial TFP (2000)
- **X-axis:** Initial TFP (2000) [Scale: 35 to 95]
- **Y-axis:** Cumulative TFP Growth (2000-2023) [Scale: 20 to 80]
- **Data points:** Several dots showing a negative relationship. As Initial TFP increases, Cumulative TFP Growth decreases.
- **Caption:** Lower initial TFP levels are associated with faster cumulative growth, consistent with beta-convergence and catch-up dynamics across ASEAN.

---

## Key Findings

- **Negative relationship: Initial TFP vs. growth**
- Lower-productivity economies grow faster
- Partial convergence occurring in ASEAN
- Technological catch-up is measurable

> The relationship appears generally negative, suggesting evidence of β-convergence within ASEAN economies. Countries with relatively low initial TFP levels, such as Vietnam and Cambodia, tended to experience faster productivity growth over the sample period.

---

1  
4

---

## Slide 15  (vision)

# CONCLUSION

**Productivity, not only capital accumulation,  
drives long-run ASEAN growth**

---

## Acknowledged Limitations
- Labour input does not account for human capital quality or hours worked
- Capacity utilization is unobserved
- Informal-sector activity may bias GDP and labour measurements

---

## Main Conclusions
1. Estimated alpha = 0.385 is the most plausible
2. Singapore leads in TFP levels, Vietnam leads in TFP growth
3. ASEAN shows partial beta-convergence
4. Findings are robust under both estimated and calibrated alpha

---

Capital accumulation matters, but sustained growth depends on productivity. ASEAN economies must invest in technology, human capital, and institutional quality to maintain long-run growth.

---

## Slide 16  (text)

Q&A
