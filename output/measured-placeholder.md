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

**Speaker notes:** 1

---

## Slide 2

MOTIVATION: WHY STUDY ASEAN PRODUCTIVITY?

ASEAN growth differs by productivity, not only capital and labour

Why This Study?

ASEAN economies show very different growth paths over 2000-2023. Singapore and Malaysia maintain high income and productivity levels, while Vietnam and Cambodia show rapid industrialization and catch-up.

2

**Speaker notes:** 2

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

**Speaker notes:** 3

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

**Speaker notes:** 4

---

## Slide 5

GDP per worker shows large cross-country differences

Key Summary Statistics

Log GDP Per Worker Trends (2000-2023)

**[Image 5]**

Title: *(No explicit title given on the chart)*

Y-axis: lnY (range: 7 to 12)

X-axis: Year (range: 2000 to 2025)

Legend/Series:
- Cambodia (blue)
- Thailand (maroon)
- Indonesia (turquoise/cyan)
- Brunei (yellow)
- Lao (purple)
- Malaysia (orange)
- Myanmar (green)
- Philippines (red)
- Singapore (dark yellow/gold)
- Vietnam (light orange)

Trends/Relationships:
- Indonesia and Brunei are at the highest lnY values, both above 11, with Indonesia showing a slight upward trend and Brunei remaining fairly constant.
- Singapore, Malaysia, and Thailand occupy mid-high values (around 10 to 11), with gentle upward trends.
- Philippines, Vietnam, and Lao have values ranging between 8 and 9.5, showing gradual increases over time.
- Cambodia starts lowest (just above 7 in 2000) but increases steadily toward 8.5 by 2025.
- Myanmar starts between 8 and 9, rising moderately.
- All countries show a general upward trend in lnY from 2000 to 2025, with some fluctuations.

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

**Speaker notes:** 5

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

**Speaker notes:** 6

---

## Slide 7

DESCRIPTIVE EVIDENCE

Singapore leads ASEAN productivity

Average TFP Levels (log)

Average Annual TFP Growth

Rankings are broadly stable under both estimated and calibrated α.

**[Image 8]**

Title: Not specified

Legend/Series:
- ⬜ Estimated α
- 🟫 Calibrated α

Y-Axis (Country):
- Vietnam
- Singapore
- Indonesia
- Cambodia
- Laos
- Thailand
- Malaysia
- Philippines
- Brunei

X-Axis (no explicit label; values range approximately from -2.5 to 2.5)

Data (approximate values based on bar lengths):

| Country      | Estimated α | Calibrated α |
|--------------|-------------|--------------|
| Vietnam      | 2.2         | 2.3          |
| Singapore    | 1.5         | 1.7          |
| Indonesia    | 1.7         | 1.8          |
| Cambodia     | 1.5         | 1.7          |
| Laos         | 1.0         | 1.1          |
| Thailand     | 1.0         | 1.3          |
| Malaysia     | 0.8         | 1.0          |
| Philippines  | 0.6         | 0.9          |
| Brunei       | -2.1        | -2.0         |

Trends/Relationships:
- All countries except Brunei have positive α values.
- Brunei is the only country with negative α values.
- Calibrated α values are generally slightly higher than Estimated α values for all countries.

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

**Speaker notes:** 7

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

**Speaker notes:** 8

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

**Speaker notes:** 9

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

**Speaker notes:** 10

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

**Speaker notes:** 11

---

## Slide 12

TFP DYNAMICS

TFP trajectories reveal partial convergence across ASEAN

TFP trajectories for all 10 ASEAN countries from 2000-2023, comparing results using estimated alpha versus a calibrated alpha of 1/3.

TFP Trajectories — Estimated α

TFP Trajectories — Calibrated α = 1/3

**[Image 14]**

Title: TFP Trajectories Est

X-axis: Year (2000 to 2025)
Y-axis: Log TFP (range approx. 5 to 8)

Legend/Series:
- BRN (light blue)
- IDN (red)
- KHM (green)
- LAO (yellow)
- MYS (purple)
- PHL (orange)
- SGP (dark blue)
- THA (brown)
- VNM (cyan)

Trends/Relationships:
- BRN and SGP exhibit the highest Log TFP overall, with BRN showing a slightly decreasing trend while SGP increases gradually.
- MYS also shows a steady increase, maintaining a middle-high position among the countries.
- IDN, PHL, and THA exhibit consistent but moderate increasing trends in Log TFP.
- KHM, LAO, and VNM start at lower levels but generally increase over time, with VNM showing a steeper rise post-2010.
- No country exhibits a dramatic change, but regional gaps persist throughout the period.

**[Image 15]**

Title: TFP Trajectories Cal

Y-axis label: Log TFP  
Y-axis range: 5.5 to 8.5

X-axis label: Year  
X-axis range: 2000 to 2025

Legend/Series:
- BRN (blue)
- IDN (dark red)
- KHM (green)
- LAO (yellow)
- MYS (purple)
- PHL (orange)
- SGP (light blue)
- THA (brown)
- VNM (teal)

Trends/Relationships:
- SGP (light blue) remains the highest in Log TFP throughout the period with slight fluctuations but generally above 8.
- BRN (blue) is below SGP but has the next highest Log TFP value, with values above 7 and showing a generally stable or slight increase over time.
- Other countries (MYS, THA, IDN, PHL, LAO, VNM, KHM) exhibit lower Log TFPs (ranging roughly from 5.5 to 7), with gradual increases for all except some flat or volatile phases for LAO and KHM.
- All countries display a positive or stable trajectory in Log TFP over the 2000-2025 period, with some variations in the slope or periods of stagnation.
- The gap between highest (SGP) and lowest (KHM, VNM) countries appears consistent but may slightly widen or narrow for specific intervals.

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

**Speaker notes:** 12

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

**Speaker notes:** 13

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

X-Axis: Initial TFP (2000)
- Range: 35 to 95

Y-Axis: Cumulative TFP Growth (2000-2023)
- Range: 20 to 80

Data Points (approximate based on visual location):
- (37, 72)
- (43, 79)
- (48, 78)
- (56, 51)
- (71, 39)
- (76, 34)
- (93, 21)

Trend/Relationship:
- Negative relationship: As the Initial TFP (2000) increases, the Cumulative TFP Growth (2000-2023) generally decreases.

Negative relationship: Initial TFP vs. growth

Lower-productivity economies grow faster

Partial convergence occurring in ASEAN

Technological catch-up is measurable

The relationship appears generally negative, suggesting evidence of β-convergence within ASEAN economies. Countries with relatively low initial TFP levels, such as Vietnam and Cambodia, tended to experience faster productivity growth over the sample period.

**[Image 19]**

(decorative — no data)

Lower initial TFP levels are associated with faster cumulative growth, consistent with beta-convergence and catch-up dynamics across ASEAN.

14

**Speaker notes:** 14

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

**Speaker notes:** 15

---

## Slide 16

Q&A
