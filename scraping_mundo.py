"""scraping de El Mundo"""

import sys
import requests
from bs4 import BeautifulSoup


# URL del periodico
URL = "https://www.elmundo.es/"

# Descargar HTML
response = requests.get(URL, timeout=10)
if response.status_code != 200:
    print("Error al descargar la página")
    sys.exit()

contenido = response.content

soup = BeautifulSoup(contenido, "html.parser")

# print(soup)

# # Buscar titulares

noticias = soup.select("h2 a,h3 a")[:5]

# print(noticias)

resultados = []
for a_tag in noticias:
    titulo = a_tag.get_text(strip=True)
    enlace = a_tag["href"]
    resultados.append((titulo, enlace))


# Mostrar en consola
print("=== Titulares de El Mundo ===\n")
for i, (titulo, enlace) in enumerate(resultados, 1):
    print(f"{i}. {titulo}\n {enlace}\n")

# print(response.content)


Prueba de cambios
