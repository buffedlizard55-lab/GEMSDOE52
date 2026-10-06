# The brief, as received (standing starting point for this repo)

> **Provenance and integrity note.** The text below is a faithful itemisation of the instructions
> given to this session, reconstructed from the session record. The *verbatim* wording of the
> original message was not recoverable from the workspace: this repo's git history has a single
> commit (`744df63 Initial commit`) that contains no brief, no file anywhere under `/home/user` or
> the sibling checkouts contains it (`grep -rl "Blum" /tmp/GEMSDOE* /home/user` → only
> `src/gems52/cotrain.py`), and Arena's session summary paraphrases rather than quotes. Rather than
> invent quotation marks, the directives are restated here in full and in order, each one
> implementation-traceable. If the original text turns up, replace this section and bump the version
> in `registry/preregistration.json`. This irregularity is also listed on the site's
> `docs/irregularities.html`.

Version 2, recorded 2026-10-06 (UTC). Nothing here expires; every later instruction in this session
is additive.

## 1. The method

1. Treat the competition as a **co-training** problem: View A = the geophysical / potential-field
   layers, View B = the surface / geomorphic layers. Fit a separate model per view over the same
   unlabelled pixels.
2. The signal is **disagreement**, not agreement: a pixel where one view is confident and the other
   withholds is a candidate for something the catalogue does not contain. Agreement is where the
   catalogue already agrees with itself.
3. Ground this in the learning theory, and cite it: Blum & Mitchell, *Combining labeled and
   unlabeled data with co-training*, **COLT '98, doi:10.1145/279943.279962**. The theorem needs the
   two views' errors to be **conditionally independent given the label**.
4. Therefore **test the premise instead of assuming it**: measure the empirical correlation of the
   two views' out-of-fold errors on **spatial blocks**, and state the reading. If the errors are not
   independent enough, the arm is void and must be dropped — no submission slot on a refuted premise.
5. Pseudo-label **only** where one view is confident and the other abstains. Never pseudo-label from
   the catalogue itself.
6. Hold out **whole segments**, with a **buffer** between blocks, so that a fold never contains half a
   fault that the other half gives away.
7. Reason about each stratum geologically, not just numerically:
   - **A-only** (field confident, surface withholds) → a fault **buried under cover**. Write that
     reasoning out **for every candidate**, not once for the population.
   - **B-only** (surface confident, field withholds) → **suspect**: roads, canal levees, quarry
     faces, erosion. Down-weight, and say why.
8. Also report a **single-view baseline on hide-and-recover**: the honest yardstick is whether the
   two-view method beats each view alone at equal mass, on hidden segments.

## 2. The submission

9. Normalise predictions to **[0, 1]** and write a **single-band GeoTIFF** on the official grid
   (EPSG:32611, 100 m, same bounds as `sample_submission.tif`).
10. Placement must be **metric-aware**: use the DTI kernel/credit structure to decide which pixels to
    emit, rather than emitting a thresholded score field.
11. **Uniqueness gate**: every artefact must be new relative to everything this group has already
    submitted, and "the union of the previous ones" explicitly does not count as new.
12. Aim above the group's current best of **0.2778**, and explain first *why* that score is what it is.

## 3. Hypotheses

13. Propose **3–5 new geological hypotheses**. Each one must state: the layers it uses, its physical
    signature, why it can find catalogue-missing faults, how it differs from what is already in this
    repo's history, and its expected DTI gain and cost. Rank them.
14. Validate the top one on a **spatially-blocked holdout** *before* spending a submission slot.

## 4. Data and knowledge

15. Any new external data must be **free, official, and confirmed obtainable**, with a licence that
    permits use and sharing with the sponsor.
16. Store the knowledge gathered here so the next session does not re-derive it.

## 5. The site

17. A clean **GitHub Pages** site for this repo, with the `.tif` **one-click download obvious at the
    very top**. The site must be able to produce the file the submission needs; "as easy as download
    the file and submit it", and that requirement belongs in the executive summary / the top of the
    page.
18. An **executive-summary subpage** carrying the exact submission instructions.
19. Fix the portal's **"Predicted values must be in range [0, 1]"** error for good.
20. A **unique submission name** plus a short note explaining what it is.
21. A **live, up-to-date data feed** so that nothing on the page has to be checked by hand.
22. Core Values: **Maximize P(Win)** and **Own the Outcome**.
23. Work in **three verification passes**, flag every irregularity found, give official links for
    manual review, and finish with a **pull request, then merge to main**. Zero manual input from the
    user; no hallucinated facts.
