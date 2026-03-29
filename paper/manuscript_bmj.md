# Reproducibility of Cochrane Meta-Analyses: An Automated Audit of 501 Pairwise Comparisons

[AUTHOR_NAME]^1^, [CO-AUTHOR_PLACEHOLDER]^2^

^1^ [AFFILIATION_PLACEHOLDER]
^2^ [AFFILIATION_PLACEHOLDER]

Correspondence to: [CORRESPONDING_EMAIL_PLACEHOLDER]

---

## Abstract

**Objective:** To assess the computational reproducibility of published Cochrane meta-analyses using automated re-extraction and re-pooling of effect estimates.

**Design:** Automated reproducibility audit using a deterministic pipeline with cryptographic provenance.

**Data sources:** Pairwise70 dataset (501 Cochrane systematic reviews with pairwise meta-analyses, post-2000), open-access trial PDFs via RCT Extractor v10.3 (1,290 PDFs), and ClinicalTrials.gov structured results via REST API v2 (4,136 PMIDs queried).

**Main outcome measures:** Study-level effect match rate across all audited outcomes (strict <=5%, moderate <=10% relative difference), review-level reproducibility classification on a prespecified primary outcome per review (reproduced, minor discrepancy, major discrepancy, insufficient coverage), and error taxonomy.

**Results:** Of 14,340 study outcomes across 501 reviews, 1,747 (12.2%) had an extraction source (PDF or CT.gov). Among those, 128 (7.3%) achieved strict-match and 222 (12.7%) moderate-match reproducibility. Using the prespecified primary outcome per review for one-row-per-review classification, 11 reviews were assessable: 1 was fully reproduced, 4 showed minor discrepancies, 1 showed a major discrepancy, and 5 had insufficient coverage. The dominant barrier was PDF availability: 87.8% of study outcomes lacked an accessible PDF. The CT.gov API pathway contributed 59 additional matches (+36% relative improvement). Median between-study heterogeneity (I-squared) across reviews was 22.2%.

**Conclusions:** Automated reproducibility auditing of Cochrane meta-analyses is technically feasible but severely constrained by open-access PDF availability. Among studies with accessible sources, reproducibility rates are moderate (12.7%). The CT.gov structured results pathway provides a valuable supplementary extraction channel. Universal open access to trial reports is a prerequisite for systematic reproducibility verification of the evidence base.

---

## What is already known on this topic

- A reproducibility crisis affects biomedical research, with meta-analyses representing the highest level of evidence
- Manual reproducibility verification is labour-intensive and rarely performed at scale
- Previous studies have found error rates of 10-30% in published meta-analyses, but sample sizes were small (<50 reviews)

## What this study adds

- The first fully automated, large-scale reproducibility audit of 501 Cochrane meta-analyses
- Quantifies the open-access barrier: 87.8% of study outcomes lack accessible PDFs for re-extraction
- Audits all outcomes per review while using a deterministic prespecified primary outcome for headline review-level classification
- Introduces a two-level classification system (study + review) with SHA-256 cryptographic provenance
- Demonstrates that ClinicalTrials.gov structured results can supplement PDF extraction by 36%

---

## Introduction

The reproducibility of scientific findings is foundational to evidence-based medicine [1,2]. Meta-analyses, which synthesise results across multiple studies, are widely regarded as the highest level of evidence for clinical decision-making [3]. Yet the computational reproducibility of published meta-analyses -- whether reported pooled estimates can be independently verified from the underlying data -- has received limited systematic investigation.

Previous work has documented errors in published meta-analyses. Nuijten et al. found that approximately half of psychology papers contained at least one statistical reporting inconsistency [4]. Maassen et al. attempted to reproduce 33 meta-analyses and found that only 64% could be exactly reproduced [5]. Hardwicke et al. reported that only 36% of a sample of Cochrane reviews had sufficient data for independent reproduction [6]. However, these studies relied on manual verification, limiting their scope to tens of reviews.

The Cochrane Library, with over 8,000 systematic reviews, represents the largest curated collection of meta-analyses in health care [3]. The Pairwise70 dataset, derived from 501 Cochrane reviews containing pairwise meta-analyses, provides a standardised format (RDA files with per-study effect sizes, confidence intervals, and raw counts) suitable for automated processing [7].

We developed MetaReproducer, a fully automated, deterministic pipeline that re-extracts effect estimates from trial publications, re-pools them using standard random-effects methods, and classifies reproducibility at both study and review levels. Each audit produces a TruthCert bundle -- a SHA-256 cryptographic provenance chain linking raw inputs to final classifications. Here we report results from the first large-scale automated reproducibility audit of 501 Cochrane meta-analyses.

---

## Methods

### Data sources

We used the Pairwise70 dataset, which contains 501 Cochrane systematic reviews with pairwise meta-analyses published after 2000 [7]. Each review is stored as an RDA file containing per-study data: point estimates (generic inverse variance "Mean" column), 95% confidence intervals, raw event counts (for binary outcomes), and means/SDs/Ns (for continuous outcomes). All outcomes within each review were audited. For headline review-level analyses that required one row per review, we prespecified a primary outcome as the outcome with the largest number of included studies, with binary outcomes preferred over continuous when tied.

### Effect extraction

Two complementary extraction pathways were used:

**PDF pathway:** Pre-computed extraction results from RCT Extractor v10.3 [8], which had previously processed 1,290 open-access trial PDFs linked to the Pairwise70 studies via DOI/PMID/PMCID matching through the mega gold standard pipeline.

**CT.gov pathway:** For studies with PubMed IDs (PMIDs), we queried the ClinicalTrials.gov REST API v2 using `AREA[ReferencePMID]` searches [9]. Of 4,136 unique PMIDs queried, 486 (11.7%) mapped to registered trials (NCT IDs), of which 147 had posted outcome analyses with extractable effect estimates (hazard ratios, odds ratios, risk ratios, mean differences).

### Effect type inference

For each study, we back-computed the expected effect size from raw data under four candidate measures: odds ratio (OR), risk ratio (RR), mean difference (MD), and standardised mean difference (SMD, Hedges' g). The inferred effect type was the measure whose computed value matched the reported "Mean" column within a relative tolerance of 0.1%. A majority vote across studies within each outcome determined the outcome-level effect type.

### Meta-analysis engine

Reference pooled estimates were computed from the Cochrane-reported values using DerSimonian-Laird (DL) random-effects meta-analysis [10]. Standard errors were back-calculated from reported confidence intervals using `z = Phi^{-1}(0.975)` from scipy.stats (no hardcoded critical values). Heterogeneity was quantified using I-squared [11] and Cochran's Q. REML estimation via Fisher scoring [12] was available as a sensitivity analysis.

### Study-level classification

Each extracted effect was compared against the corresponding Cochrane-reported value. Match tiers were:
- **Strict match:** Relative difference <=5%
- **Moderate match:** Relative difference <=10%
- **No match:** Relative difference >10% or different direction

### Review-level classification

For reviews with sufficient study-level data (k_coverage >= 30% of included studies), a four-tier classification was applied:

| Classification | Criteria |
|---|---|
| Reproduced | Same direction, same significance, <=10% relative difference in pooled estimate, k_coverage >= 50% |
| Minor discrepancy | Same direction and significance, but >10% difference or k_coverage 30-50% |
| Major discrepancy | Different direction OR different significance conclusion |
| Insufficient | k_coverage < 30% |

Direction was assessed by the sign of the pooled estimate; significance was assessed at alpha = 0.05. Near-zero estimates (|pooled| < 10^-10) were treated as compatible with either direction.

### Error taxonomy

Study outcomes that failed to match were categorised into: missing PDF (no accessible full-text), extraction failure (PDF available but no effect extracted), and no match (effect extracted but >10% discrepancy with Cochrane value).

### Provenance

Each review audit produced a TruthCert bundle containing a 4-step SHA-256 provenance chain: (1) RDA ingestion hash, (2) extraction results hash, (3) re-pooling output hash, (4) classification hash. Bundle hashes are deterministic and reproducible.

### Software

MetaReproducer is implemented in Python 3.13 using scipy, numpy, and pyreadr. The pipeline comprises 9 modules totalling approximately 2,300 lines of code with 121 automated tests (87 unit + 34 integration). No external meta-analysis software was used; all statistical computations are implemented from first principles with cross-validation against R metafor [13].

### Statistical analysis

Results are descriptive. Medians and interquartile ranges are reported for heterogeneity distributions. Percentages use the appropriate denominator (all audited study outcomes for extraction/error taxonomy, studies with an extraction source for match rates, and one prespecified primary outcome per review for review-level classification). No inferential statistics were planned or performed.

---

## Results

### Study-level reproducibility

Table 1 shows the overall flow. Of 14,340 study outcomes across 501 reviews, 1,688 (11.8%) had a linked PDF and 59 additional matches came from the CT.gov API pathway, giving 1,747 (12.2%) with an extraction source. Among those with sources, 128 (7.3%) achieved strict-match reproducibility (<=5% relative difference) and 222 (12.7%) achieved moderate-match reproducibility (<=10%).

**Table 1. Study-level reproducibility**

| Metric | n | % |
|---|---|---|
| Total study outcomes | 14,340 | 100.0 |
| With extraction source (PDF + CT.gov) | 1,747 | 12.2 |
| Strict match (<=5%) | 128 | 7.3* |
| Moderate match (<=10%) | 222 | 12.7* |
| No match (>10%) | 736 | 42.1* |
| Extraction failure | 567 | 32.4* |
| No extraction source | 12,593 | 87.8 |

*Percentage of studies with extraction source (n=1,747)

### Reproducibility by effect type

Table 2 shows study-level results stratified by inferred effect type for the prespecified primary outcome per review. Risk ratios (RR) were the most common (262 reviews) with a 14.1% moderate-match rate. Odds ratios (OR) showed a moderate-match rate of 8.9%. Continuous outcomes (MD, SMD) had too few PDF-linked studies for reliable estimates.

**Table 2. Study-level reproducibility by effect type**

| Effect type | Reviews | Studies with source | Strict match | Moderate match |
|---|---|---|---|---|
| RR | 262 | 681 | 36 (5.3%) | 96 (14.1%) |
| OR | 39 | 112 | 7 (6.2%) | 10 (8.9%) |
| MD | 9 | 10 | 0 (0.0%) | 1 (10.0%) |
| SMD | 2 | 7 | 0 (0.0%) | 0 (0.0%) |
| Unknown ratio | 189 | 878 | 43 (4.9%) | 56 (6.4%) |
| **Total** | **501** | **1,747** | **128 (7.3%)** | **222 (12.7%)** |

### Review-level classification

Using the prespecified primary outcome per review, 67 of 501 reviews (13.4%) had at least one study-level extraction, but only 11 (2.2%) met the minimum 30% k_coverage threshold for review-level assessment (Table 3). Among these 11, one was classified as fully reproduced (same direction, significance, and <=10% pooled difference with >=50% coverage), four showed minor discrepancies (same direction and significance but >10% difference), and one showed a major discrepancy (significance reversal).

**Table 3. Review-level reproducibility classification**

| Classification | n | % of total | % of assessable |
|---|---|---|---|
| Reproduced | 1 | 0.2 | 9.1 |
| Minor discrepancy | 4 | 0.8 | 36.4 |
| Major discrepancy | 1 | 0.2 | 9.1 |
| Insufficient coverage | 5 | 1.0 | 45.5 |
| Not assessable | 490 | 97.8 | -- |
| **Total** | **501** | **100.0** | -- |

### Error taxonomy

Table 4 shows the error taxonomy across all 14,340 study outcomes. Missing PDFs accounted for 87.8% of failures, making open-access availability the dominant barrier to reproducibility verification.

**Table 4. Error taxonomy**

| Category | n | % |
|---|---|---|
| Success (moderate match) | 222 | 1.5 |
| Missing PDF | 12,593 | 87.8 |
| No match | 958 | 6.7 |
| Extraction failure | 567 | 4.0 |
| **Total** | **14,340** | **100.0** |

### CT.gov API contribution

The CT.gov REST API v2 pathway queried 4,136 unique PMIDs, mapping 486 (11.7%) to registered trials. Of these, 147 had posted outcome analyses. This pathway contributed 59 additional moderate matches beyond the PDF-only pathway, a 36% relative improvement in match count.

### Heterogeneity distribution

Among 431 reviews with computable reference pooled estimates, median I-squared was 22.2% (IQR 0.0-55.1%). 218 reviews (50.6%) showed low heterogeneity (I-squared <25%), 144 (33.4%) moderate (25-75%), and 69 (16.0%) high (>=75%).

---

## Discussion

### Principal findings

This study presents the first fully automated reproducibility audit of 501 Cochrane meta-analyses. The key finding is that automated reproducibility verification is technically feasible but severely constrained by open-access PDF availability. Among the 12.2% of study outcomes with accessible extraction sources, 12.7% achieved moderate-match reproducibility. The CT.gov structured results pathway provided a meaningful supplement, contributing a 36% relative improvement in match counts.

### Comparison with existing literature

Our 12.7% moderate-match rate among extractable studies is lower than the 64% exact-reproduction rate reported by Maassen et al. [5], but the comparison is not direct: Maassen et al. manually verified a curated sample of 33 reviews with full data access, while our pipeline operates under the constraint of open-access-only PDF availability. When restricted to the 11 reviews assessable at the review level, 45.5% (5/11) showed reproduced or minor-discrepancy results, broadly consistent with prior estimates that approximately half of meta-analyses can be reproduced [5,6].

The 87.8% missing-PDF rate highlights a fundamental structural barrier. Unlike raw data sharing (which requires author cooperation), PDF availability is determined by journal access policies. This finding supports arguments for universal open access to trial reports as a prerequisite for evidence verification [14,15].

### Strengths

First, the pipeline is fully deterministic: given the same inputs, it produces identical outputs with cryptographic verification via TruthCert provenance chains. Second, the dual extraction pathway (PDF + CT.gov API) maximises coverage without requiring proprietary data access. Third, the two-level classification system (study + review) provides granular assessment. Fourth, the 121-test automated suite ensures statistical correctness (DL and REML cross-validated against R metafor). Fifth, the pipeline processes all 501 reviews in under 3 minutes, demonstrating scalability for living observatory applications.

### Limitations

Several limitations should be noted. First, our open-access-only constraint excludes paywalled PDFs, substantially reducing coverage. This is by design (ethical and legal compliance) but means our results represent a lower bound on achievable reproducibility. Second, although the pipeline audits all outcomes, our headline review-level summaries use one prespecified primary outcome per review to avoid double-counting reviews; secondary outcomes may show different reproducibility patterns and should be examined as sensitivity analyses. Third, effect type inference relies on back-computation from raw data, which may fail when Cochrane reviewers applied corrections (e.g., continuity corrections for zero cells) not captured in the RDA format. Fourth, the CT.gov pathway is limited to trials with posted results (approximately 30% of completed trials) [16]. Fifth, study linking uses author-year matching, which may produce false matches for common surnames.

### Implications

For systematic reviewers: computational reproducibility should be treated as a quality indicator alongside methodological quality assessment. For journal editors: requiring machine-readable supplementary data (not just PDF tables) would dramatically improve reproducibility verification. For funders: investment in open-access infrastructure for trial reports has direct implications for evidence integrity. For the field: the 87.8% inaccessibility rate represents a structural vulnerability in the evidence base that no amount of methodological improvement can address without open-access policy change.

### Future directions

Planned extensions include: (1) enabling the AACT PostgreSQL pathway for higher-throughput CT.gov extraction, (2) expanding formal all-outcome sensitivity analyses and visualisations alongside the primary-outcome headline summaries, (3) implementing a living observatory that monitors for new evidence and re-audits affected reviews, (4) adding therapeutic area classification for domain-specific analysis, and (5) expanding the PDF corpus through Europe PMC and bioRxiv/medRxiv preprint harvesting.

---

## Conclusions

Automated reproducibility auditing of Cochrane meta-analyses is feasible and scalable. Among studies with accessible open-access extraction sources, 12.7% achieved moderate-match reproducibility. The dominant barrier is not methodological but structural: 87.8% of study outcomes lack accessible PDFs. Universal open access to trial reports is a prerequisite for systematic reproducibility verification of the meta-analytic evidence base. ClinicalTrials.gov structured results provide a valuable supplementary pathway, contributing a 36% relative improvement. We release MetaReproducer as open-source software with cryptographic provenance to enable independent verification and extension of these findings.

---

## Data availability

The Pairwise70 dataset is available at [ZENODO_DOI_PLACEHOLDER]. MetaReproducer source code is available at [REPOSITORY_URL_PLACEHOLDER]. Full audit results (501 review reports with TruthCert provenance chains) are deposited at [ZENODO_DOI_PLACEHOLDER].

## Software availability

Source code: [REPOSITORY_URL_PLACEHOLDER]
Archived version: [ZENODO_DOI_PLACEHOLDER]
License: MIT

## Competing interests

None declared.

## Funding

[FUNDING_PLACEHOLDER]

## Author contributions

[AUTHOR_NAME] conceived the study, developed the software, ran the audit, and wrote the manuscript.

---

## References

1. Baker M. 1,500 scientists lift the lid on reproducibility. Nature. 2016;533(7604):452-454.
2. Nosek BA, Alter G, Banks GC, et al. Promoting an open research culture. Science. 2015;348(6242):1422-1425.
3. Higgins JPT, Thomas J, Chandler J, et al., eds. Cochrane Handbook for Systematic Reviews of Interventions. Version 6.3. Cochrane; 2022.
4. Nuijten MB, Hartgerink CHJ, van Assen MALM, Epskamp S, Wicherts JM. The prevalence of statistical reporting errors in psychology (1985-2013). Behav Res Methods. 2016;48(4):1205-1226.
5. Maassen E, van Assen MALM, Nuijten MB, Olsson-Collentine A, Wicherts JM. Reproducibility of individual effect sizes in meta-analyses in psychology. PLoS One. 2020;15(5):e0233107.
6. Hardwicke TE, Serghiou S, Janiaud P, et al. Calibrating the scientific ecosystem through meta-research. Annu Rev Stat Appl. 2020;7:11-37.
7. [PAIRWISE70_CITATION_PLACEHOLDER]. Pairwise70: A comprehensive dataset of 501 Cochrane pairwise meta-analyses.
8. [RCT_EXTRACTOR_CITATION_PLACEHOLDER]. RCT Extractor v10.3: Automated effect size extraction from clinical trial PDFs.
9. ClinicalTrials.gov. REST API v2. National Library of Medicine. https://clinicaltrials.gov/data-api/about-api
10. DerSimonian R, Laird N. Meta-analysis in clinical trials. Control Clin Trials. 1986;7(3):177-188.
11. Higgins JPT, Thompson SG. Quantifying heterogeneity in a meta-analysis. Stat Med. 2002;21(11):1539-1558.
12. Viechtbauer W. Bias and efficiency of meta-analytic variance estimators in the random-effects model. J Educ Behav Stat. 2005;30(3):261-293.
13. Viechtbauer W. Conducting meta-analyses in R with the metafor package. J Stat Softw. 2010;36(3):1-48.
14. Piwowar H, Priem J, Lariviere V, et al. The state of OA: a large-scale analysis of the prevalence and impact of Open Access articles. PeerJ. 2018;6:e4375.
15. Suber P. Open Access. MIT Press; 2012.
16. Anderson ML, Chiswell K, Peterson ED, Tasneem A, Topping J, Califf RM. Compliance with results reporting at ClinicalTrials.gov. N Engl J Med. 2015;372(11):1031-1039.
17. Ioannidis JPA. Why most published research findings are false. PLoS Med. 2005;2(8):e124.
18. Page MJ, McKenzie JE, Bossuyt PM, et al. The PRISMA 2020 statement: an updated guideline for reporting systematic reviews. BMJ. 2021;372:n71.
19. Lakens D, Hilgard J, Staaks J. On the reproducibility of meta-analyses: six practical recommendations. BMC Psychol. 2016;4:24.
20. Gøtzsche PC, Hrobjartsson A, Maric K, Tendal B. Data extraction errors in meta-analyses that use standardized mean differences. JAMA. 2007;298(4):430-437.
21. Jones AP, Remmington T, Williamson PR, Ashby D, Smyth RL. High prevalence but low impact of data extraction and reporting errors were found in Cochrane systematic reviews. J Clin Epidemiol. 2005;58(7):741-742.
