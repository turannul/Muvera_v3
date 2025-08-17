from langchain_core.prompts import ChatPromptTemplate

def generate_sorgu_prompt(kullanici_sorgusu: str, mevcut_icerik: str, html_bolumu: str, eski_skor: float) -> str:
    """
    LLM'ye, metni küçük dokunuşlarla geliştirmesi için net talimat verir.
    Çıktı: yalnızca geçerli JSON.
    """

    system_template = """
        Sen bir SEO ve içerik geliştirme uzmanısın.
        Görevin, kullanıcı sorgusuna göre mevcut metni küçük dokunuşlarla iyileştirmektir.

        Kurallar:
        1) Benzerlik skorunu artırmaya odaklan, anlamı bozma.
        2) Metin türüne göre:
        - h1/h2: Kullanıcı sorgusundan DOĞRUDAN başlık üret (örn: "google reklam verme" → "Google Reklam Verme Nasıl Yapılır?").
        - p/div: Mevcut metni KORU, sadece sorguyu karşılayacak şekilde en fazla 5–10 kelime ekle.
        - li: Mevcut metni KORU, en fazla 1–2 kelime ekle.
        3) Uzunluk sınırları:
        - p/div: +5–10 kelime
        - li: +1–2 kelime
        - h1/h2: “Nasıl Yapılır?” / “Kılavuzu” varsa kesme.
        4) Her zaman değiştir. Aynen geri döndürmek YASAK.
        5) Reklam/CTA dili kullanma.
        6) Cevap **yalnızca geçerli JSON** olmalı.
        7) Kullanıcı sorgusundaki anahtar kelimeleri mutlaka geçirmelisin.
    """

    human_template = """
        Girdi:
        Kullanıcı Sorgusu: "{kullanici_sorgusu}"
        Mevcut İçerik: "{mevcut_icerik}"
        HTML Bölümü: "{html_bolumu}"
        Eski Skor: {eski_skor}

        Beklenen çıktı (yalnız JSON):
        {{
        "Kullanıcı Sorgusu": "{kullanici_sorgusu}",
        "Eski Metin": "{mevcut_icerik}",
        "Geliştirilmiş Metin": "Buraya geliştirilmiş hali gelecek",
        "HTML Bölümü": "{html_bolumu}"
        }}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", human_template),
    ])

    return prompt.format(
        kullanici_sorgusu=kullanici_sorgusu,
        mevcut_icerik=mevcut_icerik,
        html_bolumu=html_bolumu,
        eski_skor=eski_skor,
    )
