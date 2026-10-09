(() => {
  const set = (id, value) => {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  };

  async function render() {
    const response = await fetch("data/h65_continuation_card.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`run card request failed (${response.status})`);
    const card = await response.json();
    const premise = card.premise_auc;
    const holdout = card.holdout_dti;

    set("h65-premise-mean", Number(premise.mean_oof_auc).toFixed(4));
    set("h65-premise-min", Number(premise.minimum_fold_auc).toFixed(4));
    set("h65-premise-thresholds", `${Number(premise.mean_threshold).toFixed(2)} mean / ${Number(premise.minimum_fold_threshold).toFixed(2)} minimum fold`);
    set("h65-holdout-status", holdout.status);
    set("h65-holdout-status-secondary", holdout.status);
    set("h65-holdout-evaluator", holdout.evaluator_version || "not applicable — no holdout run");
    set("h65-file-status", card.raster.emitted ? "Unexpected raster receipt; review required." : "No H65 TIFF was emitted.");
    set("h65-slots", String(card.submission.weekly_slots_used));
    set("h65-tests", `${card.test_suite.passed} passed · ${card.test_suite.skipped} skipped · ${card.test_suite.failed} failed (repository tests only)`);
  }

  render().catch((error) => {
    console.error("H65 review card could not be loaded", error);
    set("h65-premise-mean", "unavailable");
    set("h65-premise-min", "unavailable");
    set("h65-premise-thresholds", "see the linked JSON receipt");
    set("h65-holdout-status", "NOT RUN");
    set("h65-holdout-evaluator", "not applicable — no holdout run");
    set("h65-file-status", "No current H65 file is approved for download or submission.");
    set("h65-slots", "0");
    set("h65-tests", "see the linked review record");
  });
})();
