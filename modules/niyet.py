# modules/niyet.py (veya verdiğin dosyada aynen değiştir)
import pandas as pd

from config import output_dir

IN_CSV  = f"{output_dir}/html_icerik_niyet_uyumu.csv"
TOP_K   = 10
OUT_CSV = f"{output_dir}/icerik_niyet_top{TOP_K}.csv"

def sort_intent_similarity(dedup_within_intent: bool = True):
    # 1) Skor formatını bozmamak için string olarak yükle
    df = pd.read_csv(IN_CSV, encoding="utf-8-sig", dtype=str)

    # 2) Gerekli kolonlar
    need = {"Kullanıcı Niyeti", "Benzerlik Skoru", "Web İçeriği"}
    miss = need - set(df.columns)
    if miss:
        raise KeyError(f"Eksik kolon(lar): {miss}")

    # 3) Sıralama için sayısal kopya; çıkışta ham skoru yazacağız
    df["_score_raw"] = df["Benzerlik Skoru"]
    num = (df["_score_raw"]
             .str.replace(",", ".", regex=False)
             .str.replace("%", "", regex=False)
             .str.strip())
    df["_score_num"] = pd.to_numeric(num, errors="coerce")
    # Yüzde gibi duran değerler için 0–1 ölçeğine çek
    if pd.notna(df["_score_num"].max()) and df["_score_num"].max() > 1.5:
        df["_score_num"] = df["_score_num"] / 100.0

    # 4) Aynı niyet içinde aynı içerik tekrar etmesin (isteğe bağlı)
    if dedup_within_intent:
        df = df.drop_duplicates(subset=["Kullanıcı Niyeti", "Web İçeriği"], keep="first")

    # 5) Sırala ve her niyet için Top-10 al
    out = (df.sort_values(["Kullanıcı Niyeti", "_score_num"], ascending=[True, False])
            .groupby("Kullanıcı Niyeti", group_keys=True)
            .head(TOP_K)
            .reset_index(drop=True))

    # 6) Ham skoru aynen yaz ve kolon sırasını düzgünle
    out["Benzerlik Skoru"] = out["_score_raw"]
    cols = ["Kullanıcı Niyeti"]
    if "HTML Kaynağı" in out.columns: cols.append("HTML Kaynağı")
    cols += ["Web İçeriği", "Benzerlik Skoru"]
    if "URL" in out.columns: cols.append("URL")
    out = out[cols]

    # 7) Kaydet
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"✅ {OUT_CSV} yazıldı")
