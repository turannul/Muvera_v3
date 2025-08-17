from itertools import chain

import pandas as pd
import torch
from sentence_splitter import SentenceSplitter
from sentence_transformers import util

from config import model
from modules.kullanici_sorgusu import sorgular

# Türkçe için cümle ayırıcı
splitter = SentenceSplitter(language='tr')

def cumlelere_bol(metin):
    if not isinstance(metin, str):
        return []
    return splitter.split(metin)

# ✅ 1. Anlamsal eşleştirme (tek eşleşme)
def anlamsal_eslestirme(content):

    metinler = list(
        chain(
            content["headings"].get("h1", []),
            content["headings"].get("h2", []),
            content["headings"].get("h3", []),
            content.get("paragraphs", []),
            content.get("div_texts", []),
            content.get("lists", []),
            content.get("tables", [])
        )
    )
    sorgu_vecs = model.encode(sorgular, convert_to_tensor=True)
    metin_vecs = model.encode(metinler, convert_to_tensor=True)

    results = []
    for i, sorgu in enumerate(sorgular):
        skorlar = util.cos_sim(sorgu_vecs[i], metin_vecs)[0]
        en_yuksek_idx = torch.argmax(skorlar).item()
        en_yuksek_skor = skorlar[en_yuksek_idx].item()
        eslesen_metin = metinler[en_yuksek_idx]

        results.append({
            "Sorgu": sorgu,
            "Eşleşen İçerik": eslesen_metin,
            "Benzerlik Skoru": round(en_yuksek_skor, 4)
        })

    sonuc_df = pd.DataFrame(results)
    return sonuc_df

# ✅ 2. Tüm sorgulara göre içerik eşleşmeleri
def tam_sorgu_uyum_tablosu(content, sorgular: list):
    print("🔍 Sorgular ile cümle cümle eşleşme başlatıldı...")

    tum_parcalar = []
    for tag, liste in content["headings"].items():
        for metin in liste:
            for cumle in cumlelere_bol(metin):
                tum_parcalar.append({"html": tag, "icerik": cumle.strip()})

    for tag in ["paragraphs", "div_texts", "lists", "tables"]:
        for metin in content.get(tag, []):
            for cumle in cumlelere_bol(metin):
                tum_parcalar.append({"html": tag, "icerik": cumle.strip()})

    result_rows = []
    for parca in tum_parcalar:
        icerik = parca["icerik"]
        icerik_vec = model.encode(icerik, convert_to_tensor=True)
        sorgu_vecs = model.encode(sorgular, convert_to_tensor=True)

        cosine_scores = util.cos_sim(icerik_vec, sorgu_vecs)[0]
        for i, skor in enumerate(cosine_scores):
            result_rows.append({
                "HTML Kaynağı": parca["html"],
                "Web İçeriği": icerik,
                "Sorgu": sorgular[i],
                "Benzerlik Skoru": round(float(skor), 4)
            })

    df = pd.DataFrame(result_rows)
    return df

def tam_niyet_uyum_tablosu(content, niyet_listesi: list):
    print("🔍 Niyetler ile cümle cümle eşleşme başlatıldı...")

    tum_parcalar = []
    for tag, liste in content["headings"].items():
        for metin in liste:
            for cumle in cumlelere_bol(metin):
                tum_parcalar.append({"html": tag, "icerik": cumle.strip()})

    for tag in ["paragraphs", "div_texts", "lists", "tables"]:
        for metin in content.get(tag, []):
            for cumle in cumlelere_bol(metin):
                tum_parcalar.append({"html": tag, "icerik": cumle.strip()})

    result_rows = []
    for parca in tum_parcalar:
        icerik = parca["icerik"]
        icerik_vec = model.encode(icerik, convert_to_tensor=True)
        niyet_vecs = model.encode(niyet_listesi, convert_to_tensor=True)

        cosine_scores = util.cos_sim(icerik_vec, niyet_vecs)[0]
        for i, skor in enumerate(cosine_scores):
            result_rows.append({
                "HTML Kaynağı": parca["html"],
                "Web İçeriği": icerik,
                "Kullanıcı Niyeti": niyet_listesi[i],
                "Benzerlik Skoru": round(float(skor), 4)
            })

    df = pd.DataFrame(result_rows)
    return df

# ✅ 4. Başlık ve açıklama ile sorguların anlamsal uyumu
def title_description_uyumu(content: dict, sorgular: list) -> pd.DataFrame:
    baslik = content.get("title", "")
    aciklama = content.get("meta_description", "")

    entries = [("title", baslik), ("meta_description", aciklama)]
    sonuc = []

    for alan_adi, metin in entries:
        if not metin:
            continue
        metin_vec = model.encode(metin, convert_to_tensor=True)
        sorgu_vecs = model.encode(sorgular, convert_to_tensor=True)

        for i, sorgu in enumerate(sorgular):
            skor = util.cos_sim(metin_vec, sorgu_vecs[i])[0][0].item()
            sonuc.append({
                "Alan": alan_adi,
                "İçerik": metin,
                "Kullanıcı Sorgusu": sorgu,
                "Benzerlik Skoru": round(skor, 4)
            })

    return pd.DataFrame(sonuc)


# ✅ Başlık ve açıklama arasında benzerlik skoru hesaplayan fonksiyon
def title_description_birbirine_uyum(content: dict) -> pd.DataFrame:
    title = content.get("title", "").strip()
    description = content.get("meta_description", "").strip()

    if not title or not description:
        return pd.DataFrame([{
            "title": title,
            "meta_description": description,
            "Benzerlik Skoru": "veri eksik",
        }])

    title_vec = model.encode(title, convert_to_tensor=True)
    desc_vec = model.encode(description, convert_to_tensor=True)
    skor = util.cos_sim(title_vec, desc_vec)[0][0].item()

    return pd.DataFrame([{
        "title": title,
        "meta_description": description,
        "Benzerlik Skoru": round(skor, 4),
    }])