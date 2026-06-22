## Slide 1

**[Image 1]**

(decorative — no data)

Cross-Country TFP in ASEAN

A Panel-Data Analysis Using World Development Indicators

By: Atitaya Pongpanngam
Submitted to: Assoc. Prof. Monthien Satimanon
Faculty of Economics, Thammasat University — May 2026

**[Image 2]**

(decorative — no data)

---

## Slide 2

MOTIVATION: WHY STUDY ASEAN PRODUCTIVITY?

ASEAN growth differs by productivity, not only capital and labour

Why This Study?

ASEAN economies show very different growth paths over 2000-2023. Singapore and Malaysia maintain high income and productivity levels, while Vietnam and Cambodia show rapid industrialization and catch-up.

2

---

## Slide 3

RESEARCH QUESTION

Central Research Question

Which ASEAN economies have driven productivity growth between 2000 and 2023, and how does the answer depend on whether we estimate or calibrate the capital share parameter alpha?

**[Image 3]**

(decorative — no data)

Estimated α

Calibrated α

Obtained from panel-data regression on WDI data

Standard macroeconomic assumption: α = 1/3

3

---

## Slide 4

TFP is recovered from the Cobb-Douglas framework

Y

K

L

A

Real GDP

Capital stock

Labour force

Total factor productivity

TFP (A) measures the part of output not explained by capital and labour inputs. It captures technology, efficiency, and institutions.

**[Image 4]**

(decorative — no data)

4

---

## Slide 5

GDP per worker shows large cross-country differences

Key Summary Statistics

Log GDP Per Worker Trends (2000-2023)

**[Image 5]**

Title: *Not specified*

Y-axis label: lny  
Y-axis range: 7 to 12

X-axis label: Year  
X-axis range: 2000 to 2025

Legend/Series:
- Cambodia (blue)
- Thailand (red)
- Indonesia (green)
- Brunei (yellow)
- Lao (purple)
- Malaysia (orange)
- Myanmar (teal)
- Philippines (brown)
- Singapore (light blue)
- Vietnam (dark yellow/orange)

Data/Trends/Relationships:
- All countries show a generally increasing trend in "lny" from 2000 to 2025.
- Indonesia and Brunei consistently have the highest values (above 11) for "lny" throughout the time period.
- Cambodia starts out with the lowest "lny" (around 7), but increases steadily and narrows the gap by 2025.
- Vietnam, Lao, Myanmar, and the Philippines show steady growth.
- Thailand, Malaysia, and Singapore remain near the middle to upper range.
- There is no crossover between the highest group (Indonesia, Brunei), the middle group (Malaysia, Singapore, Thailand, Vietnam), and the lowest group (Cambodia, Lao, Myanmar, Philippines) throughout the timeline.

9.27

Avg. log GDP/worker

Std. dev. = 1.24

9.98

Avg. log capital/worker

Std. dev. = 1.43

Highest: Singapore and Brunei
Lowest: Cambodia and Laos
Highest investment: Indonesia

Clear divergence between high-income (Singapore, Brunei) and developing ASEAN economies, with Vietnam showing a strong upward trajectory.

5

---

## Slide 6

DATA CONSTRUCTION

Capital stock is constructed using the Perpetual Inventory Method

WDI does not directly provide capital stock data. We construct it using the Perpetual Inventory Method (PIM), a standard approach in macroeconomics.

Two Key Equations

**[Image 6]**

\( K_0 = \frac{I_0}{g + \delta} \)

**[Image 7]**

(decorative — no data)

Where:

I = gross capital formation (investment)
δ = depreciation rate
g = long-run growth rate

Key assumption: Baseline depreciation rate = 6% (robustness checks use 4% and 8%)

6

---

## Slide 7

DESCRIPTIVE EVIDENCE

Singapore leads ASEAN productivity

Average TFP Levels (log)

Average Annual TFP Growth

Rankings are broadly stable under both estimated and calibrated α.

**[Image 8]**

Legend:
- Estimated α (light brown)
- Calibrated α (dark brown)

X-axis: Value range from -2.5 to 2.5  
Y-axis: Country

Data (approximate values, dark brown for Calibrated α, light brown for Estimated α):

- Vietnam:  
  - Estimated α: ~2.2  
  - Calibrated α: ~2.2

- Singapore:  
  - Estimated α: ~1.5  
  - Calibrated α: ~1.3

- Indonesia:  
  - Estimated α: ~1.6  
  - Calibrated α: ~1.5

- Cambodia:  
  - Estimated α: ~1.2  
  - Calibrated α: ~1.6

- Laos:  
  - Estimated α: ~1.0  
  - Calibrated α: ~1.3

- Thailand:  
  - Estimated α: ~0.7  
  - Calibrated α: ~1.1

- Malaysia:  
  - Estimated α: ~0.7  
  - Calibrated α: ~1.0

- Philippines:  
  - Estimated α: ~0.7  
  - Calibrated α: ~0.8

- Brunei:  
  - Estimated α: ~-2.1  
  - Calibrated α: ~-2.0

General trends:
- Most countries have positive α values, with Brunei being a negative outlier.
- Vietnam has the highest α, both estimated and calibrated.
- Estimated and calibrated α values are generally similar per country, but some (e.g., Cambodia, Malaysia, Thailand) show moderate calibration adjustments.

Singapore (SGP): lntfp_est = 7.51 | lntfp_cal = 8.03 — highest in ASEAN

**[Image 9]**

(decorative — no data)

Brunei (BRN): lntfp_est = 7.34 | lntfp_cal = 7.84 — advanced production structure

**[Image 9]**

(decorative — no data)

Malaysia (MYS): lntfp_est = 6.62 | lntfp_cal = 7.06 — strong technological adoption

**[Image 9]**

(decorative — no data)

Cambodia (KHM), Laos (LAO), and Vietnam (VNM) sit at the bottom of the regional TFP distribution.

Average annual TFP growth rates (%) under estimated and calibrated α. Vietnam leads; Brunei is the only economy with negative TFP growth.

7

---

## Slide 8

GROWTH DYNAMICS

Vietnam records the fastest TFP growth

While Singapore leads in absolute productivity levels, Vietnam shows the strongest productivity growth over 2000-2023. This reflects rapid industrialization and integration into global value chains.

**[Image 10]**

(decorative — no data)

**[Image 10]**

(decorative — no data)

Level leader = Singapore; Growth leader = Vietnam

**[Image 11]**

(decorative — no data)

Vietnam

Singapore

2.08% average annual TFP growth (estimated alpha)

1.74% (second highest)

Growth leadership is concentrated in economies undergoing faster structural change, while mature frontier economies expand more gradually.

**[Image 10]**

(decorative — no data)

**[Image 12]**

(decorative — no data)

Indonesia

Malaysia, Philippines, Thailand

1.68% (third highest)

Moderate growth (1.1-1.4%)

**[Image 10]**

(decorative — no data)

Brunei

-2.27% (only economy with negative TFP growth)

8

---

## Slide 9

ECONOMETRIC METHODS

Four panel estimators are used to estimate alpha

To estimate the capital share parameter alpha, we use four different panel data methods. Each has different assumptions and controls for different sources of bias.

Pooled OLS

Fixed Effects

Random Effects

Ignores country heterogeneity. Likely upward biased.

Controls for time-invariant country differences. Removes country-specific intercepts.

Intermediate approach. Assumes country effects are uncorrelated with regressors.

Two-Way Fixed Effects

Controls both country and year effects. Most comprehensive specification.

9

---

## Slide 10

ECONOMETRIC RESULTS

Estimated alpha falls after controlling for country and year effects

The per-worker Cobb-Douglas production function is estimated using four panel methods. Cluster-robust standard errors are clustered at the country level.

Model

Estimated α

Interpretation

Pooled OLS

0.852***

Likely upward biased; ignores country heterogeneity

Fixed Effects

0.507***

Controls for time-invariant country differences

Random Effects

0.612***

Intermediate; assumes RE uncorrelated with regressors

Two-Way Fixed Effects

0.385**

Most plausible; controls country + year effects

Key Takeaway: The TWFE estimate of 0.385 falls within the standard theoretical range of 0.25-0.45, making it the most economically credible specification.

**[Image 13]**

(decorative — no data)

10

---

## Slide 11

ECONOMETRIC VALIDATION

Country-specific effects bias simple regressions

Why Pooled OLS Overstates α
Countries with persistently high productivity also tend to have high capital accumulation. Ignoring this causes an upward bias — the capital share rises from 0.385 to 0.852 in the pooled regression.
Hausman Specification Test

Test Statistic

p-value

Conclusion

chi-square(1) = 1520.76

0.0000 — rejects H₀ at all significance levels

Random effects is inconsistent. Fixed effects methods are preferred.

11

---

## Slide 12

TFP DYNAMICS

TFP trajectories reveal partial convergence across ASEAN

TFP trajectories for all 10 ASEAN countries from 2000-2023, comparing results using estimated alpha versus a calibrated alpha of 1/3.

TFP Trajectories — Estimated α

TFP Trajectories — Calibrated α = 1/3

**[Image 14]**

Title: TFP Trajectories Est

X-axis: Year (Range: 2000 to 2025)
Y-axis: Log TFP (Range: 5 to 8)

Legend/Series:
- BRN (light blue)
- IDN (red)
- KHM (green)
- LAO (yellow)
- MYS (purple)
- PHL (orange)
- SGP (pink)
- THA (brown)
- VNM (cyan)

Data/Trends:
- BRN starts near Log TFP 8 in 2000, generally declines over time, plateaus, and slightly increases after 2015.
- MYS consistently holds the second-highest Log TFP, showing a gradual increase from 2000 to 2025.
- SGP, THA, and PHL are clustered in the middle range (around Log TFP 6), with gradual increases.
- IDN, KHM, LAO, and VNM start in the lower range (Log TFP 5 to 6). VNM and KHM show notable increases over time.
- Most countries present steady or slightly increasing TFP trends, with BRN being the exception with an initial decline.

**[Image 15]**

Title: TFP Trajectories Cal

X-axis: Year (Range: 2000 to 2025)
Y-axis: Log TFP (Range: 5.5 to 8.5)

Legend/Series:
- BRN (Blue)
- IDN (Brownish Red)
- KHM (Teal)
- LAO (Yellow)
- MYS (Purple)
- PHL (Orange)
- SGP (Light Blue)
- THA (Maroon)
- VNM (Greenish Cyan)

Trends/Relationships:
- SGP has the highest Log TFP values consistently, remaining above 8.
- MYS follows with Log TFP levels just below 7.
- BRN, THA, and PHL form the middle group with Log TFP levels between 6 and 6.5.
- LAO, VNM, KHM, and IDN have the lowest Log TFP values, around 5.5 to 6.
- Most countries show a gradual increase in Log TFP from 2000 to 2025, with some variation and flat trends for certain periods.
- No country shows a marked decline over the period.

Singapore

Brunei

Vietnam

Cambodia and Laos

Highest TFP, stable upward trend

High initial level but gradual decline

Steepest upward trajectory

Start low, show moderate improvement

Both specifications produce similar patterns, confirming that the main productivity findings are robust to the choice of capital share parameter.

**[Image 16]**

(decorative — no data)

12

---

## Slide 13

ROBUSTNESS ANALYSIS

Productivity, not only capital accumulation, drives long-run ASEAN growth

The two-way fixed effects model is re-estimated using capital stocks constructed under three different depreciation rates. The estimated α remains virtually unchanged across all specifications.

Depreciation Rate

Estimated α (TWFE)

4%

0.382

6% (Baseline)

0.385

8%

0.389

Key Finding: All estimates remain close to 0.38 and within the theoretically plausible range of 0.25-0.45.

**[Image 17]**

(decorative — no data)

13

---

## Slide 14

GROWTH DYNAMICS

Convergence Analysis: Evidence of Beta-Convergence

To examine ASEAN-level convergence, initial TFP levels in 2000 were plotted against cumulative TFP growth during 2000-2023.

Key Findings

**[Image 18]**

Title: Cumulative TFP Growth (2000-2023)

Legend/Series:
- ● Cumulative TFP Growth (2000-2023)

X-Axis: Initial TFP (2000) [Range: 35 to 95]
Y-Axis: Cumulative TFP Growth (2000-2023) [Range: 20 to 80]

Data points (approximate, based on plot location):
- (37, 75)
- (43, 80)
- (56, 55)
- (70, 45)
- (76, 35)
- (92, 20)

Trends/Relationships:
- As Initial TFP (2000) increases, Cumulative TFP Growth (2000-2023) decreases. This suggests a negative relationship between initial TFP levels and subsequent cumulative TFP growth.

Negative relationship: Initial TFP vs. growth

Lower-productivity economies grow faster

Partial convergence occurring in ASEAN

Technological catch-up is measurable

The relationship appears generally negative, suggesting evidence of β-convergence within ASEAN economies. Countries with relatively low initial TFP levels, such as Vietnam and Cambodia, tended to experience faster productivity growth over the sample period.

**[Image 19]**

(decorative — no data)

Lower initial TFP levels are associated with faster cumulative growth, consistent with beta-convergence and catch-up dynamics across ASEAN.

14

---

## Slide 15

CONCLUSION

Productivity, not only capital accumulation, drives long-run ASEAN growth

Acknowledged Limitations

Main Conclusions

Labour input does not account for human capital quality or hours worked
Capacity utilization is unobserved
Informal-sector activity may bias GDP and labour measurements

Estimated alpha = 0.385 is the most plausible
Singapore leads in TFP levels, Vietnam leads in TFP growth
ASEAN shows partial beta-convergence
Findings are robust under both estimated and calibrated alpha

Capital accumulation matters, but sustained growth depends on productivity. ASEAN economies must invest in technology, human capital, and institutional quality to maintain long-run growth.

**[Image 17]**

(decorative — no data)

---

## Slide 16

Q&A
