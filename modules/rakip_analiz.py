# rakip_analiz.py — sorgu-merkezli rakip analizi (interactive query, no 'uyum_durumu')
from __future__ import annotations

import os, sys, re, json, glob, argparse, unicodedata
from pathlib import Path
import pandas as pd
from sentence_transformers import SentenceTransformer, util
from playwright.sync_api import sync_playwright
from lxml import html as lxml_html

# ------------------- Konfig / yollar -------------------
try:
    from config import output_dir as _cfg_output_dir
except Exception:
    _cfg_output_dir = None
output_dir = _cfg_output_dir or os.path.join("data", "output")
os.makedirs(output_dir, exist_ok=True)

# input_dir
try:
    from config import input_dir as _cfg_input_dir
except Exception:
    _cfg_input_dir = None
input_dir = _cfg_input_dir or os.path.join("data", "input")
os.makedirs(input_dir, exist_ok=True)

# Excel varsayılanı: data/input/sonuclar.xlsx
DEFAULT_EXCEL = os.path.join(input_dir, "sonuclar.xlsx")

# ------------------- Semantik model -------------------
ST_MODEL_NAME = os.getenv("ST_MODEL_NAME", "emrecan/bert-base-turkish-cased-mean-nli-stsb-tr")
_model: SentenceTransformer | None = None
def model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(ST_MODEL_NAME)
    return _model

# (opsiyonel) stealth
try:
    from playwright_stealth import stealth_sync  # type: ignore
except Exception:
    def stealth_sync(page):  # no-op
        return None

# ------------------- Genel ayarlar -------------------
OUR_SITE = "reklamvermek.com"
HEADERS = {"Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"}
SEM_THRESHOLD = 0.50  # snippet/meta eşik

# ------------------- Yardımcılar -------------------
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokenize_tr(s: str) -> list[str]:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    s = re.sub(r"[^\wğüşöçıİĞÜŞÖÇ]+", " ", s)
    return [t for t in s.split() if len(t) >= 2]

def _overlap_ratio(query: str, text: str) -> float:
    qt, tt = set(_tokenize_tr(query)), set(_tokenize_tr(text))
    if not qt or not tt:
        return 0.0
    return len(qt & tt) / max(1, len(qt))

def _score_to_float(x) -> float:
    s = str(x) if x is not None else ""
    s = s.replace("%", "").replace(",", ".").strip()
    m = re.findall(r"[-+]?\d*\.?\d+", s)
    if not m:
        return float("nan")
    v = float(m[0])
    return v / 100.0 if v > 1.5 else v

def _norm_dedup_key(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s+", " ", s).strip().casefold()
    s = re.sub(r"^[^\wğüşöçıİĞÜŞÖÇ]+|[^\wğüşöçıİĞÜŞÖÇ]+$", "", s)
    return s

def _dedup_exact_keep_order(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        k = _norm_dedup_key(it)
        if k and k not in seen:
            out.append(it); seen.add(k)
    return out

def drop_near_duplicates_texts(rows: pd.DataFrame, text_col="icerik", sim_thresh=0.95):
    if rows.empty or text_col not in rows.columns:
        return rows
    keep_idx, embs = [], []
    for i, t in enumerate(rows[text_col].astype(str).tolist()):
        e = model().encode(t, normalize_embeddings=True)
        if all(float(util.cos_sim(e, ee)) < sim_thresh for ee in embs):
            keep_idx.append(i); embs.append(e)
    return rows.iloc[keep_idx].copy()

# ------------------- CSV/Excel I/O -------------------
def read_csv_robust(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=None, engine="python")
    except Exception:
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return pd.read_csv(path, encoding=enc)
            except Exception:
                continue
    raise RuntimeError(f"CSV okunamadı: {path}")

def read_excel_robust(path: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path)
    except Exception:
        return pd.read_excel(path, engine="openpyxl")

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    new_cols = {c: c.strip().translate(tr_map).lower().replace(" ", "_") for c in df.columns}
    return df.rename(columns=new_cols)

def pick(df: pd.DataFrame, cands):
    for c in cands:
        if c in df.columns:
            return c
    return None

def load_many(pattern: str) -> pd.DataFrame:
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        raise SystemExit(f"Dosya bulunamadı: {pattern}")
    dfs = []
    for f in files:
        df = read_csv_robust(f)
        df = normalize_cols(df)
        df["kaynak_dosya"] = f
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text

def domain_from_url(url: str) -> str:
    if not isinstance(url, str):
        url = str(url)
    url = re.sub(r"^https?://", "", url.strip().lower()).split("/")[0]
    return re.sub(r"^www\.", "", url)

# ------------------- İçerik filtreleme (yalnızca sorgu) -------------------
def _norm_for_csv_dedup(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s) if s is not None else "")
    return re.sub(r"\s+", " ", s).strip().casefold()

def filter_for_query(df: pd.DataFrame, query_text: str) -> pd.DataFrame:
    """Seçilen sorguya ait satırlar; varsa skorla sırala; tekilleştir."""
    sorgu_col = pick(df, ["kullanici_sorgusu", "sorgu", "query", "aranan_sorgu"])
    skor_col  = pick(df, ["benzerlik_skoru", "skor", "score", "similarity_score", "benzerlik_skoru"])
    html_col  = pick(df, ["html_bolumu", "html_section", "bolum", "html_kaynagi", "html_kaynağı", "html_kaynaği"])
    text_col  = pick(df, ["icerik", "i̇cerik", "metin", "content", "web_içeriği", "web_icerigi"])

    if not sorgu_col:
        raise SystemExit("CSV'de sorgu sütunu yok (kullanici_sorgusu/sorgu/query).")

    q_mask = df[sorgu_col].astype(str).str.strip().str.casefold() == query_text.casefold()
    out = df.loc[q_mask].copy()

    if skor_col and skor_col in out.columns:
        out["_score"] = pd.to_numeric(out[skor_col], errors="coerce")
        out = out.sort_values(by="_score", ascending=False)
    else:
        if text_col in out.columns:
            texts = out[text_col].astype(str).fillna("").tolist()
            if texts:
                q_emb = model().encode(query_text, normalize_embeddings=True)
                i_emb = model().encode(texts, normalize_embeddings=True)
                out["_score"] = list(util.cos_sim(q_emb, i_emb).cpu().numpy().flatten())
                out = out.sort_values(by="_score", ascending=False)

    # Kolon sırası
    ordered = []
    for group in [[html_col], [text_col], ["_score"], ["kaynak_dosya"], [sorgu_col]]:
        for c in group:
            if c and c in out.columns and c not in ordered:
                ordered.append(c)
    for c in out.columns:
        if c not in ordered:
            ordered.append(c)

    # Tekilleştirme
    if text_col:
        out["_dedup_key"] = out[text_col].astype(str).map(_norm_for_csv_dedup) + "||" + out.get(html_col, "").astype(str).map(_norm_for_csv_dedup)
        out = out.drop_duplicates(subset=["_dedup_key"]).drop(columns=["_dedup_key"])
        out = drop_near_duplicates_texts(out, text_col=text_col, sim_thresh=0.95)

    return out[ordered]

# ------------------- SERP/üstümüzdeki siteler -------------------
def read_excel_or_empty(path: str | None) -> pd.DataFrame:
    try:
        if path and os.path.exists(path):
            return read_excel_robust(path)
    except Exception:
        pass
    return pd.DataFrame([])

def get_competitors_above(query_text: str, excel_path: str | None):
    """Seçilen sorgu için bizden üstteki URL'ler ve konumumuz."""
    df = read_excel_or_empty(excel_path or DEFAULT_EXCEL)
    if df.empty:
        return [], None
    df = normalize_cols(df)

    sorgu_col = pick(df, ["sorgu", "query", "aranan_sorgu", "kullanici_sorgusu"])
    url_col   = pick(df, ["url", "site", "website", "adres"])
    rank_col  = pick(df, ["konum", "pozisyon", "sira", "rank", "position"])
    if not (sorgu_col and url_col and rank_col):
        return [], None

    df["_domain"] = df[url_col].astype(str).map(domain_from_url)
    q_mask = df[sorgu_col].astype(str).str.strip().str.casefold() == query_text.casefold()
    sub = df.loc[q_mask].copy()
    if sub.empty:
        return [], None

    sub["_rank"] = pd.to_numeric(sub[rank_col], errors="coerce")
    ours = sub.loc[sub["_domain"] == OUR_SITE]
    our_best = (sub["_rank"].max() + 1) if ours.empty else ours["_rank"].min()

    above = sub.loc[sub["_rank"] < our_best].sort_values("_rank", ascending=True)
    urls_in_order = [u for u in above[url_col].astype(str).tolist() if u and domain_from_url(u) != OUR_SITE]
    return urls_in_order, int(our_best) if pd.notna(our_best) else None

# ------------------- HTML çekme + parse + skor -------------------
COMMON_COOKIE_SELECTORS = [
    "button#onetrust-accept-btn-handler",
    "button[aria-label*='Kabul']",
    "button:has-text('Kabul et')",
    "button:has-text('Accept')",
    "button:has-text('Tümünü kabul et')",
    "button:has-text('Accept all')",
]
_SENT_SPLIT = re.compile(r"(?<=[\.\!\?…])\s+")

NOISE_PATTERNS = [
    r"\b(hakkında|privacy|gizlilik|telif|şartlar|koşullar|terms|policy|çerez|cookies)\b",
    r"\b(bize ulaşın|iletişim|contact|developers|geliştiriciler)\b",
    r"\b(yardım merkezi|help center|yardım)\b",
    r"\b(oturum aç|giriş yap|sign in|log in)\b",
    r"\b(aydınlatma metni|kvkk|çerez aydınlatma)\b",
]

def _auto_scroll(page, step=1200, pause_ms=250, max_passes=8):
    last_height = page.evaluate("() => document.body.scrollHeight")
    for _ in range(max_passes):
        page.evaluate(f"() => window.scrollBy(0, {step})")
        page.wait_for_timeout(pause_ms)
        new_height = page.evaluate("() => document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def _try_click_cookies(page):
    for sel in COMMON_COOKIE_SELECTORS:
        try:
            el = page.locator(sel)
            if el.count() > 0 and el.first.is_visible():
                el.first.click(timeout=1500)
                page.wait_for_timeout(400)
                return True
        except Exception:
            continue
    return False

def fetch_html_rendered(url: str, timeout_ms=25000, retries=2) -> str:
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
    ]
    for attempt in range(min(retries, len(user_agents))):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
                context = browser.new_context(
                    user_agent=user_agents[attempt],
                    extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]}
                )
                page = context.new_page()
                stealth_sync(page)
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                _try_click_cookies(page)
                _auto_scroll(page, step=1400, pause_ms=300, max_passes=10)
                for sel in ["main", "[role=main]", "article", ".content", "#content"]:
                    try:
                        page.wait_for_selector(sel, timeout=2000); break
                    except Exception:
                        continue
                page.wait_for_timeout(600)
                content = page.content()
                context.close(); browser.close()
                if content and content.strip():
                    return content
        except Exception:
            continue
    return ""

def _split_block_to_sentences(block_text: str):
    return [s.strip() for s in _SENT_SPLIT.split(block_text or "") if _norm(s)]

def _strip_noise_lines(text: str) -> str:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    kept = []
    for l in lines:
        low = l.lower()
        if any(re.search(p, low) for p in NOISE_PATTERNS): continue
        if len(l) > 600: continue
        kept.append(l)
    return _norm(" ".join(kept))

def sentence_mode_snippets(query: str, tree, top_k=3, threshold=0.50, context_radius=1):
    main = tree
    for xp in ["//*[@role='main']", "//main", "//*[contains(@id,'main')]", "//*[contains(@class,'content')]", "//*[contains(@id,'content')]"]:
        nodes = tree.xpath(xp)
        if nodes: main = nodes[0]; break

    blocks = []
    for node in main.xpath("|".join([
        ".//p",".//li",".//section",".//article",".//blockquote",".//dd",".//dt",
        ".//div[not(.//p) and string-length(normalize-space())>0]"
    ])):
        txt = _strip_noise_lines(_norm(node.text_content()))
        if len(txt) >= 20: blocks.append(txt)

    blocks = _dedup_exact_keep_order(blocks)

    all_sentences, block_sents = [], []
    for bi, bt in enumerate(blocks):
        sents = _split_block_to_sentences(bt)
        block_sents.append(sents)
        for si, s in enumerate(sents): all_sentences.append((s, bi, si))

    if not all_sentences: return []

    sent_texts = [s for s,_,_ in all_sentences]
    q_emb = model().encode(query, normalize_embeddings=True)
    i_emb = model().encode(sent_texts, normalize_embeddings=True)
    sem = util.cos_sim(q_emb, i_emb).cpu().numpy().flatten()

    scored = []
    for (s, bi, si), sc in zip(all_sentences, sem):
        ov = _overlap_ratio(query, s)
        if ov == 0 and sc < (threshold + 0.10): continue
        final = 0.7*float(sc) + 0.3*ov
        scored.append({"text": s, "score": round(max(0.0, min(1.0, final)), 4), "block": bi, "idx": si})

    scored.sort(key=lambda x: x["score"], reverse=True)
    if not scored:
        topn = min(top_k, len(all_sentences))
        scored = [{"text": all_sentences[i][0], "score": round(float(sem[i]),4), "block": all_sentences[i][1], "idx": all_sentences[i][2]} for i in range(topn)]

    snippets, seen = [], set()
    for item in scored:
        key = _norm_dedup_key(item["text"])
        if key in seen: continue
        seen.add(key)
        bi, si = item["block"], item["idx"]
        sents = block_sents[bi]
        start, end = max(0, si-context_radius), min(len(sents), si+context_radius+1)
        merged = " ".join(sents[start:end]).strip()
        snippets.append({"text": merged, "score": item["score"]})
        if len(snippets) >= top_k: break
    return snippets[:top_k]

def _score_items(query: str, items: list[str], top_k=10, threshold=0.50, pos_boost=0.0):
    items = _dedup_exact_keep_order([_norm(x) for x in items if _norm(x)])
    if not items: return []
    q_emb = model().encode(query, normalize_embeddings=True)
    i_emb = model().encode(items, normalize_embeddings=True)
    sem = util.cos_sim(q_emb, i_emb).cpu().numpy().flatten()
    results = []
    for txt, s in zip(items, sem):
        ov = _overlap_ratio(query, txt)
        if ov == 0 and s < (threshold + 0.10): continue
        final = 0.7*float(s) + 0.3*ov + pos_boost
        results.append({"text": txt, "score": round(max(0.0, min(1.0, final)), 4)})
    above = [r for r in results if r["score"] >= threshold]
    ranked = sorted(above if above else results, key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]

def _collect_query_relevant_meta_lxml(tree, query: str, threshold=0.50):
    t = tree.xpath("string(//title)")
    titles = []
    if t: titles.append(_norm(t))
    titles += [_norm(x) for x in tree.xpath("//meta[@property='og:title']/@content")]
    titles += [_norm(x) for x in tree.xpath("//meta[@name='twitter:title']/@content")]
    titles_scored = _score_items(query, titles, top_k=5, threshold=threshold, pos_boost=0.08)

    descs = []
    descs += [_norm(x) for x in tree.xpath("//meta[@name='description']/@content")]
    descs += [_norm(x) for x in tree.xpath("//meta[@property='og:description']/@content")]
    descs += [_norm(x) for x in tree.xpath("//meta[@name='twitter:description']/@content")]
    descs_scored = _score_items(query, descs, top_k=8, threshold=threshold, pos_boost=0.05)

    heads = {}
    for level in range(1,7):
        texts = [_norm(el.text_content()) for el in tree.xpath(f"//h{level}")]
        heads[f"h{level}"] = _score_items(query, texts, top_k=10, threshold=threshold, pos_boost=0.06 if level==1 else 0.0)
    return {"titles": titles_scored, "descriptions": descs_scored, "headings": heads}

def parse_meta_and_snippets(html, base_url, query, max_snippets=3):
    tree = lxml_html.fromstring(html)
    meta = _collect_query_relevant_meta_lxml(tree, query, threshold=SEM_THRESHOLD)
    snippets = sentence_mode_snippets(query=query, tree=tree, top_k=max_snippets, threshold=SEM_THRESHOLD, context_radius=1)

    def _top1(lst): return (lst[0]["text"] if lst else None)
    title = _top1(meta.get("titles", []))
    desc  = _top1(meta.get("descriptions", []))
    h1    = _top1(meta.get("headings", {}).get("h1", []))

    return {"title": title, "description": desc, "h1": h1, "eslesen_snippetler": snippets, "url": base_url}

def _is_all_empty(obj: dict) -> bool:
    return not (obj.get("title") or obj.get("description") or obj.get("h1") or obj.get("eslesen_snippetler"))

def analyze_competitor_sites(url_list, query, max_snippets=3):
    results = []
    for url in url_list:
        html = fetch_html_rendered(url)
        if not html:
            results.append({"title": None, "description": None, "h1": None,
                            "eslesen_snippetler": [], "url": url,
                            "not": "HTML boş veya erişilemedi (bot engeli / yönlendirme / hata)."})
            continue
        rec = parse_meta_and_snippets(html, url, query, max_snippets=max_snippets)
        if _is_all_empty(rec):
            rec["not"] = "Sayfa yüklendi ama title/description/h1/snippet bulunamadı."
        results.append(rec)
    return results

# ------------------- JSON için uyumlu_kayitlar -------------------
def build_uyumlu_kayitlar(df: pd.DataFrame, query_text: str, topk: int | None = 10):
    """DataFrame -> uyumlu_kayitlar listesi (skora göre DESC, topk kadar)."""
    sorgu_col = pick(df, ["kullanici_sorgusu", "sorgu", "query", "aranan_sorgu"])
    html_col  = pick(df, ["html_bolumu", "html_section", "bolum", "html_kaynagi", "html_kaynağı", "html_kaynaği"])
    text_col  = pick(df, ["icerik", "i̇cerik", "metin", "content", "web_içeriği", "web_icerigi"])
    skor_col  = pick(df, ["benzerlik_skoru", "skor", "score", "similarity_score", "benzerlik_skoru"])

    out = []
    for _, r in df.iterrows():
        icerik = str(r.get(text_col, "") or "")
        html_bolumu = str(r.get(html_col, "") or "")
        raw_score = r.get(skor_col, None)
        s = _score_to_float(raw_score)
        if not (s == s):  # NaN ise yeniden hesapla
            s = float(util.cos_sim(
                model().encode(query_text, normalize_embeddings=True),
                model().encode(icerik, normalize_embeddings=True)
            ).item())
        out.append({
            "html_bolumu": html_bolumu if html_bolumu else None,
            "icerik": icerik,
            "benzerlik_skoru": float(round(s, 6)),
            "kaynak_dosya": r.get("kaynak_dosya", ""),
            "kullanici_sorgusu": str(r.get(sorgu_col, "") or query_text)
        })

    # Skora göre sırala ve topk uygula
    out.sort(key=lambda r: r["benzerlik_skoru"], reverse=True)
    if topk is not None:
        out = out[:int(topk)]
    return out

# ------------------- MAIN -------------------
def main():
    global SEM_THRESHOLD

    ap = argparse.ArgumentParser(description="Rakip Analiz — sorgu-merkezli (interactive query, no 'uyum_durumu')")
    ap.add_argument("--glob",
        default=f"{output_dir}/html_icerik_sorgu_uyumu.csv",
        help="CSV yolu/deseni. Vars: output_dir/html_icerik_sorgu_uyumu.csv")
    ap.add_argument("--query", default=None, help="Hedef sorgu. Vermezsen terminalden sorulur.")
    ap.add_argument("--excel", default=None, help=f"SERP Excel yolu (vars: {DEFAULT_EXCEL})")
    ap.add_argument("--threshold", type=float, default=0.50, help="Snippet/meta eşiği (0-1). Vars: 0.50")
    ap.add_argument("--max-snippets", type=int, default=3, help="Rakip sayfadan alınacak maksimum snippet")
    ap.add_argument("--topk", type=int, default=10, help="JSON'a eklenecek uyumlu_kayit sayısı (vars: 10)")
    args = ap.parse_args()

    SEM_THRESHOLD = float(args.threshold)

    # 1) CSV'yi yükle
    df_all = load_many(args.glob)

    # 2) Sorgu
    if args.query:
        selected = args.query.strip()
    else:
        try:
            selected = input("🔎 Analiz etmek istediğiniz sorguyu yazın: ").strip()
        except EOFError:
            selected = ""
    if not selected:
        raise SystemExit("Sorgu boş olamaz.")

    # 3) Seçilen sorgu için satırlar
    result_df = filter_for_query(df_all, selected)

    # ←← İsteğe bağlı: burada da kıs (sıralama zaten DESC):
    if args.topk and args.topk > 0:
        result_df = result_df.head(args.topk)

    # 4) Üstümüzdeki siteler (SERP excel)
    comp_list, our_rank = get_competitors_above(selected, args.excel)

    # 5) Rakip sayfalarında snippet+meta
    rakip_kullanimlar = analyze_competitor_sites(comp_list, selected, max_snippets=args.max_snippets) if comp_list else []

    # 6) JSON
    uyumlu_kayitlar = build_uyumlu_kayitlar(result_df, selected, topk=args.topk)
    data = {
        "site": "https://reklamvermek.com/",
        "query": selected,
        "bizim_tahmini_sira": our_rank,
        "uyumlu_kayit_sayisi": len(uyumlu_kayitlar),
        "uyumlu_kayitlar": uyumlu_kayitlar,
        "ustumuzde_olan_siteler": comp_list or [],
        "rakip_sorgu_kullanimlari": rakip_kullanimlar
    }

    # 7) Kaydet
    out_dir = Path(output_dir) / "json"
    out_dir.mkdir(exist_ok=True, parents=True)
    json_path = out_dir / f"analiz_{slugify(selected)}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON kaydedildi: {json_path.resolve()}")
    print(f"[DEBUG] topk={args.topk}, DF_satir={len(result_df)}, JSON_kayit={len(uyumlu_kayitlar)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
