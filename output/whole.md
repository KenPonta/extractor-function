## Slide 1

**Cross-Country TFP in ASEAN**  
A Panel-Data Analysis Using World Development Indicators

By: Atitaya Pongpanngam  
Submitted to: Assoc. Prof. Monthien Satimanon  
Faculty of Economics, Thammasat University — May 2026

---

## Slide 2

### MOTIVATION: WHY STUDY ASEAN PRODUCTIVITY?

**ASEAN growth differs by productivity, not only capital and labour**

#### Why This Study?
ASEAN economies show very different growth paths over 2000-2023. Singapore and Malaysia maintain high income and productivity levels, while Vietnam and Cambodia show rapid industrialization and catch-up.

---

## Slide 3

### RESEARCH QUESTION

**Central Research Question**  
Which ASEAN economies have driven productivity growth between 2000 and 2023, and how does the answer depend on whether we estimate or calibrate the capital share parameter alpha?

- **Estimated α**  
  Obtained from panel-data regression on WDI data

- **Calibrated α**  
  Standard macroeconomic assumption: α = 1/3

---

## Slide 4

TFP is recovered from the Cobb-Douglas framework

- **Y:** Real GDP
- **K:** Capital stock
- **L:** Labour force
- **A:** Total factor productivity

TFP (A) measures the part of output not explained by capital and labour inputs. It captures technology, efficiency, and institutions.

---

## Slide 5

### GDP per worker shows large cross-country differences

**Key Summary Statistics**

- 9.27  
  Avg. log GDP/worker  
  Std. dev. = 1.24

- 9.98  
  Avg. log capital/worker  
  Std. dev. = 1.43

- Highest: Singapore and Brunei
- Lowest: Cambodia and Laos
- Highest investment: Indonesia

#### [Line Chart] Log GDP Per Worker Trends (2000-2023)

- Y-axis: ln(y)
- X-axis: Year (2000–2025)
- Series: Cambodia, Thailand, Indonesia, Brunei, Lao, Malaysia, Myanmar, Philippines, Singapore, Vietnam
- Clear divergence between high-income (Singapore, Brunei) and developing ASEAN economies, with Vietnam showing a strong upward trajectory.

---

## Slide 6

### DATA CONSTRUCTION

**Capital stock is constructed using the Perpetual Inventory Method**

WDI does not directly provide capital stock data. We construct it using the Perpetual Inventory Method (PIM), a standard approach in macroeconomics.

#### Two Key Equations

K₀ = I₀ / (g + δ)

Kₜ = (1 – δ) × Kₜ₋₁ + Iₜ

Where:  
- I = gross capital formation (investment)  
- δ = depreciation rate  
- g = long-run growth rate

**Key assumption:** Baseline depreciation rate = 6% (robustness checks use 4% and 8%)

---

## Slide 7

### DESCRIPTIVE EVIDENCE

**Singapore leads ASEAN productivity**

#### Average TFP Levels (log)  
Rankings are broadly stable under both estimated and calibrated α.

- Singapore (SGP): lntfp_est = 7.51 | lntfp_cal = 8.03 — highest in ASEAN
- Brunei (BRN): lntfp_est = 7.34 | lntfp_cal = 7.84 — advanced production structure
- Malaysia (MYS): lntfp_est = 6.62 | lntfp_cal = 7.06 — strong technological adoption

Cambodia (KHM), Laos (LAO), and Vietnam (VNM) sit at the bottom of the regional TFP distribution.

#### [Bar Chart] Average Annual TFP Growth
Two series: Estimated α and Calibrated α  
- Countries: Vietnam, Singapore, Indonesia, Cambodia, Laos, Thailand, Malaysia, Philippines, Brunei
- Vietnam leads; Brunei is the only economy with negative TFP growth.

Average annual TFP growth rates (%) under estimated and calibrated α.

---

## Slide 8

### GROWTH DYNAMICS

**Vietnam records the fastest TFP growth**

While Singapore leads in absolute productivity levels, Vietnam shows the strongest productivity growth over 2000-2023. This reflects rapid industrialization and integration into global value chains.

#### 
- Vietnam: 2.08% average annual TFP growth (estimated alpha)
- Singapore: 1.74% (second highest)
- Indonesia: 1.68% (third highest)

- Malaysia, Philippines, Thailand: Moderate growth (1.1–1.4%)
- Brunei: –2.27% (only economy with negative TFP growth)

**Level leader = Singapore; Growth leader = Vietnam**

Growth leadership is concentrated in economies undergoing faster structural change, while mature frontier economies expand more gradually.

---

## Slide 9

### ECONOMETRIC METHODS

**Four panel estimators are used to estimate alpha**

To estimate the capital share parameter alpha, we use four different panel data methods. Each has different assumptions and controls for different sources of bias.

- **Pooled OLS**  
  Ignores country heterogeneity. Likely upward biased.
- **Fixed Effects**  
  Controls for time-invariant country differences. Removes country-specific intercepts.
- **Random Effects**  
  Intermediate approach. Assumes country effects are uncorrelated with regressors.
- **Two-Way Fixed Effects**  
  Controls both country and year effects. Most comprehensive specification.

---

## Slide 10

### ECONOMETRIC RESULTS

**Estimated alpha falls after controlling for country and year effects**

The per-worker Cobb-Douglas production function is estimated using four panel methods. Cluster-robust standard errors are clustered at the country level.

| Model                 | Estimated α | Interpretation                                                  |
|-----------------------|:-----------|-----------------------------------------------------------------|
| Pooled OLS            | 0.852***   | Likely upward biased; ignores country heterogeneity             |
| Fixed Effects         | 0.507***   | Controls for time-invariant country differences                 |
| Random Effects        | 0.612***   | Intermediate; assumes RE uncorrelated with regressors           |
| Two-Way Fixed Effects | 0.385**    | Most plausible; controls country + year effects                 |

**Key Takeaway:** The TWFE estimate of 0.385 falls within the standard theoretical range of 0.25–0.45, making it the most economically credible specification.

---

## Slide 11

### ECONOMETRIC VALIDATION

**Country-specific effects bias simple regressions**

#### Why Pooled OLS Overstates α  
Countries with persistently high productivity also tend to have high capital accumulation. Ignoring this causes an upward bias — the capital share rises from 0.385 to 0.852 in the pooled regression.

#### Hausman Specification Test  
- Test Statistic chi-square(1) = 1520.76  
- p-value 0.0000 — rejects H₀ at all significance levels

**Conclusion**  
Random effects is inconsistent. Fixed effects methods are preferred.

---

## Slide 12

### TFP DYNAMICS

**TFP trajectories reveal partial convergence across ASEAN**

TFP trajectories for all 10 ASEAN countries from 2000–2023, comparing results using estimated alpha versus a calibrated alpha of 1/3.

#### [Two Line Charts]

**TFP Trajectories — Estimated α**  
- Y-axis: Log TFP  
- X-axis: Year (2000–2025)  
- Countries: BRN, IDN, KHM, LAO, MYS, PHL, SGP, THA, VNM

**TFP Trajectories — Calibrated α = 1/3**  
(Same axes and countries)

- Singapore: Highest TFP, stable upward trend
- Brunei: High initial level but gradual decline
- Vietnam: Steepest upward trajectory
- Cambodia and Laos: Start low, show moderate improvement

**Both specifications produce similar patterns, confirming that the main productivity findings are robust to the choice of capital share parameter.**

---

## Slide 13

### ROBUSTNESS ANALYSIS

**Productivity, not only capital accumulation, drives long-run ASEAN growth**

The two-way fixed effects model is re-estimated using capital stocks constructed under three different depreciation rates. The estimated α remains virtually unchanged across all specifications.

| Depreciation Rate | Estimated α (TWFE) |
|-------------------|:------------------|
| 4%                | 0.382             |
| 6% (Baseline)     | 0.385             |
| 8%                | 0.389             |

**Key Finding:** All estimates remain close to 0.38 and within the theoretically plausible range of 0.25–0.45.

---

## Slide 14

### GROWTH DYNAMICS

**Convergence Analysis: Evidence of Beta-Convergence**

To examine ASEAN-level convergence, initial TFP levels in 2000 were plotted against cumulative TFP growth during 2000–2023.

- Lower initial TFP levels are associated with faster cumulative growth, consistent with beta-convergence and catch-up dynamics across ASEAN.

#### Key Findings

- Negative relationship: Initial TFP vs. growth
- Lower-productivity economies grow faster
- Partial convergence occurring in ASEAN
- Technological catch-up is measurable

#### [Scatter Plot]
- Y-axis: Cumulative TFP Growth (2000–2023)
- X-axis: Initial TFP (2000)
- Each point: Country observation
- Trend: Negative slope (countries with lower initial TFP show higher cumulative growth)

The relationship appears generally negative, suggesting evidence of β-convergence within ASEAN economies. Countries with relatively low initial TFP levels, such as Vietnam and Cambodia, tended to experience faster productivity growth over the sample period.

---

## Slide 15

### CONCLUSION

**Productivity, not only capital accumulation, drives long-run ASEAN growth**

#### Acknowledged Limitations
- Labour input does not account for human capital quality or hours worked
- Capacity utilization is unobserved
- Informal-sector activity may bias GDP and labour measurements

#### Main Conclusions
1. Estimated alpha = 0.385 is the most plausible
2. Singapore leads in TFP levels, Vietnam leads in TFP growth
3. ASEAN shows partial beta-convergence
4. Findings are robust under both estimated and calibrated alpha

Capital accumulation matters, but sustained growth depends on productivity. ASEAN economies must invest in technology, human capital, and institutional quality to maintain long-run growth.

---

## Slide 16

Q&A
