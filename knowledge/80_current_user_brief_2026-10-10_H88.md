# 80 · Current user brief for round H88 (2026-10-10)

**Standing brief.** The verbatim user prompt for this work is archived at
`knowledge/77_standing_brief_2026-10-10.md` (identical text re-received this session; it is the
parallel-run co-training lane paragraph + protocol + site/README requirements). Read it at the
start of every session. This file records only what is round-specific.

**Round identity.** This session runs on branch `arena/b61b2802-gemsdoe52`, forked from
`main @ bc26fe2` ("feed: scheduled refresh 2026-10-10T21:42:55Z"). `main` already contains the H87
round (co-training wavelength contrast + Th/K; build receipt only, NO holdout, no slot used). This
round is therefore **H88** (next free identifier per IR-H84-006 rename precedent).

**What the brief adds beyond the lane paragraph (checked against repo state):**

| Brief demand | Repo state at session start |
|---|---|
| "Generate 3–5 candidate geological hypotheses we haven't tried yet… rank them" | Done for this round in `knowledge/81_hypotheses_H88_preregistered.md` |
| "Validate the top candidate on our spatially-blocked holdout before touching a weekly submission slot" | Planned: `scripts/run_h88.py` on the shared `gems52-pooled-hide-v1` instrument; zero slots are spent by this round regardless |
| "Put this prompt into the repo README and read it every time" | `README.md` gains an H88 block pointing at this brief; the verbatim prompt stays in `knowledge/77` |
| "Easy to download submission TIF; obvious whether it is OK to submit" | `docs/index.html` current-first block carries an explicit DOWNLOAD/SUBMIT verdict banner |
| "Why did 0.2778 win, can we beat it" | Answered from bytes on disk in `knowledge/76` and `knowledge/78`; carried forward unchanged |
| "Work line by line, no hallucinations, flag irregularities" | Every number below is from disk or from the organiser page; irregularities go to `registry/irregularities.json` |

**Owner-reported board context received with the brief (PUBLIC, not ORGANIZER-CONFIRMED):**
repo-family best remains `h33-h33-2-b2-…-zeros: 0.2778` (GEMSDOE32); claimed current leaderboard
high 0.3195; GEMSDOE52 itself has NO scored submission yet (the site's score list is empty).
H87's file (`a861069b…`) was built but never holdout-validated and never submitted.

**Data access limitations (unchanged from `knowledge/78` §5):**
* DrivenData data tab is login-walled; competition rasters are restored from the owner's SHA-256-pinned
  sibling mirrors (`scripts/restore_data.py`); labels are integrity-pinned, NOT organiser-authenticated.
* Sandbox egress allowlist: github.com, codeload.github.com, api.github.com, registry.npmjs.org,
  pypi.org, files.pythonhosted.org. USGS/EarthExplorer/GDR hosts are unreachable here, so any
  candidate needing new external data must name the official source and be marked not-viable-in-session.

**Budget.** 3 experiments, ≤ 2 hours, 0 submission slots (promotion is a separate selector step).
