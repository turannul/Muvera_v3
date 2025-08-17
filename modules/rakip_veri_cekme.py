import re
import time

import openpyxl
import pandas as pd
from serpapi import GoogleSearch

# =============== AYARLAR ===============
API_KEY = "26cb0c0c44cbb5ef59f4a9daadd6d9169243c1c8efccca9121020f2e09003447"  # API anahtarınızı buraya yazın
DOMAIN_BILGI_SAYFASI = "Sayfa sayısı"  # Domain bilgisinin bulunduğu sayfa adı
EXCEL_DOSYA_YOLU = "data/input/1hafta.xlsx"
EXCEL_CIKTI_YOLU = "data/output/sonuclar.xlsx"
SAYFA_SAYISI = 3  # İlk 3 sayfa (30 sonuç)
SORGU_LIMITI = 5  # Kaç sorguyu analiz edeceğiz
# =======================================


# Domain'i URL'den ayıkla
def domain_ayikla(url):
    # URL'den domain'i çıkarmak için düzenli ifade
    domain_pattern = r'https?://([^/]+)'
    match = re.search(domain_pattern, url)
    if match:
        return match.group(1)
    return url


# Excel'den kendi domain URL'sini al
def kendi_domaini_al(dosya_adi, sayfa_adi):
    try:
        df = pd.read_excel(dosya_adi, sheet_name=sayfa_adi, header=None)
        url = df.iloc[1, 0]  # A2 hücresi
        return domain_ayikla(url)
    except Exception as e:
        print(f"Domain bilgisi alınırken hata oluştu: {e}")
        return None


# Excel'den en popüler sorguları al
def en_populer_sorgulari_al(dosya_yolu, limit):
    try:
        df = pd.read_excel(dosya_yolu)
        df = df.dropna(subset=["En çok yapılan sorgular"])
        ilk_tiklama = df.sort_values(by="Tıklamalar", ascending=False).head(limit)
        ilk_gosterim = df.sort_values(by="Gösterimler", ascending=False).head(limit)
        birlesik = pd.concat([ilk_tiklama, ilk_gosterim]).drop_duplicates(subset=["En çok yapılan sorgular"])
        return birlesik["En çok yapılan sorgular"].tolist()
    except Exception as e:
        print(f"Sorgular alınırken hata oluştu: {e}")
        return []


# Google sonuçlarını çek - TEK SEFERDE TÜM SONUÇLARI ALIR
def google_sonuclari_cek(sorgu, num_pages=3):
    try:
        # Her sayfada 10 sonuç olduğu için toplam sonuç sayısı = num_pages * 10
        toplam_sonuc = num_pages * 10

        params = {
            "q": sorgu,
            "location": "Turkey",  # Türkiye'den arama yapmak için
            "hl": "tr",  # Türkçe sonuçlar için
            "gl": "tr",  # Türkiye için
            "num": toplam_sonuc,  # Tek seferde tüm sonuçları al
            "api_key": API_KEY
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        organic_results = results.get("organic_results", [])

        # Eğer istenilen sayıda sonuç gelmediyse, ek sorgu yap
        if len(organic_results) < toplam_sonuc:
            print(f"Uyarı: İstenen {toplam_sonuc} sonuç yerine {len(organic_results)} sonuç alındı.")

        time.sleep(1)  # API hız sınırlamasına karşı
        return organic_results
    except Exception as e:
        print(f"Google sonuçları çekilirken hata oluştu: {e}")
        return []


# Kendi sitemizin üstündekileri filtrele
def ust_siteleri_al(sonuclar, kendi_domain):
    pozisyon = None
    for i, sonuc in enumerate(sonuclar):
        link = sonuc.get("link", "")
        link_domain = domain_ayikla(link)
        if kendi_domain in link_domain:
            pozisyon = i
            break
    if pozisyon is None:
        print(f"{kendi_domain} listede bulunamadı. Tüm sonuçlar alınacak.")
        ust_siteler = sonuclar
    else:
        ust_siteler = sonuclar[:pozisyon]
    return ust_siteler


# Ana işlem
def main():
    # Kendi domain URL'sini Excel'den al
    KENDI_SITE = kendi_domaini_al(EXCEL_DOSYA_YOLU, DOMAIN_BILGI_SAYFASI)
    if not KENDI_SITE:
        print("Kendi site URL'si alınamadı. Lütfen Excel dosyasını kontrol edin.")
        return

    print(f"Kullanılan site URL'si: {KENDI_SITE}")

    sorgular = en_populer_sorgulari_al(EXCEL_DOSYA_YOLU, SORGU_LIMITI)
    if not sorgular:
        print("Sorgular alınamadı. Lütfen Excel dosyasını kontrol edin.")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ust Siteler"
    ws.append(["Sorgu", "Pozisyon", "Başlık", "URL", "Açıklama"])

    for sorgu in sorgular:
        print(f"[+] Sorgulanıyor: {sorgu}")
        try:
            tum_sonuc = google_sonuclari_cek(sorgu, num_pages=SAYFA_SAYISI)
            if not tum_sonuc:
                print(f"'{sorgu}' için sonuç alınamadı")
                continue

            ust_siteler = ust_siteleri_al(tum_sonuc, KENDI_SITE)

            for i, site in enumerate(ust_siteler):
                ws.append([
                    sorgu,
                    i + 1,
                    site.get("title", ""),
                    site.get("link", ""),
                    site.get("snippet", "")
                ])
        except Exception as e:
            print(f"'{sorgu}' işlenirken hata oluştu: {e}")
            continue

    try:
        wb.save(EXCEL_CIKTI_YOLU)
        print("✅ Tüm sorgular işlendi. Sonuçlar:", EXCEL_CIKTI_YOLU)
    except Exception as e:
        print(f"Excel dosyası kaydedilirken hata oluştu: {e}")


if __name__ == "__main__":
    main()
