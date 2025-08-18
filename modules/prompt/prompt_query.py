from __future__ import annotations

import os
import pandas as pd
from .prompt_helpers import _cols, build_prompt
from config import output_dir

SORGU_TOP10 = os.path.join(output_dir, "icerik_sorgu_top10.csv")


def _read_top10() -> pd.DataFrame:
    if not os.path.exists(SORGU_TOP10):
        raise FileNotFoundError(f"[HATA] Sorgu verisi bulunamadı: {SORGU_TOP10}")
    df = pd.read_csv(SORGU_TOP10)
    if df.shape[1] < 4:
        raise ValueError("En az 4 kolon bekleniyordu: Sorgu, HTML, İçerik, Skor")
    return df


def _system_template() -> str:
    return """
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
    """.strip()


def generate_prompts_for_sorgu(sorgu: str, topk: int = 10) -> list[dict]:
    """
    Seçilen 'sorgu' için ilk topk satırın LLM prompt'larını döndürür.
    Dönen her eleman: { "prompt": str, "row": {...} }
    """
    df = _read_top10()
    cols = _cols(df)
    mask = df[cols["query"]].astype(str).str.strip() == str(sorgu).strip()
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


def generate_sorgu_prompt() -> str:
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