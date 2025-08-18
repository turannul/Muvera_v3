from __future__ import annotations

import os
import pandas as pd
import time
from modules.improve_helpers import SORGU_IN_CSV, SORGU_OUT_CSV, fmt_sec, norm_score, now, pick_col, read_csv_robust, similarity, try_improve

# ============== CONFIG (edit here) ==============
MIN_IMPROVE = 0.0003               # ~0.03% absolute relative improvement
MAX_ATTEMPTS = 3                   # try up to N; if not improved, add anyway with 0% change
ONLY_IMPROVED = False              # do NOT skip non-improved rows
# ===============================================


def run_sorgu_flow(min_improve=MIN_IMPROVE, max_attempts=MAX_ATTEMPTS, only_improved=ONLY_IMPROVED) -> str:
    t_flow = time.time()
    df = read_csv_robust(SORGU_IN_CSV)

    c_query = pick_col(df, ["Kullanıcı Sorgusu", "Kullanici Sorgusu", "Sorgu", "Query", "Aranan Sorgu"])
    c_html = pick_col(df, ["HTML Kaynağı", "HTML Kaynagi", "HTML Bölümü", "HTML Section"])
    c_text = pick_col(df, ["Web İçeriği", "Web Icerigi", "İçerik", "Icerik", "Metin", "Content"])
    c_score = pick_col(df, ["Benzerlik Skoru", "Skor", "Score", "Similarity Score", "similarity_score"])
    for need, name in [(c_query, "Kullanıcı Sorgusu"), (c_html, "HTML Kaynağı"), (c_text, "Web İçeriği")]:
        if not need:
            raise KeyError(f"Eksik kolon: {name}")

    total = len(df)
    kept = improved = 0
    rows = []

    print(f"[{now()}] 🚀 SORGU flow start | rows={total} | MIN_IMPROVE={min_improve} | MAX_ATTEMPTS={max_attempts}", flush=True)

    for idx, r in df.iterrows():
        r_t0 = time.time()
        q = str(r[c_query] or "")
        tag = str(r[c_html] or "")
        cur = str(r[c_text] or "")
        old = norm_score(r[c_score]) if c_score else similarity(q, cur)

        print(f"\n[{now()}] → Row {idx + 1}/{total} | tag='{tag}' | old={old:.4f}", flush=True)
        cand, new = try_improve("sorgu", q, cur, tag, old, min_improve, max_attempts)

        improved_flag = new > old
        improved += 1 if improved_flag else 0
        kept += 1
        change_pct = ((new - old) / max(old, 1e-8) * 100.0) if improved_flag else 0.0

        rows.append({
            "HTML Bölümü": tag,
            "Kullanıcı Sorgusu": q,
            "Eski Metin": cur,
            "Geliştirilmiş Metin": cand,
            "Eski Skor": round(float(old), 6),
            "Yeni Skor": round(float(new), 6),
            "Yüzde Değişim": round(float(change_pct), 2),
        })
        msg = "✅ kept (Δ=+{:.2f}%)".format(change_pct) if improved_flag else "✅ kept (no improvement; Δ=0.00%)"
        print(f"{msg}", flush=True)
        print(f"⏱ row time: {fmt_sec(time.time() - r_t0)}", flush=True)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(SORGU_OUT_CSV, index=False, encoding="utf-8")
    print(f"\n[{now()}] 💾 SORGU saved → {SORGU_OUT_CSV} (rows kept={kept}, improved={improved})", flush=True)
    print(f"[{now()}] 🏁 SORGU flow finished in {fmt_sec(time.time() - t_flow)}\n", flush=True)
    return SORGU_OUT_CSV


def main():
    t_all = time.time()
    print(f"[{now()}] ⚙️  START sorgu_iylestir.py", flush=True)
    print(f"    MIN_IMPROVE={MIN_IMPROVE} | MAX_ATTEMPTS={MAX_ATTEMPTS} | ONLY_IMPROVED={ONLY_IMPROVED}", flush=True)
    print(f"    INPUT: {SORGU_IN_CSV}", flush=True)
    print(f"    OUTPUT: {SORGU_OUT_CSV}", flush=True)

    output = run_sorgu_flow()

    print(f"[{now()}] ✅ DONE in {fmt_sec(time.time() - t_all)}", flush=True)
    print(f"   • {os.path.abspath(output)}", flush=True)


if __name__ == "__main__":
    main()
