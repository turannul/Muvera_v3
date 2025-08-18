import ollama
import os
from sentence_transformers import SentenceTransformer

# Directories
input_dir = os.path.join("data", "input")
output_dir = os.path.join("data", "output")
json_output_dir = os.path.join(output_dir, "json")

# Create directories if they don't exist
os.makedirs(input_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)
os.makedirs(json_output_dir, exist_ok=True)

# Top K values
TOP_K_NIYET = 10
TOP_K_SORGU = 10

# Input files
bir_hafta_input = os.path.join(input_dir, "1hafta.xlsx")
uc_ay_input = os.path.join(input_dir, "3ay.xlsx")
sonuclar_input = os.path.join(input_dir, "sonuclar.xlsx")

# Output files
title_desc_uyum_output = os.path.join(output_dir, "title_description_uyum.csv")
title_desc_kendi_uyum_output = os.path.join(output_dir, "title_description_kendi_uyumu.csv")
html_icerik_niyet_uyumu_output = os.path.join(output_dir, "html_icerik_niyet_uyumu.csv")
html_icerik_sorgu_uyumu_output = os.path.join(output_dir, "html_icerik_sorgu_uyumu.csv")
icerik_niyet_top_output = os.path.join(output_dir, f"icerik_niyet_top{TOP_K_NIYET}.csv")
icerik_sorgu_top_output = os.path.join(output_dir, f"icerik_sorgu_top{TOP_K_SORGU}.csv")
icerik_niyet_iyilestirme_output = os.path.join(output_dir, "icerik_niyet_iyilestirme.csv")
icerik_sorgu_iyilestirme_output = os.path.join(output_dir, "icerik_sorgu_iyilestirme.csv")
sorgu_niyet_tema_output = os.path.join(output_dir, "sorgu_niyet_tema.csv")


# Model and client
model = SentenceTransformer("emrecan/bert-base-turkish-cased-mean-nli-stsb-tr")
ollama_client = ollama.Client(host='http://localhost:11434')
ollama_model = "gemma3:4b"

# API Keys
SERPAPI_API_KEY = "26cb0c0c44cbb5ef59f4a9daadd6d9169243c1c8efccca9121020f2e09003447"


url: str = "reklamvermek.com"
