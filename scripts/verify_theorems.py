#!/usr/bin/env python3
"""Verify every algebraic claim in knowledge/02_the_ceiling_and_the_instrument.md.

The whole point of this file is that the claims in that document are *checkable* rather than
asserted.  Each block prints the quantity, the tolerance, and PASS/FAIL, and the process exits
non-zero if anything fails.

Claims verified
---------------
(A) Eq. (2.2)  1/DTI = alpha + alpha*(F/T) + beta*(K/T)
(B) Eq. (3.1)  the exact marginal theorem, sign of
               D0*dT - alpha*T*(dT + 1 - kbar), against the official implementation
(C) Eq. (6.1)  DTI(lambda*p) = lambda*T / (lambda*alpha*(T+F) + beta*K)
(D) Eq. (6.3)-(6.5) recovery of T, K, F from three simulated leaderboard returns
(E) the "bar cannot bind on own support" proposition of §4b
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import metric as M  # noqa: E402

OK = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global OK
    OK = OK and bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{('  ' + detail) if detail else ''}")


def random_pair(rng, n=21):
    truth = np.zeros((n, n), bool)
    for _ in range(rng.integers(1, 4)):
        y = int(rng.integers(1, n - 1))
        x = int(rng.integers(1, n - 6))
        truth[y, x:x + int(rng.integers(2, 6))] = True
    pred = np.zeros((n, n))
    idx = rng.choice(n * n, size=int(rng.integers(0, 25)), replace=False)
    pred.ravel()[idx] = 1.0
    return pred, truth


def main() -> int:
    rng = np.random.default_rng(20261004)

    print("(A) the design equation  1/DTI = alpha + alpha*(F/T) + beta*(K/T)")
    worst = 0.0
    for _ in range(200):
        pred, truth = random_pair(rng)
        c = M.components(pred, truth)
        if c["TP_w"] <= 0 or c["K"] <= 0:
            continue
        lhs = 1.0 / M.dti(c["TP_w"], c["FP_w"], c["FN_w"])
        rhs = M.ALPHA + M.ALPHA * c["FP_w"] / c["TP_w"] + M.BETA * c["K"] / c["TP_w"]
        worst = max(worst, abs(lhs - rhs))
    check("max |1/DTI - (alpha + alpha*F/T + beta*K/T)|", worst < 1e-9, f"= {worst:.3e}")

    print("(B) the exact marginal theorem (coverage-deducted), vs the official implementation")
    agree = total = 0
    n = 19
    for _ in range(300):
        pred, truth = random_pair(rng, n)
        c0 = M.components(pred, truth)
        s0 = M.dti(c0["TP_w"], c0["FP_w"], c0["FN_w"])
        dy, dx, kw = M._OFF
        cover = np.zeros((n, n))
        for d, e, kk in zip(dy, dx, kw):
            cover = np.maximum(cover, M._shift(pred, -d, -e) * kk)
        D0 = c0["TP_w"] + M.ALPHA * c0["FP_w"] + M.BETA * c0["FN_w"]
        free = np.argwhere(pred == 0)
        if not len(free):
            continue
        y, x = (int(v) for v in free[rng.integers(len(free))])
        from scipy import ndimage
        kbar = float(M.kernel(float(ndimage.distance_transform_edt(~truth)[y, x])))
        dT = 0.0
        for d, e, kk in zip(dy, dx, kw):
            gy, gx = y + d, x + e
            if 0 <= gy < n and 0 <= gx < n and truth[gy, gx]:
                dT += max(0.0, kk - float(cover[gy, gx]))
        lhs = dT * D0 - M.ALPHA * float(c0["TP_w"]) * (dT + 1.0 - kbar)
        cand = pred.copy()
        cand[y, x] = 1.0
        total += 1
        agree += ((lhs > 0) == (M.score(cand, truth) > s0))
    check(f"sign agreement over {total} random single-add trials", agree == total,
          f"{agree}/{total}")

    print("(C) the scaling law  DTI(lambda*p) = lambda*T/(lambda*alpha*(T+F) + beta*K)")
    worst = 0.0
    for _ in range(40):
        pred, truth = random_pair(rng, 25)
        c = M.components(pred, truth)
        for lam in (1.0, 0.75, 0.5, 0.25, 0.1):
            meas = M.score(lam * pred, truth)
            form = lam * c["TP_w"] / (lam * M.ALPHA * (c["TP_w"] + c["FP_w"]) + M.BETA * c["K"])
            worst = max(worst, abs(meas - form))
    check("max |DTI(lambda*p) - law|", worst < 1e-12, f"= {worst:.3e}")

    print("(D) recovery of (T, K, F) from three leaderboard returns")
    # A realistic-scale synthetic system so that all three returns are well conditioned:
    #   truth  : 24 horizontal traces of length 15 on a 300x300 canvas           (K = 360 px)
    #   anchor : every 3rd truth pixel + 60 off-trace dots                       (T ~ 300, F ~ 60)
    #   S2     : 0.5 * anchor
    #   S3     : anchor + M null dots placed > 3 px from every truth pixel
    from scipy import ndimage
    n = 300
    truth = np.zeros((n, n), bool)
    rng_d = np.random.default_rng(7)
    for i in range(24):
        y = 10 + i * 12
        x = 20 + int(rng_d.integers(0, 40))
        truth[y, x:x + 15] = True
    anchor = np.zeros((n, n))
    anchor[truth] = 1.0
    keep = np.zeros((n, n), bool)
    keep[::3, :] = True
    anchor = anchor * keep                       # thin the on-trace dots to every 3rd
    off = rng_d.choice(n * n, size=60, replace=False)
    oy, ox = np.unravel_index(off, (n, n))
    anchor[oy, ox] = 1.0                         # plus 60 off-trace dots

    M_dots = 50
    null = np.zeros((n, n))
    placed = 0
    d_to_truth = ndimage.distance_transform_edt(~truth)
    cand = np.argwhere(d_to_truth > 4.0)
    cand = cand[(cand[:, 0] < 120)]
    for y, x in cand[:M_dots]:
        null[y, x] = 1.0
        placed += 1

    c_true = M.components(anchor, truth)
    T, F, K = c_true["TP_w"], c_true["FP_w"], c_true["K"]
    s1 = M.score(anchor, truth)
    s2 = M.score(0.5 * anchor, truth)
    s3 = M.score(anchor + null, truth)
    T_hat = M.ALPHA * placed / (1.0 / s3 - 1.0 / s1)
    K_hat = T_hat * (1.0 / s2 - 1.0 / s1) / M.BETA
    F_hat = T_hat * (1.0 / s1 - M.ALPHA - M.BETA * K_hat / T_hat) / M.ALPHA
    print(f"        T={T:.3f} F={F:.3f} K={K:.0f} | s1={s1:.6f} s2={s2:.6f} s3={s3:.6f} M={placed}")
    check("all three returns are positive and separated",
          s1 > 0 and s2 > 0 and s3 > 0 and s1 != s2 and s1 != s3)
    check("null pixels are > 3 px from every truth pixel",
          float(d_to_truth[null > 0].min()) > 3.0,
          f"min d = {float(d_to_truth[null > 0].min()):.2f}")
    check("T recovered", abs(T_hat - T) < 1e-6 * max(1.0, T), f"T={T:.4f} -> T_hat={T_hat:.4f}")
    check("K recovered", abs(K_hat - K) < 1e-6 * max(1.0, K), f"K={K:.1f} -> K_hat={K_hat:.2f}")
    check("F recovered", abs(F_hat - F) < 1e-6 * max(1.0, F), f"F={F:.4f} -> F_hat={F_hat:.4f}")

    print("(E) on-support proposition: the credit bar cannot bind (§4b)")
    field = np.zeros((41, 41))
    field[20, 5:36] = 1.0
    dy, dx, kw = M._OFF
    kbar = np.zeros_like(field)
    for d, e, kk in zip(dy, dx, kw):
        kbar = np.maximum(kbar, M._shift(field, -d, -e) * kk)
    on = field > 0
    check("min kbar over the field's own support >= 1", float(kbar[on].min()) >= 1.0,
          f"min = {float(kbar[on].min()):.3f}")
    sys.path.insert(0, str(ROOT / "src"))
    from gems52 import emitter
    _, log = emitter.emit(field, budget=None, prior_dti=0.26)
    check("bar-priced emit() consumes the whole support (non-binding)",
          log.n_emitted == int(on.sum()) and log.stopped_by == "exhausted_support",
          f"emitted {log.n_emitted}/{int(on.sum())}, stopped_by={log.stopped_by}")

    print()
    print("ALL CLAIMS VERIFIED" if OK else "SOME CLAIMS FAILED")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
