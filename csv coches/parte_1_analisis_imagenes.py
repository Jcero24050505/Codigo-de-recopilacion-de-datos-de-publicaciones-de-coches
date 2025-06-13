import pandas as pd
import requests
import os
import json
from PIL import Image  # Importar la clase Image de Pillow
import io
import time
from datetime import datetime
import math

# --- Configuración ---
# ¡IMPORTANTE! ACTUALIZA ESTAS RUTAS A TU NUEVA UBICACIÓN
CSV_PATH = "C:\\Users\\CERO\\PycharmProjects\\PythonProject1\\csv coches\\Coches_Ocasión.csv"  # Asegúrate de que esta es la ruta correcta
DOWNLOAD_BASE_DIR = "C:\\Users\\CERO\\PycharmProjects\\PythonProject1\\csv coches\\imagenes_coches_descargadas"
LOCAL_JSON_PATH = "C:\\Users\\CERO\\PycharmProjects\\PythonProject1\\csv coches\\listings_with_local_data.json"
ANALYSIS_RESULTS_PATH = "C:\\Users\\CERO\\PycharmProjects\\PythonProject1\\csv coches\\analysis_results.json"
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos
MAX_IMAGE_COUNT_PER_CAR = 25  # Límite de imágenes por coche
MIN_SIZE_BYTES = 5000  # Tamaño mínimo en bytes para considerar la imagen válida (puede ser útil para filtrar placeholders)

# --- Inicialización de métricas para el análisis ---
total_cars_processed = 0
total_download_size_bytes = 0
total_image_width = 0
total_image_height = 0

total_images_downloaded_global_counter = []
total_download_size_bytes_global_counter = []
total_image_width_global_counter = []
total_image_height_global_counter = []

successful_cars = 0
failed_cars = 0
images_per_car_counts = []
download_errors_by_type = {}


def safe_download_image(url, destination_path, guid_anuncio):
    """
    Descarga una imagen de forma segura con reintentos, utilizando solo Pillow.
    Asegura que la URL de descarga termina en .jpg para forzar el formato.
    """
    # Asegurarse de que la URL pida un JPG
    # Si la URL ya tiene una extensión de imagen, la reemplazamos con .jpg
    # Si no tiene extensión o si termina en algo como .avif, lo ajustamos
    parsed_url = requests.utils.urlparse(url)
    path_segments = parsed_url.path.split('/')

    # Intenta obtener la última parte del path que podría ser el nombre del archivo
    last_segment = path_segments[-1] if path_segments else ''

    # Buscar la extensión en el último segmento o en los parámetros de la URL
    # Este es un enfoque heurístico, lo más robusto sería una expresión regular
    if '.' in last_segment and last_segment.split('.')[-1].lower() in ['png', 'gif', 'webp', 'avif']:
        # Reemplazar la extensión existente con .jpg
        new_last_segment = last_segment.rsplit('.', 1)[0] + '.jpg'
        path_segments[-1] = new_last_segment
        new_path = '/'.join(path_segments)
    elif not last_segment.endswith('.jpg'):
        # Si no tiene una extensión conocida o no termina en .jpg, añadírsela
        new_path = parsed_url.path + '.jpg'
    else:
        new_path = parsed_url.path  # Ya termina en .jpg o no tiene una extensión fácilmente reconocible

    # Reconstruir la URL con el nuevo path
    adjusted_url = requests.utils.urlunparse(
        parsed_url._replace(path=new_path)
    )

    # Cabeceras User-Agent para simular una petición de navegador Chrome
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
        'Accept': 'image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5'
        # Preferimos JPEG, luego PNG, luego cualquier imagen, luego todo
    }

    for attempt in range(MAX_RETRIES):
        try:
            print(f"  Descargando desde: {adjusted_url} (Intento {attempt + 1}/{MAX_RETRIES})")  # Usamos adjusted_url
            response = requests.get(adjusted_url, timeout=10, stream=True, headers=headers)
            response.raise_for_status()

            image_data_bytes = io.BytesIO(response.content)

            try:
                img = Image.open(image_data_bytes)

                if img.mode in ('RGBA', 'P', 'CMYK'):
                    img = img.convert('RGB')
                elif img.mode == 'LA':
                    img = img.convert('L')

                img.save(destination_path, "jpeg")

                actual_size_bytes = os.path.getsize(destination_path)

                if actual_size_bytes < MIN_SIZE_BYTES:
                    print(
                        f"  Advertencia: La imagen descargada '{os.path.basename(destination_path)}' es muy pequeña ({actual_size_bytes} bytes). Podría no ser una imagen de coche válida.")

                return True, img.size[0], img.size[1], actual_size_bytes

            except Image.UnidentifiedImageError:
                error_msg = f"Pillow no pudo identificar el formato de la imagen descargada de {adjusted_url}. Esto NO DEBERÍA pasar si el servidor devuelve un JPG."
                print(f"  Error: {error_msg}")
                download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
                return False, 0, 0, 0
            except Exception as e_pillow:
                error_msg = f"Error de Pillow al procesar la imagen de {adjusted_url}: {e_pillow}"
                print(f"  Error: {error_msg}")
                download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
                return False, 0, 0, 0

        except requests.exceptions.RequestException as e:
            error_msg = f"Error de red o HTTP al descargar {adjusted_url}: {e}"
            print(f"  Error de descarga (Intento {attempt + 1}/{MAX_RETRIES}): {error_msg}")
            download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
            time.sleep(RETRY_DELAY)
        except Exception as e:
            error_msg = f"Error inesperado durante la descarga inicial de {adjusted_url}: {e}"
            print(f"  Error inesperado (Intento {attempt + 1}/{MAX_RETRIES}): {e}")
            download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
            time.sleep(RETRY_DELAY)

    print(f"Fallo la descarga de {adjusted_url} despues de {MAX_RETRIES} intentos.")
    return False, 0, 0, 0


def process_image_urls(guid_anuncio, urls):
    """
    Procesa una lista de URLs de imagen para un anuncio, descarga y guarda.
    Retorna una lista de diccionarios con la información de las imágenes locales.
    """
    local_images_data = []
    car_image_dir = os.path.join(DOWNLOAD_BASE_DIR, guid_anuncio)
    os.makedirs(car_image_dir, exist_ok=True)

    downloaded_count = 0
    for i, url in enumerate(urls):
        if downloaded_count >= MAX_IMAGE_COUNT_PER_CAR:
            print(f"Límite de {MAX_IMAGE_COUNT_PER_CAR} imágenes alcanzado para el anuncio {guid_anuncio}.")
            break

        local_filename = f"x{i + 1}.jpg"
        local_image_path = os.path.join(car_image_dir, local_filename)

        # Primero, verifica si la imagen ya existe y es válida para evitar descargarla de nuevo
        if os.path.exists(local_image_path) and os.path.getsize(local_image_path) > MIN_SIZE_BYTES:
            try:
                with Image.open(local_image_path) as img:
                    local_images_data.append({
                        "original_url": url,
                        "local_path": local_image_path,
                        "size_bytes": os.path.getsize(local_image_path),
                        "width": img.size[0],
                        "height": img.size[1]
                    })
                    downloaded_count += 1
                    print(
                        f"  Imagen {os.path.basename(local_image_path)} ya existe localmente y es válida. Saltando descarga.")
                    continue
            except Exception as e:
                print(f"  Error al verificar imagen local {local_image_path}: {e}. Intentando descargar de nuevo.")
                if os.path.exists(local_image_path):
                    os.remove(local_image_path)

        success, width, height, size_bytes = safe_download_image(url, local_image_path, guid_anuncio)

        if success:
            global total_images_downloaded_global_counter, total_download_size_bytes_global_counter, \
                total_image_width_global_counter, total_image_height_global_counter

            total_images_downloaded_global_counter.append(1)
            total_download_size_bytes_global_counter.append(size_bytes)
            total_image_width_global_counter.append(width)
            total_image_height_global_counter.append(height)

            local_images_data.append({
                "original_url": url,
                "local_path": local_image_path,
                "size_bytes": size_bytes,
                "width": width,
                "height": height
            })
            downloaded_count += 1
        else:
            print(
                f"No se pudo descargar o procesar la imagen {url} para el anuncio {guid_anuncio}.")  # Aquí seguimos mostrando la URL original
            # en caso de fallo, para depurar.

    return local_images_data


# --- Función principal de procesamiento (resto del código sin cambios) ---
def main():
    global total_cars_processed, successful_cars, failed_cars, images_per_car_counts

    global total_images_downloaded_global_counter
    global total_download_size_bytes_global_counter
    global total_image_width_global_counter
    global total_image_height_global_counter

    total_images_downloaded_global_counter = []
    total_download_size_bytes_global_counter = []
    total_image_width_global_counter = []
    total_image_height_global_counter = []

    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"Error: El archivo CSV no se encuentra en '{CSV_PATH}'")
        return

    processed_listings = []
    print(f"Iniciando procesamiento de {len(df)} anuncios...")

    for index, row in df.iterrows():
        total_cars_processed += 1
        guid_anuncio = str(row['guid_anuncio'])
        image_urls_str = row['url_imagenes']

        if pd.isna(image_urls_str):
            print(f"Anuncio {guid_anuncio}: No hay URLs de imágenes. Saltando.")
            failed_cars += 1
            continue

        image_urls = [url.strip() for url in image_urls_str.split(';') if url.strip()]

        print(f"\n--- Procesando anuncio {guid_anuncio} ({index + 1}/{len(df)}) ---")
        print(f"Encontradas {len(image_urls)} URLs de imágenes.")

        downloaded_images = process_image_urls(guid_anuncio, image_urls)

        if downloaded_images:
            successful_cars += 1
            row_dict = row.to_dict()
            row_dict['downloaded_images'] = downloaded_images
            processed_listings.append(row_dict)
            images_per_car_counts.append(len(downloaded_images))
        else:
            print(f"Anuncio {guid_anuncio}: No se pudo descargar ninguna imagen.")
            failed_cars += 1

    with open(LOCAL_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(processed_listings, f, ensure_ascii=False, indent=4)
    print(f"\nDatos de listings con rutas locales guardados en '{LOCAL_JSON_PATH}'")

    avg_images_per_car = sum(images_per_car_counts) / len(images_per_car_counts) if images_per_car_counts else 0

    total_actual_images_downloaded = len(total_images_downloaded_global_counter)

    avg_total_download_size_bytes = sum(
        total_download_size_bytes_global_counter) / total_actual_images_downloaded if total_actual_images_downloaded else 0
    avg_total_image_width = sum(
        total_image_width_global_counter) / total_actual_images_downloaded if total_actual_images_downloaded else 0
    avg_total_image_height = sum(
        total_image_height_global_counter) / total_actual_images_downloaded if total_actual_images_downloaded else 0

    analysis_results = {
        "fecha_generacion": datetime.now().isoformat(),
        "total_coches_procesados": total_cars_processed,
        "coches_exitosos": successful_cars,
        "coches_fallidos": failed_cars,
        "total_imagenes_descargadas": total_actual_images_downloaded,
        "promedio_imagenes_por_coche": round(avg_images_per_car, 2),
        "promedio_peso_kb": round(avg_total_download_size_bytes / 1024, 2),
        "promedio_dimensiones_px": f"{round(avg_total_image_width)}x{round(avg_total_image_height)}",
        "errores_descarga_por_anuncio": download_errors_by_type,
    }

    with open(ANALYSIS_RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=4)
    print(f"Resultados del análisis guardados en '{ANALYSIS_RESULTS_PATH}'")

    print("\n--- Resumen del Proceso ---")
    print(f"Total coches procesados: {total_cars_processed}")
    print(f"Coches con imágenes descargadas: {successful_cars}")
    print(f"Coches fallidos (sin imágenes/errores): {failed_cars}")
    print(f"Total de imágenes descargadas y procesadas: {total_actual_images_downloaded}")
    print(f"Promedio de peso de imagen: {avg_total_download_size_bytes / 1024:.2f} KB")
    print(f"Promedio de dimensiones de imagen: {round(avg_total_image_width)}x{round(avg_total_image_height)} px")


if __name__ == "__main__":
    main()