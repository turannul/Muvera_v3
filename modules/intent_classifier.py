# modules/intent_classifier.py (öneri)

import pandas as pd
from ollama import Client

from config import ollama_client, sorgu_niyet_tema_output
from modules.kullanici_sorgusu import sorgular


def niyet_belirle(sorgu: str) -> str:
    prompt = f'''
Bir kullanıcı şu arama sorgusunu yazdı: "{sorgu}"
Bu sorgunun özünde hangi amaç yatıyor?
Lütfen yalnızca 3–5 kelimelik, sade ve tematik bir niyet ifadesi ver.
Nokta veya açıklama yazma.
'''
    response = ollama_client.chat(
        model='gemma3:4b',
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response['message']['content'].strip().lower()


if __name__ == "__main__":
    # İsterseniz ayrı bir komutla sadece niyet temalarını üretirsiniz
    sonuclar = []
    for s in sorgular:
        n = niyet_belirle(s)
        print(f"{s} → {n}")
        sonuclar.append({"Sorgu": s, "Kısa Niyet Teması": n})
    pd.DataFrame(sonuclar).to_csv(sorgu_niyet_tema_output, index=False)
