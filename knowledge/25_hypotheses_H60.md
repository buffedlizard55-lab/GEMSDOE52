# 25 — H60 hypotheses, ranked (2026-10-08)

Five candidate geological hypotheses were ranked before any H60 fit ran. One was implemented (H60-1);
the other four are recorded with the reason they were deferred or folded in. Ranking is by expected
DTI improvement over implementation cost, using what the family's 30+ prior submissions established:

1. Placement (the ≤200 m ring deletion, isotropic 3-px greedy emission, DTI-optimal budget) is
   responsible for almost all of the jump from ~0.16 to 0.28, and is already in the code base.
2. Within the already-placed arm, a ranker with real new geology can shift ρ_novel (the hidden-truth
   density of the novel pixels) and that shifts DTI by tens of points in the third decimal.
3. The simulator that selects arms is structurally blind to novel arms (IR-52-017), so a hypothesis
   is selected for implementation on physical plausibility + data-obtainability, never on a local
   holdout lift that has been shown not to transfer.

## H60-1 (implemented) — Strike-gated triple-convergence AND-gate (gravity × RTP × K/Th) + depth gradient

* **Layers.** Gravity (b13 iso_grav_anom, b11 vg, b5 slope, b18 hg) · RTP magnetics (b2) + TMI
  (b14, b3 hg, b9 vg) · K/Th ratio (USGS GeoDAWN `geodawn_extensions_u8.tif` band 1; K and Th
  from `geodawn_rad_u8.tif` bands 1–2) · depth to basement (b15) gradient.
* **Physical signature.** A blind (non-emergent) Basin-and-Range normal fault juxtaposes rock
  densities (gravity step), magnetic basement lithologies (RTP step), and radiometrically
  distinct bedrock (K/Th step) along a sharp vertical contact that strikes NNE–SSW and downdrops
  one side into the basin (depth-to-basement gradient).
* **Why it catches faults missing from the catalogue.** The USGS Quaternary fault map and the
  competition labels primarily trace scarps visible in topography/DEM. A blind fault dies out
  under valley alluvium — no scarp, no slope break, no LiDAR lineament — but the potential-field
  and radiometric contacts are still present at depth, and the sedimentary wedge thickens across
  the fault. The champion file (0.2778) and its scarp-only siblings (h19, h25, h27, h28, h33)
  cannot see these, by construction.
* **Why it differs from prior rounds.**
    * Not a top-K of a single field (H19/H25/H28/H33).
    * Not `max(p_A, p_B)` over two logistic-regression views (H57/H59).
    * Not a pixel-level multiplicative corroboration weight (H59-A, which was refuted).
    * Adds an AND-gate across *three independent physics families* with a hard ±25° strike
      tolerance around the dominant fabric azimuth (015°).
    * Restricts the novel-arm pool to above-median depth-to-basement (cover > ~316 m), which is
      the A-only stratum H57 ranked worst when fed as a plain logistic score; the AND-gate and
      strike restriction are what rehabilitates it.
    * Budget 31,000 px (not the historical 37,654), chosen per the T(S) power law in
      `knowledge/10`.

## H60-2 (deferred, egress-blocked) — InSAR lineament rate at 10× strain resolution

* **Layers.** Sentinel-1 InSAR LOS velocity time series from the Alaska Satellite Facility (ASF;
  free, NASA-funded, public domain).
* **Physical signature.** Shallow fault creep produces mm/yr velocity steps aligned with basement
  structure at the 10–30 m scale that the provided 100 m geodetic-strain bands (b4, b7, b8) smooth
  away.
* **Why it could catch new faults.** The geodetic strain in the cube is heavily smoothed and
  derivative, so lineaments at the sub-km scale are invisible; InSAR sees them.
* **Why it is deferred.** `api.github.com` and `pypi.org` are reachable from the sandbox;
  `raw.githubusercontent.com`, `asf.alaska.edu` and `search.asf.alaska.edu` time out at the
  network layer. An unrestricted runner can fetch this; the sandbox cannot. Expected lift is
  high if the data lands, but implementation cost is dominated by download (~20 GB of SLCs).

## H60-3 (deferred) — LiDAR intensity / return-width road veto

* **Layers.** USGS 3DEP 1 m LAS/LAZ intensity and return-width (public domain).
* **Physical signature.** Roads produce sharp slope breaks that look exactly like small scarps in
  DEM-derived products, while having a uniformly high-intensity, narrow return-width signature in
  the raw point cloud.
* **Why it could help.** H59-B (blanket B-veto at λ=0.5) failed because the B-only stratum
  carries ~2.7× random signal; suppressing it indiscriminately kills real mass with the artefacts.
  A trained road-vs-scarp intensity classifier is what would let us veto only the actual
  artefacts, not everything B sees.
* **Why deferred.** Hundreds of GB of LAS tiles; bandwidth-blocked from the sandbox. Not
  achievable inside a single session but the highest-value external-data idea.

## H60-4 (folded in) — Conductivity-plumb conjunction (hydrothermal alteration)

* **Layers.** Conductivity surface (b17, `cond_surf`) co-located with triple-edge.
* **Physical signature.** Fluidized fault zones (particularly geothermally active ones) show
  elevated conductivity along the plane due to clay alteration and brine saturation.
* **Status.** H59-E was statistically indistinguishable from the union (−0.0001/−0.0011). Folded
  into H60 as a 0.15 blend weight rather than a gate.

## H60-5 (already exploited) — Earthquake lineament density

* **Layers.** The provided seismicity bands (b10 dist_to_eq, b16 eq_density).
* **Status.** Both are already in View A with gradient and rank transforms; adding them again
  adds nothing. Real improvement would require ComCat event-level focal mechanisms and depth,
  which is blocked on USGS egress.
