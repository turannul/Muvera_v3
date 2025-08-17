import pandas as pd
from config import output_dir

IN_CSV  = f"{output_dir}/html_icerik_niyet_uyumu.csv"
TOP_K   = 10
OUT_CSV = f"{output_dir}/icerik_niyet_top{TOP_K}.csv"


df = pd.read_csv(IN_CSV, encoding="utf-8")


# Skor normalize
def norm(x):
    s = str(x).replace("%","").replace(",",".").strip()
    try:
        v = float(s)
        if v > 1: v /= 100.0
        return round(v, 4)
    except:
        return 0.0


def sort_intent_similarity():
    if not "Benzerlik Skoru" in df.columns:
        raise KeyError("Beklenen kolon yok: 'Benzerlik Skoru'")
    
    df["Benzerlik Skoru"] = df["Benzerlik Skoru"].apply(norm)
    need = {"HTML Kaynağı", "Web İçeriği", "Kullanıcı Niyeti", "Benzerlik Skoru"}
    miss = need - set(df.columns)
    if miss:
        raise KeyError(f"Eksik kolon(lar): {miss}")

    # Her 'Kullanıcı Niyeti' için skora göre en yüksek 10
    out = (df.sort_values(["Kullanıcı Niyeti","Benzerlik Skoru"], ascending=[True, False])
            .groupby("Kullanıcı Niyeti", group_keys=True)
            .head(TOP_K)
            .reset_index(drop=True))

    out.to_csv(OUT_CSV, index=False, encoding="utf-8")
