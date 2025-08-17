import os
import re

from config import output_dir
from modules.anlamsal_eslestirme import (anlamsal_eslestirme, tam_niyet_uyum_tablosu, tam_sorgu_uyum_tablosu, title_description_birbirine_uyum, title_description_uyumu)
from modules.intent_classifier import niyet_belirle
from modules.kullanici_sorgusu import sorgular
from modules.sorgu import OUT_CSV, TOP_K, sort_query_similarity
from modules.webScraping import get_structured_web_content_selenium


def temizle_niyet(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[.?!,:;]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace('"', '').replace("'", '')
    return text


# ---- 1) URL ----
url = "https://www.reklamvermek.com"  # isterseniz değiştirin
if not url.startswith(("http://", "https://")):
    url = "https://" + url

# ---- 2) İçeriği topla (İLK ÖNCE BU!) ----
print("\n🌐 Sayfa indiriliyor ve yapılandırılıyor...")
content = get_structured_web_content_selenium(url)

# ---- 3) Anlamsal eşleşmeler ----
print("\n🔍 Anlamsal eşleşmeler yapılıyor...")
eslesme_df = anlamsal_eslestirme(content)

# ---- 4) Kullanıcı niyeti tahmini ----
print("\n🧠 Kullanıcı niyetleri çıkarılıyor...")
niyetler = []
for s in eslesme_df["Sorgu"]:
    niyet = niyet_belirle(s)
    print(f"{s} → {niyet}")
    niyetler.append(temizle_niyet(niyet))

eslesme_df["Kullanıcı Niyeti"] = niyetler

# ---- 5) Tüm içerik × niyet analizi ----
if not os.path.exists(f"{output_dir}/html_icerik_niyet_uyumu.csv"):
    print("\n📊 Tüm içerik × niyet eşleşmeleri oluşturuluyor...")
    niyet_listesi = eslesme_df["Kullanıcı Niyeti"].unique().tolist()
    tam_niyet_df = tam_niyet_uyum_tablosu(content, niyet_listesi)
    tam_niyet_df.to_csv(f"{output_dir}/html_icerik_niyet_uyumu.csv", index=False)
    print("✅ html_icerik_niyet_uyumu.csv yazıldı.")

# ---- 6) Tüm içerik × sorgu analizi ----
if not os.path.exists(f"{output_dir}/html_icerik_sorgu_uyumu.csv"):
    print("\n📊 Tüm içerik × sorgu eşleşmeleri oluşturuluyor...")
    tam_sorgu_df = tam_sorgu_uyum_tablosu(content, sorgular)
    tam_sorgu_df.to_csv(f"{output_dir}/html_icerik_sorgu_uyumu.csv", index=False)
    print("✅ html_icerik_sorgu_uyumu.csv yazıldı.")

# ---- 7) Title & Description × sorgu uyumu ----
if not os.path.exists(f"{output_dir}/title_description_uyum.csv"):
    print("\n📝 Title/Description alanlarının sorgularla uyumu hesaplanıyor...")
    title_desc_df = title_description_uyumu(content, sorgular)
    title_desc_df.to_csv(f"{output_dir}/title_description_uyum.csv", index=False)
    print("✅ title_description_uyum.csv yazıldı.")

# ---- 8) Title ↔ Description kendi aralarında uyum ----
if not os.path.exists(f"{output_dir}/title_description_kendi_uyumu.csv"):
    print("\n📊 Title ile Description birbirine göre uyumu hesaplanıyor...")
    title_meta_df = title_description_birbirine_uyum(content)
    title_meta_df.to_csv(f"{output_dir}/title_description_kendi_uyumu.csv", index=False)
    print("✅ title_description_kendi_uyumu.csv yazıldı.")


# ---- 9) Sorgu benzerlik skoru hesaplama ----
if (f"{output_dir}/icerik_sorgu_top{TOP_K}.csv"):
    print("\n📈 Sorgu benzerlik skorları sıralanıyor...")
    sort_query_similarity()
    print(f"✅ {OUT_CSV} yazıldı.")

# ---- 10) Niyet benzerlik skoru hesaplama ----
if (f"{output_dir}/icerik_niyet_top{TOP_K}.csv"):
    print("\n📈 Niyet benzerlik skorları sıralanıyor...")
    from modules.niyet import sort_intent_similarity
    sort_intent_similarity()
    print(f"✅ {OUT_CSV} yazıldı.")
