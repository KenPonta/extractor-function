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

Title: *(Not specified)*

Y-axis label: lny  
Y-axis range: 7 to 12

X-axis label: Year  
X-axis range: 2000 to 2025

Legend/Series:
- Cambodia (blue)
- Thailand (dark pink)
- Indonesia (teal)
- Brunei (yellow)
- Lao (purple)
- Malaysia (red-orange)
- Myanmar (light blue)
- Philippines (brown)
- Singapore (red)
- Vietnam (orange)

Trends/Relationships:
- The chart shows the trends in "lny" for ten Southeast Asian countries from 2000 to 2025.
- Indonesia and Brunei have the highest values throughout the period (~11 to 12 range).
- Malaysia and Singapore are in the next tier (~10 to 10.5).
- Thailand, Philippines, Lao, Myanmar, and Vietnam are in the 8–9.5 range, with Vietnam showing a steady increase.
- Cambodia starts with the lowest at just above 7 in 2000 and increases steadily over time, almost reaching 8.5.
- All series generally show gradual upward trends, with few fluctuations.

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
- Light brown: Estimated α
- Dark brown: Calibrated α

Y-Axis: Country
- Vietnam
- Singapore
- Indonesia
- Cambodia
- Laos
- Thailand
- Malaysia
- Philippines
- Brunei

X-Axis: (No label), range approximately from -2.5 to 2.5

Data/Trends (Bar chart, estimated visually from bar lengths for each country):

| Country      | Estimated α | Calibrated α |
|--------------|-------------|--------------|
| Vietnam      | 2.0         | 2.1          |
| Singapore    | 1.3         | 1.6          |
| Indonesia    | 1.4         | 1.8          |
| Cambodia     | 1.1         | 1.5          |
| Laos         | 1.0         | 1.2          |
| Thailand     | 0.9         | 1.1          |
| Malaysia     | 0.8         | 1.2          |
| Philippines  | 0.7         | 1.0          |
| Brunei       | -2.0        | -1.9         |

Trend/relationship: 
- Most countries have positive values for both Estimated α and Calibrated α, with Calibrated α generally slightly higher than Estimated α.
- Brunei is the only country with negative values for both metrics.
- Vietnam shows the highest positive values.

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
- SGP (dark blue)
- THA (brown)
- VNM (cyan)

Trends/Relationships:
- BRN and SGP have the highest Log TFP levels throughout the period.
- KHM and VNM have the lowest Log TFP levels.
- Most countries show a gradual increase in Log TFP from 2000 to 2025, with minor fluctuations.
- BRN appears relatively flat or slightly declining, while MYS and SGP show noticeable upward trends.
- The spread among countries remains relatively consistent across years.

**[Image 15]**

Title: TFP Trajectories Cal

Y-axis: Log TFP (range roughly from 5.5 to 8.3)
X-axis: Year (range: 2000 to 2025)

Legend/Series:
- BRN (blue)
- IDN (maroon)
- KHM (green)
- LAO (yellow)
- MYS (purple)
- PHL (orange)
- SGP (light blue)
- THA (brown)
- VNM (teal)

Data/Trends:
- SGP (Singapore) consistently has the highest Log TFP, with values above 8, showing some fluctuation but remaining mostly stable.
- MYS (Malaysia) is the next highest, with steadily increasing Log TFP values in the low 7s.
- BRN (Brunei) and THA (Thailand) follow, with Log TFP between 6.5 and 7.
- PHL (Philippines) and IDN (Indonesia) have similar values, between roughly 6 and 6.5, gradually increasing over time.
- LAO (Laos), VNM (Vietnam), and KHM (Cambodia) have the lowest Log TFP, mostly ranging from 5.5 to around 6, with slight upward trends.
- All countries show either a stable or upward trajectory in Log TFP from 2000 to slightly after 2020.

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

X-Axis: Initial TFP (2000)
- Range: 35 to 95

Y-Axis: Cumulative TFP Growth (2000-2023)
- Range: 20 to 80

Plotted Data Points (approximate based on visual inspection):
- (37, 78)
- (44, 76)
- (56, 46)
- (70, 38)
- (77, 32)
- (93, 20)

Trends/Relationships:
- There is a negative correlation: as Initial TFP (2000) increases, Cumulative TFP Growth (2000-2023) generally decreases.

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
