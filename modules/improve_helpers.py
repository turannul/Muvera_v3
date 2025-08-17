from __future__ import annotations
import os, json, re, time
import pandas as pd
from ollama import chat
from sentence_transformers import SentenceTransformer, util

from modules.prompt.prompt_intent import generate_niyet_prompt as _gen_niyet_prompt
from modules.prompt.prompt_query import generate_sorgu_prompt as _gen_sorgu_prompt

from config import (
    icerik_niyet_top10_output as NIYET_IN_CSV,
    icerik_sorgu_top10_output as SORGU_IN_CSV,
    icerik_niyet_iyilestirme_output as NIYET_OUT_CSV,
    icerik_sorgu_iyilestirme_output as SORGU_OUT_CSV,
    model as st_model,
    ollama_model as ollama_model
)


# ============== UTIL ==============
def now() -> str:
    return time.strftime("%H:%M:%S", time.localtime())


def fmt_sec(s: float) -> str:
    if s < 1:
        return f"{s * 1000:.0f} ms"
    m, r = divmod(s, 60)
    return f"{int(m)}m {r:.1f}s" if m >= 1 else f"{s:.2f} s"


def read_csv_robust(path: str) -> pd.DataFrame:
    t0 = time.time()
    print(f"[{now()}] ⬇️  Reading CSV: {path}", flush=True)
    for enc in (None, "utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc) if enc else pd.read_csv(path)
            print(f"[{now()}] ✅ CSV loaded ({len(df)} rows) in {fmt_sec(time.time() - t0)}", flush=True)
            return df
        except Exception:
            continue
    raise RuntimeError(f"CSV okunamadı: {path}")


def pick_col(df: pd.DataFrame, names):
    low = {c.lower(): c for c in df.columns}
    for n in names:
        if n in df.columns:
            return n
        if n.lower() in low:
            return low[n.lower()]

    def norm(s):
        return re.sub(r"[İIı]", "i", s, flags=re.I).lower()

    norm_map = {norm(c): c for c in df.columns}
    for n in names:
        if norm(n) in norm_map:
            return norm_map[norm(n)]
    return None


def norm_score(x) -> float:
    s = str(x if x is not None else "").replace("%", "").replace(",", ".").strip()
    m = re.findall(r"[-+]?\d*\.?\d+", s)
    if not m:
        return 0.0
    v = float(m[0])
    return round(v / 100.0, 6) if v > 1.5 else round(v, 6)


def similarity(a_text: str, b_text: str) -> float:
    if not a_text or not b_text:
        return 0.0
    a = st_model.encode(a_text, convert_to_tensor=True, normalize_embeddings=True)
    b = st_model.encode(b_text, convert_to_tensor=True, normalize_embeddings=True)
    return float(util.cos_sim(a, b).item())


def run_llm(prompt: str) -> str:
    t0 = time.time()
    print(f"[{now()}] 🔁 LLM call → {OLLAMA_MODEL} (chars: {len(prompt)})", flush=True)
    resp = chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
    out = resp.get("message", {}).get("content", str(resp))
    print(f"[{now()}] ✅ LLM done in {fmt_sec(time.time() - t0)}", flush=True)
    return out


def parse_llm_json(text: str) -> dict:
    m = re.search(r"\{{.*\}}", text, flags=re.S)
    if not m:
        raise ValueError("LLM yanıtında JSON bulunamadı.")
    return json.loads(m.group(0))


# ---- prompt builders ----
NIYET_SYS = (
    "Sen bir SEO ve içerik geliştirme uzmanısın. "
    "Görevin, kullanıcı niyetine göre mevcut metni küçük dokunuşlarla iyileştirmek. "
    "h1/h2: niyeti doğrudan karşılayan başlık; p/div: +5–10 kelime; li: +1–2 kelime. "
    "Anlamı bozma, pazarlama klişeleri ekleme. Sadece geçerli JSON döndür."
)
NIYET_HUM = '''.strip()

def build_niyet_prompt(intent, current, tag, old):
    if _gen_niyet_prompt:
        try:
            return _gen_niyet_prompt(intent, current, tag, old)
        except Exception:
            pass
    return f"{NIYET_SYS}\n{NIYET_HUM}".format(intent=intent, current=current, tag=tag, old=old)

def build_sorgu_prompt(query, current, tag, old):
    if _gen_sorgu_prompt:
        try:
            return _gen_sorgu_prompt(query, current, tag, old)
        except Exception:
            pass
    return build_niyet_prompt(query, current, tag, old)
        .replace("Kullanıcı Niyeti", "Kullanıcı Sorgusu")
        .replace("Geliştirilmiş İçerik", "Geliştirilmiş Metin")


# ---- core improve ----
def try_improve(mode, query_text, current_text, html_tag, old_score, min_improve, max_attempts):
    best_text = current_text
    best_score = old_score if old_score > 0 else similarity(query_text, current_text)

    for attempt in range(1, max_attempts + 1):
        print(f"    [{now()}] attempt {attempt}/{max_attempts} | baseline={best_score:.4f}", flush=True)
        prompt = build_niyet_prompt(query_text, best_text, html_tag, best_score) if mode == "niyet" else build_sorgu_prompt(query_text, best_text, html_tag, best_score)
        data = parse_llm_json(run_llm(prompt))

        cand = (
                data.get("Geliştirilmiş İçerik") if mode == "niyet"
                else data.get("Geliştirilmiş Metin")
        )
        if not isinstance(cand, str) or not cand.strip():
            print("    ↪️  LLM returned empty candidate; keeping current text", flush=True)
            cand = best_text

        new_score = similarity(query_text, cand)
        print(f"[{now()}] scored new={new_score:.4f} (delta={{(new_score - best_score):+.4f}})", flush=True)

        if new_score >= best_score * (1.0 + min_improve):
            print(f"🎯 improved ≥ {min_improve * 100:.3f}% — accepting", flush=True)
            return cand, new_score

        if new_score > best_score:
            print("    ⬆️  slight improvement; updating baseline and retrying", flush=True)
            best_text, best_score = cand, new_score

    print("⚖️  no sufficient improvement; returning best so far", flush=True)
    return best_text, best_score