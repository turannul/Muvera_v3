import os
from sentence_transformers import SentenceTransformer
from ollama import Client

input_dir = os.path.join("data", "input")
output_dir = os.path.join("data", "output")

os.makedirs(input_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

model = SentenceTransformer("emrecan/bert-base-turkish-cased-mean-nli-stsb-tr")

ollama_client = Client(host='http://localhost:11434')  # Ollama arka planda çalışmalı
