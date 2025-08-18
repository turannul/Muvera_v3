import os, time
from turtle import st

from config import (
    html_icerik_niyet_uyumu_output,
    html_icerik_sorgu_uyumu_output,
    title_desc_uyum_output,
    title_desc_kendi_uyum_output,
    icerik_sorgu_top_output,
    icerik_niyet_top_output,
)
from modules.anlamsal_eslestirme import (
    anlamsal_eslestirme,
    tam_niyet_uyum_tablosu,
    tam_sorgu_uyum_tablosu,
    title_description_birbirine_uyum,
    title_description_uyumu,
)
from modules.intent_classifier import main as niyet_belirle
from modules.kullanici_sorgusu import sorgular
from modules.sorgu import sort_query_similarity
from modules.niyet import sort_intent_similarity
from modules.webScraping import get_structured_web_content_selenium

try:
    stage1_start = time.time()
    # ---- 1) URL ----  ! Always run
    url = "reklamvermek.com"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        print("added https://")
        if not url.startswith(("www.")):
            url = "www." + url
            print("added www.")
    print(f"Stage 1 completed in {(time.time() - stage1_start):.2f}s")

    # ---- 2) İçeriği topla ! Always run ----
    stage2_start = time.time()
    print("\n🌐 Sayfa indiriliyor ve yapılandırılıyor...")
    content = get_structured_web_content_selenium(url)
    print(f"Stage 2 completed in {(time.time() - stage2_start):.2f}s")

    # ---- 3) Anlamsal eşleşmeler ----
    stage3_start = time.time()
    print("\n🔍 Anlamsal eşleşmeler yapılıyor...")
    eslesme_df = anlamsal_eslestirme(content)
    print(f"Stage 3 completed in {(time.time() - stage3_start):.2f}s")

    # ---- 4) Kullanıcı niyeti tahmini ----
    stage4_start = time.time()
    print("\n🧠 Kullanıcı niyetleri çıkarılıyor...")
    niyet_listesi = niyet_belirle()  # (eslesme_df["Kullanıcı Niyeti"].unique().tolist())
    print(f"Stage 4 completed in {(time.time() - stage4_start):.2f}s")

    # ---- 5) Tüm içerik × niyet analizi ----
    stage5_start = time.time()
    print("\n📊 Tüm içerik × niyet eşleşmeleri oluşturuluyor...")
    niyet_listesi = eslesme_df["Kullanıcı Niyeti"].unique().tolist()
    tam_niyet_uyum_tablosu(content, niyet_listesi)
    print(f"Stage 5 completed in {(time.time() - stage5_start):.2f}s")

    # ---- 6) Tüm içerik × sorgu analizi ----
    stage6_start = time.time()
    print("\n📊 Tüm içerik × sorgu eşleşmeleri oluşturuluyor...")
    tam_sorgu_uyum_tablosu(content, sorgular)
    print(f"Stage 6 completed in {(time.time() - stage6_start):.2f}s")

    # ---- 7) Title & Description × sorgu uyumu ----
    stage7_start = time.time()
    print("\n📝 Title/Description alanlarının sorgularla uyumu hesaplanıyor...")
    title_description_uyumu(content, sorgular)
    print(f"Stage 7 completed in {(time.time() - stage7_start):.2f}s")

    # ---- 8) Title ↔ Description kendi aralarında uyum ----
    stage8_start = time.time()
    print("\n📊 Title ile Description birbirine göre uyumu hesaplanıyor...")
    title_description_birbirine_uyum(content)
    print(f"Stage 8 completed in {(time.time() - stage8_start):.2f}s")

    # ---- 9) Sorgu benzerlik skoru hesaplama ----
    if not os.path.exist(icerik_sorgu_top_output):
        stage1_start = time.time()
        print("\n📈 Sorgu benzerlik skorları sıralanıyor...")
        sort_query_similarity()
        print(f"Stage 9 completed in {(time.time() - stage1_start):.2f}s")

    # ---- 10) Niyet benzerlik skoru hesaplama ----
    if not os.path.exist(icerik_niyet_top_output):
        stage10_start = time.time()
        print("\n📈 Niyet benzerlik skorları sıralanıyor...")
        sort_intent_similarity()
        print(f"Stage 10 completed in {(time.time() - stage10_start):.2f}s")

except Exception as unknownErr:
    print(f"bir hata oldu: {unknownErr}")
except KeyboardInterrupt:
    exit(1)
