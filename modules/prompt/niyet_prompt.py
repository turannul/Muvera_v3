from __future__ import annotations
import os
import pandas as pd
from config import output_dir
from .prompt_shared import build_prompt, _cols

NIYET_TOP10 = os.path.join(output_dir, "icerik_niyet_top10.csv")


def _read_top10() -> pd.DataFrame:
    if not os.path.exists(NIYET_TOP10):
        raise FileNotFoundError(f"[HATA] Niyet verisi bulunamadı: {NIYET_TOP10}")
    df = pd.read_csv(NIYET_TOP10)
    if df.shape[1] < 4:
        raise ValueError("En az 4 kolon bekleniyordu: Niyet, HTML, İçerik, Skor")
    return df


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
        prompt = build_prompt(
            system_template=_system_template(),
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
    return build_prompt(
        system_template=_system_template(),
        kullanici_niyeti=str(r[cols["query"]] or ""),
        mevcut_icerik=str(r[cols["text"]] or ""),
        html_bolumu=str(r[cols["html"]] or ""),
        eski_skor=r.get(cols["score"], 0.0),
    )