import requests
from PIL import Image
import io
import pillow_heif # Importa para que el soporte AVIF/HEIF se registre

# NUEVO: Llama explícitamente a la función de registro de Pillow-Heif
pillow_heif.register_heif_opener()

# URL de una de las imágenes que te está dando problemas (reemplaza si quieres otra)
IMAGE_URL = "https://images.grupoocasionplus.com/fn4tuSkdY9AyLFdjBwzudsP1EtWrcF14RzsJjDWglWY/normal_ao/aHR0cHM6Ly9mb3Rvcy5lc3RhdGljb3NtZi5jb20vZm90b3NfYW51bmNpb3MvMDAvMDcvMzAvNTgvNzYvNC94MDEuanBnPzE0ODI4OTczMTMzPSZtZDU9bnVsbA"

print(f"Intentando descargar y abrir: {IMAGE_URL}")
print(f"Versión de Pillow: {Image.__version__}")

# --- Diagnóstico de Formato HEIF/AVIF ---
# Para Pillow 11.2.1, es más probable que registre 'HEIF' si el soporte es correcto.
# No podemos usar .registered_formats() en esta versión, así que nos basamos en el comportamiento.



try:
    # Añade User-Agent como en tu script principal
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
    }
    response = requests.get(IMAGE_URL, timeout=10, headers=headers)
    response.raise_for_status() # Lanza un error para códigos HTTP 4xx/5xx

    # Intenta abrir la imagen con Pillow
    image_content = io.BytesIO(response.content)
    img = Image.open(image_content)

    # Si llega aquí, la imagen se abrió
    print(f"¡Éxito! La imagen se abrió correctamente.")
    print(f"Formato de la imagen: {img.format}") # Debería decir 'AVIF'
    print(f"Dimensiones de la imagen: {img.width}x{img.height}")

    # Opcional: guardar una copia para verificar
    # img.save("test_descargada.avif", format="AVIF") # Si quieres guardar como AVIF
    img.save("test_descargada.jpg", format="JPEG") # Mejor guardar como JPG para compatibilidad

except requests.exceptions.RequestException as e:
    print(f"Error de descarga: {e}")
except Image.UnidentifiedImageError:
    print("Error: Pillow no pudo identificar la imagen. El soporte AVIF no se ha cargado correctamente o el archivo no es una imagen válida.")
    print(f"Primeros 20 bytes de la respuesta: {response.content[:20]}")
    print(f"Content-Type de la respuesta: {response.headers.get('Content-Type')}")
except Exception as e:
    print(f"Error inesperado: {e}")