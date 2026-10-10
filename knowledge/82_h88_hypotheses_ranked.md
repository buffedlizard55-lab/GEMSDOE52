# 82 · Candidate hypotheses after H88, ranked (written before any new fit)

Scope: the brief asks for 3–5 candidate geological hypotheses **not yet tried**, each naming the layers, the physical signature,
why it should catch a fault missing from the USGS/INGENIOUS catalogue, how it differs from what the repository already does,
ranked by expected DTI improvement and implementation cost. The top candidate must be validated on the holdout before any
slot is considered. Only H88-P has been validated so far (`knowledge/81`, NEGATIVE).

**Method of "not tried".** Repository grep on `src/` and `scripts/` (this session). Counts are files that contain the term,
so they are an upper bound on use, not a measure of effect. "Expected DTI" is an ordinal prior, **not a projection**
(AGENTS.md: a projection is never written as a score).

| term grepped | files | status |
|---|---:|---|
| `wavelet` | 0 | untried in this repository |
| `theta map` / `theta_map` | 0 | untried |
| `resistivity` | 0 | untried (no MT data in this sandbox) |
| `heat flow` / `heatflow` | 0 | untried (no official source reachable) |
| `2-m temperature` / `temperature survey` | 0 | untried (GDR 1391 not reachable) |
| `total horizontal` / `THD` | 10 | **already used** (H60d, H62, H69, H74 and others); not new |
| `tilt` | 29 | already used |
| `upward` / `up150` | 20 | already used |
| `depth_to_base` | 62 | already used; basement-step signatures are not new |
| `lineament` | 49 | already used |
| `Euler` | 3 | tested as H86-E: holdout random-level (`knowledge/79`) |
| `Th/K` / `ThK` | 27 | already used (H87 and others) |

## Ranked candidates

### 1 · H89-W — multi-scale band-pass (wavelet) edge of the reduced-to-pole field  *(top untried candidate)*

* **Layer(s):** training-feature band 2 `rtp` (reduced to pole), tagged "Reduced to pole magnetic data" in the file.
* **Physical signature:** magnetic edge response that is selective in **scale**. Fault-scale contacts (about 0.5–3 km
  wavelength in the 100 m grid) are kept and basin-scale trends are removed by a 2-D Mexican-hat or Morlet wavelet. Ridge
  maxima of the modulus mark steps in susceptibility.
* **Why it could find a catalogue-missing fault:** a buried, catalogue-absent fault produces a short-wavelength magnetic
  contact under cover. The Hessian-based and tilt-based tools already in the repo respond to every scale at once, so a
  buried structure can be masked by basin-scale gradients. A scale-selected response gives a cleaner ridge.
* **Non-fault mimic (named):** dike and sill margins of the same width; shallow intrusive bodies of matching size; cultural
  magnetic noise (fences, pipelines) at the shortest scale.
* **How it differs:** the repo has tilt (`tc`), total horizontal derivative (THD), upward continuation and Euler (H86-E). It
  has **no wavelet and no scale-selected ridge** on the magnetic field. H87's "wavelength contrast" is a ratio of Hessian
  magnitudes on the **DEM** (sigma 1 vs 8), not a band-pass on the magnetic field. Closest cousin: H87's Hessian ratio; the
  field and the operator differ.
* **Expected DTI improvement:** unknown. Ordinal prior: low to medium, because the magnetic edge family already sits at
  holdout-random level in this repository.
* **Implementation cost:** medium (about 1 h): a fixed scale grid, a wavelet modulus, ridge extraction, one holdout run.
* **Validation status:** **not run.** The next experiment, pre-registered with a hash before any fit, with single-view
  and random controls on the H88 instrument.

### 2 · H89-Θ — theta map (normalised total horizontal derivative of tilt) of band 2

* **Layer(s):** band 2 `rtp`.
* **Signature:** an equal-amplitude edge map of magnetic contacts, after Wijns et al. (2005) normalisation (not verified
  from a source in this sandbox; the repo does not contain that paper).
* **Why it could find a catalogue-missing fault:** amplitude-independent edges are less dominated by the strongest
  sources.
* **Non-fault mimic:** the same as tilt: intrusive margins and lithologic contacts.
* **How it differs:** `tc` (tilt) is in the repo in 29 files. Theta is a re-normalisation of the same information, so
  **novelty is low**. This is why it ranks second, not first.
* **Expected DTI improvement:** low. **Cost:** low (a few minutes). **Validation status:** not run.

### 3 · H89-B — compliance fix: View B must contain band 6 (radiometric total count)

* **Layer(s):** band 6 `tc` as tagged, but radiometric by content. Measured in `knowledge/81` §5: Pearson 0.99569 and Spearman
  0.99912 with GeoDAWN `TC`, on sentinel-free cells.
* **Why this matters:** the brief lists "radiometric bands present in training_features.tif" as part of View B. H88 left band 6
  out (IR-H88-001). H61 already isolated band 6 in View B, so this is a **repair, not a new signature**.
* **Expected DTI improvement:** not a discovery claim. **Cost:** trivial. **Validation status:** not run; to be pre-registered
  as a protocol amendment if it is ever used.

### 4 · H89-G — 2-m temperature survey (INGENIOUS, GDR 1391), **blocked in this sandbox**

* **Source:** INGENIOUS 2-m temperature survey, GDR submission 1391 (`https://gdr.openei.org/submissions/1391`, CC BY 4.0 per the
  repository's source notes).
* **Signature:** thermal anomalies at 2 m depth that concentrate along fault-controlled fluid pathways. This is a
  non-geophysical channel, so it is orthogonal to the potential-field views.
* **Why it could find a catalogue-missing fault:** a buried fault that transmits fluid shows up in shallow temperature
  even without a scarp.
* **Non-fault mimic:** solar heating, vegetation and soil moisture, and shallow groundwater not tied to a fault.
* **Why it is not viable yet:** `gdr.openei.org` returns HTTP **000** from this sandbox (verified this session; egress
  allowlist is `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`,
  `files.pythonhosted.org`). The data needs a user-side download with a SHA-256 pin, or an owner-approved allowlist entry.
* **Expected DTI improvement:** unknown. **Cost:** medium once the file is local. **Validation status:** not run.

### 5 · H89-R — resistivity / magnetotelluric (conductive fault-zone) — **blocked**

* **Source needed:** a free, official MT or resistivity survey for the GeoDAWN footprint. Not located from this sandbox, and
  no USGS or NGDS host is reachable (egress 000). **Not viable until a source is named and fetched.**

## What this round did and did not establish

* Validated: H88-P, the top in-lane candidate (co-training, pre-registered). **NEGATIVE**, `knowledge/81`.
* Not validated: H89-W (top untried transform), H89-Θ, H89-B, H89-G, H89-R. No file is produced for any of them.
* Not checked from a source: the Wijns et al. (2005) theta-map normalisation, and the Blum & Mitchell DOI. Neither could be
  resolved from this sandbox (`doi.org` and `usgs.gov` are not on the allowlist). Both are marked as such.
