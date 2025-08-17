import os
import re

from config import (
    output_dir,
    html_icerik_niyet_uyumu_output,
    html_icerik_sorgu_uyumu_output,
    title_desc_uyum_output,
    title_desc_kendi_uyum_output,
    icerik_sorgu_top10_output,
    icerik_niyet_top10_output,
)
from modules.anlamsal_eslestirme import (
    anlamsal_eslestirme,
    tam_niyet_uyum_tablosu,
    tam_sorgu_uyum_tablosu,
    title_description_birbirine_uyum,
    title_description_uyumu,
)
from modules.intent_classifier import niyet_belirle
from modules.kullanici_sorgusu import sorgular
from modules.sorgu import sort_query_similarity
from modules.niyet import sort_intent_similarity
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
print("\n📊 Tüm içerik × niyet eşleşmeleri oluşturuluyor...")
niyet_listesi = eslesme_df["Kullanıcı Niyeti"].unique().tolist()
tam_niyet_uyum_tablosu(content, niyet_listesi)


# ---- 6) Tüm içerik × sorgu analizi ----
print("\n📊 Tüm içerik × sorgu eşleşmeleri oluşturuluyor...")
tam_sorgu_uyum_tablosu(content, sorgular)


# ---- 7) Title & Description × sorgu uyumu ----
print("\n📝 Title/Description alanlarının sorgularla uyumu hesaplanıyor...")
title_description_uyumu(content, sorgular)


# ---- 8) Title ↔ Description kendi aralarında uyum ----
print("\n📊 Title ile Description birbirine göre uyumu hesaplanıyor...")
title_description_birbirine_uyum(content)


# ---- 9) Sorgu benzerlik skoru hesaplama ----
if (icerik_sorgu_top10_output):
    print("\n📈 Sorgu benzerlik skorları sıralanıyor...")
    sort_query_similarity()
    print(f"✅ {icerik_sorgu_top10_output} yazıldı.")

# ---- 10) Niyet benzerlik skoru hesaplama ----
if (icerik_niyet_top10_output):
    print("\n📈 Niyet benzerlik skorları sıralanıyor...")
    sort_intent_similarity()
    print(f"✅ {icerik_niyet_top10_output} yazıldı.")