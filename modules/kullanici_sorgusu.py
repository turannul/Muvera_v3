import pandas as pd

from config import bir_hafta_input, uc_ay_input

# Excel dosyasını oku
df = pd.read_excel(bir_hafta_input)
month3 = pd.read_excel(uc_ay_input)

# Boş olan sorguları ayıkla
df = df.dropna(subset=["En çok yapılan sorgular"])

# Tıklamalara göre en çok 5 sorgu
ilk5_tiklama = df.sort_values(by="Tıklamalar", ascending=False).head(5)

# Gösterimlere göre en çok 5 sorgu
ilk5_gosterim = df.sort_values(by="Gösterimler", ascending=False).head(5)

# İkisini birleştir ve tekrar edenleri çıkar
birlesik_sorgular = pd.concat([ilk5_tiklama, ilk5_gosterim]).drop_duplicates(subset=["En çok yapılan sorgular"])

# Nihai sorgu listesi
sorgular = birlesik_sorgular["En çok yapılan sorgular"].tolist()

print("Öncelikli sorgular:", sorgular)
