from __future__ import annotations

import os

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate

# --- Konfig ---
try:
    from config import output_dir  # "data/output" vb.
except ImportError:
    output_dir = "data/output"

NIYET_TOP10 = os.path.join(output_dir, "icerik_niyet_top10.csv")

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


# --- Yardımcılar ---
def _read_top10() -> pd.DataFrame:
    if not os.path.exists(NIYET_TOP10):
        raise FileNotFoundError(f"[HATA] Niyet verisi bulunamadı: {NIYET_TOP10}")
    df = pd.read_csv(NIYET_TOP10)
    if df.shape[1] < 4:
        raise ValueError("En az 4 kolon bekleniyordu: Niyet, HTML, İçerik, Skor")
    return df


def _cols(df: pd.DataFrame):
    # Eski tasarıma sadık: ilk 4 sütun
    c1, c2, c3, c4 = df.columns[:4]
    return {"query": c1, "html": c2, "text": c3, "score": c4}


def _system_template() -> str:
    return """
Sen bir SEO ve içerik geliştirme uzmanısın.
Görevin, kullanıcı niyetine (intent) göre mevcut metni küçük dokunuşlarla iyileştirmektir.

Kurallar:
1) Benzerlik skorunu artırmaya odaklan, anlamı bozma.
2) HTML bölümüne göre:
    - h1/h2: niyeti doğrudan karşılayan başlık üret (örn: "... nasıl" → "… Nasıl Yapılır?").
    - p/div: Mevcut metni KORU, en fazla 5–10 kelime ekle.
    - li: Mevcut metni KORU, en fazla 1–2 kelime ekle.
3) Uzunluk sınırları: p/div 5–10 kelime; li 1–2 kelime; h1/h2 kesme/özetleme yapma.
4) Her zaman değiştir; rollback yok.
5) Pazarlama/CTA klişeleri yok ("hedef kitlenize ulaşın", "kampanyanızı oluşturun" vb.).
6) Cevap DAİMA geçerli JSON olmalı.
7) Mevcut metin korunur; sadece küçük ekleme yapılır (kısaltma/özetleme YOK).
8) Niyet doğrudan karşılanır (örn. "… reklam verme nasıl" → metinde "nasıl yapılır" geçsin).
""".strip()


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


def _build_prompt(kullanici_niyeti: str, mevcut_icerik: str, html_bolumu: str, eski_skor):
    prompt = ChatPromptTemplate.from_messages([
        ("system", _system_template()),
        ("human", _human_template()),
    ])
    return prompt.format(
        kullanici_niyeti=kullanici_niyeti,
        mevcut_icerik=mevcut_icerik,
        html_bolumu=html_bolumu,
        eski_skor=eski_skor if eski_skor is not None else 0.0
    )


# --- Dışa açık API ---
def generate_prompts_for_intent(intent: str, topk: int = 10) -> list[dict]:
    """
    Seçilen 'intent' için ilk topk satırın LLM prompt'larını döndürür.
    Dönen her eleman: { "prompt": str, "row": {...} }
    """
    df = _read_top10()
    cols = _cols(df)
    mask = df[cols["query"]].astype(str).str.strip() == str(intent).strip()
    sub = df.loc[mask].copy()
    if sub.empty:
        return []

    # Skor varsa azalan sırala
    try:
        sub["_score"] = pd.to_numeric(sub[cols["score"]], errors="coerce")
        sub = sub.sort_values("_score", ascending=False)
    except Exception:
        pass

    out = []
    for _, r in sub.head(topk).iterrows():
        prompt = _build_prompt(
            kullanici_niyeti=str(r[cols["query"]] or ""),
            mevcut_icerik=str(r[cols["text"]] or ""),
            html_bolumu=str(r[cols["html"]] or ""),
            eski_skor=r.get(cols["score"], 0.0),
        )
        out.append({
            "prompt": prompt,
            "row": {
                "Kullanıcı Niyeti": r[cols["query"]],
                "HTML Bölümü": r[cols["html"]],
                "Web İçeriği": r[cols["text"]],
                "Benzerlik Skoru": r.get(cols["score"], None),
            }
        })
    return out


def generate_niyet_prompt() -> str:
    """
        Eski akışla uyum için: CSV'nin ilk satırı baz alınarak TEK prompt döndürür.
    """
    df = _read_top10()
    cols = _cols(df)
    r = df.iloc[0]
    return _build_prompt(
        kullanici_niyeti=str(r[cols["query"]] or ""),
        mevcut_icerik=str(r[cols["text"]] or ""),
        html_bolumu=str(r[cols["html"]] or ""),
        eski_skor=r.get(cols["score"], 0.0),
    )
