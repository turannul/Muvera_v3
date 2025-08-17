# modules/sorgu.py
import os
import re
import unicodedata

import pandas as pd

from config import output_dir

TOP_K = 10
IN_CSV = f"{output_dir}/html_icerik_sorgu_uyumu.csv"
OUT_CSV = f"{output_dir}/icerik_sorgu_top{TOP_K}.csv"


# ---------- Yardımcılar ----------
def _clean(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    # gizli karakter / BOM / zero-width / NBSP temizliği
    s = s.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\xa0", " ")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = unicodedata.normalize("NFKC", s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _score_to_num(raw: pd.Series) -> pd.Series:
    s = raw.astype(str).str.replace(",", ".", regex=False).str.replace("%", "", regex=False).str.strip()
    num = pd.to_numeric(s, errors="coerce")
    # yüzde ise 0–1 ölçeğine çek
    if pd.notna(num.max()) and num.max() > 1.5:
        num = num / 100.0
    return num


def _pick_column(df: pd.DataFrame, candidates) -> str | None:
    # normalize edilmiş karşılaştırma
    norm_map = {col: _clean(col) for col in df.columns}
    rev = {v: k for k, v in norm_map.items()}
    # doğrudan eşleşme
    for cand in candidates:
        c = _clean(cand)
        if c in rev:
            return rev[c]
    # içerir eşleşmesi
    for col, coln in norm_map.items():
        if any(_clean(cand) in coln for cand in candidates):
            return col
    return None


# ---------- Ana Fonksiyon ----------
def sort_query_similarity():
    if not os.path.exists(IN_CSV):
        # bazı koşullarda dosya repo kökünde olabilir
        alt = os.path.join("/mnt/data", os.path.basename(IN_CSV))
        if os.path.exists(alt):
            in_csv = alt
        else:
            raise FileNotFoundError(f"Bulunamadı: {IN_CSV}")
    else:
        in_csv = IN_CSV

    # Skor formatını korumak için string oku
    df_raw = pd.read_csv(in_csv, encoding="utf-8-sig", dtype=str)

    # Kolon isimlerini yakala (hem Türkçe hem varyantlara dayanıklı)
    col_sorgu = _pick_column(df_raw, ["Sorgu", "query", "kullanıcı sorgusu", "kullanici sorgusu", "kullanici_sorgusu", "kullanıcı_sorgusu"])
    col_skor = _pick_column(df_raw, ["Benzerlik Skoru", "benzerlik_skoru", "score", "similarity", "skor", "benzerlik"])
    col_icerik = _pick_column(df_raw, ["Web İçeriği", "web icerigi", "icerik", "içerik", "content", "metin", "cümle", "cumle"])
    # HTML Kaynağı için hem otomatik seçim hem de sabit fallback
    col_kaynak = _pick_column(df_raw, ["HTML Kaynağı", "html kaynagi", "html_kaynagi", "kaynak", "section", "bölüm", "bolum"])
    if not col_kaynak and "HTML Kaynağı" in df_raw.columns:
        col_kaynak = "HTML Kaynağı"  # doğrudan sabitle
    col_url = _pick_column(df_raw, ["URL", "sayfa_url", "page_url", "link"])

    need = [col_sorgu, col_skor, col_icerik]
    if not all(need):
        raise KeyError(f"Gerekli kolonlar eksik. Bulunanlar: {list(df_raw.columns)}")

    df = df_raw.copy()
    # Sıralama için sayısal skor kopyası; yazarken ham skoru bırak
    df["_score_raw"] = df[col_skor]
    df["_score_num"] = _score_to_num(df["_score_raw"])

    # Aynı Sorgu içinde aynı içerik tekrar etmesin
    df = df.drop_duplicates(subset=[col_sorgu, col_icerik], keep="first")

    # Skora göre sırala ve her Sorgu için Top-10 al
    topk = (
        df.sort_values([col_sorgu, "_score_num"], ascending=[True, False])
        .groupby(col_sorgu, group_keys=True)
        .head(TOP_K)
        .reset_index(drop=True)
    )

    # Çıkış DataFrame (HTML Kaynağı zorunlu kolon; yoksa boş doldur)
    out = pd.DataFrame()
    out["Sorgu"] = topk[col_sorgu].values
    out["HTML Kaynağı"] = topk[col_kaynak].values if (col_kaynak and col_kaynak in topk.columns) else ""
    out["Web İçeriği"] = topk[col_icerik].values
    out["Benzerlik Skoru"] = topk["_score_raw"].values
    if col_url:
        out["URL"] = topk[col_url].values

    os.makedirs(output_dir, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"✅ {OUT_CSV} yazıldı")


# Script olarak çağrılırsa üret
if __name__ == "__main__":
    sort_query_similarity()
