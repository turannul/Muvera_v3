from __future__ import annotations

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate

# --- Şema (dışarıdaki kodların kullanması için) ---
OUTPUT_KEYS = {
    "candidate": "Geliştirilmiş İçerik",
    "aliases": ["gelistirilmis_icerik", "geliştirilmiş icerik"]
}
COLUMN_MAP = {
    "query": ["Kullanıcı Niyeti", "Kullanici Niyeti", "Niyet", "Intent"],
    "html": ["HTML Kaynağı", "HTML Kaynagi", "HTML Bölümü", "HTML Section"],
    "text": ["Web İçeriği", "Web Icerigi", "İçerik", "Icerik", "Metin", "Content"],
    "score": ["Benzerlik Skoru", "Skor", "Score", "Similarity Score", "similarity_score"]
}

def _cols(df: pd.DataFrame):
    # Eski tasarıma sadık: ilk 4 sütun
    c1, c2, c3, c4 = df.columns[:4]
    return {"query": c1, "html": c2, "text": c3, "score": c4}


def _human_template() -> str:
    return """
Girdi:
Kullanıcı Niyeti: "{kullanici_niyeti}"
Mevcut İçerik: "{mevcut_icerik}"
HTML Bölümü: "{html_bolumu}"
Eski Skor: {eski_skor}

Beklenen çıktı (JSON):
{
    "Kullanıcı Niyeti": "{kullanici_niyeti}",
    "Mevcut İçerik": "{mevcut_icerik}",
    "Geliştirilmiş İçerik": "Buraya geliştirilmiş hali gelecek",
    "HTML Bölümü": "{html_bolumu}"
}

Sadece bu JSON'u döndür; başka açıklama ekleme.
""".strip()


def build_prompt(system_template: str, kullanici_niyeti: str, mevcut_icerik: str, html_bolumu: str, eski_skor):
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", _human_template()),
    ])
    return prompt.format(
        kullanici_niyeti=kullanici_niyeti,
        mevcut_icerik=mevcut_icerik,
        html_bolumu=html_bolumu,
        eski_skor=eski_skor if eski_skor is not None else 0.0
    )
