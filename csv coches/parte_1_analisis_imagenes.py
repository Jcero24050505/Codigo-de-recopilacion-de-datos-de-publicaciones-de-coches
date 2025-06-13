import pandas as pd
import requests
import os
import json
from PIL import Image  # Importar la clase Image de Pillow
import io
import time
from datetime import datetime
import subprocess  # Para llamar a ImageMagick
import math

# --- Configuración ---
CSV_PATH = "C:\\Users\\CERO\\Desktop\\csv coches\\listings.csv"
DOWNLOAD_BASE_DIR = "C:\\Users\\CERO\\Desktop\\csv coches\\imagenes_coches_descargadas"
LOCAL_JSON_PATH = "C:\\Users\\CERO\\Desktop\\csv coches\\listings_with_local_data.json"
ANALYSIS_RESULTS_PATH = "C:\\Users\\CERO\\Desktop\\csv coches\\analysis_results.json"
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos
MAX_IMAGE_COUNT_PER_CAR = 25  # Límite de imágenes por coche
MIN_SIZE_BYTES = 5000  # Tamaño mínimo en bytes para considerar la imagen válida

# --- Inicialización de métricas para el análisis ---
total_cars_processed = 0
total_images_downloaded = 0
total_download_size_bytes = 0
total_image_width = 0
total_image_height = 0
successful_cars = 0
failed_cars = 0
images_per_car_counts = []  # Para calcular el promedio de imágenes por coche
image_dimensions_by_car = {}  # Para almacenar dimensiones por coche
image_sizes_by_car = {}  # Para almacenar tamaños por coche
download_errors_by_type = {}  # Para categorizar errores de descarga


def safe_download_image(url, destination_path, guid_anuncio):
    """
    Descarga una imagen de forma segura, con reintentos.
    Si Pillow no puede identificarla, intenta convertirla con ImageMagick.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Lanza un error para códigos de estado HTTP 4xx/5xx
            image_data = io.BytesIO(response.content)

            # --- Intentar con Pillow primero ---
            try:
                img = Image.open(image_data)
                img_format = img.format  # Obtener formato de la imagen
                # Si es AVIF, Pillow puede abrirlo, pero a veces con advertencias.
                # Asegúrate de que no haya habido advertencias que te impidan usarla.
                # Si el formato es AVIF y decidimos no usar pillow-heif, podríamos forzar ImageMagick aquí.
                # Pero si Pillow ya lo abre, y la advertencia no causa un error fatal, está bien.
                # Sin embargo, hemos visto que AVIF con Pillow es problemático para ti.

                # Si es AVIF, o si el formato es desconocido por Pillow de alguna forma,
                # o si la imagen tiene un tamaño muy pequeño (podría ser un placeholder/error)
                if img.format == 'AVIF' or len(response.content) < MIN_SIZE_BYTES:
                    raise IOError(f"Pillow no pudo identificar completamente AVIF o imagen pequeña.")

                # Guardar como JPEG si Pillow lo abrió bien
                img.convert("RGB").save(destination_path, "jpeg")
                return True, img.size[0], img.size[1], len(response.content)  # width, height, size_bytes

            except (IOError, SyntaxError) as e:
                # Si Pillow falla (incluyendo AVIF problemático), intentamos con ImageMagick
                print(f"Pillow no pudo identificar {os.path.basename(destination_path)}. Intentando con ImageMagick...")
                # Guardar el contenido original temporalmente para ImageMagick
                temp_input_path = destination_path + "_temp_download"
                with open(temp_input_path, 'wb') as temp_f:
                    temp_f.write(response.content)

                # Intentar convertir con ImageMagick
                # 'magick convert' convierte el archivo a JPG
                try:
                    # Usamos -quality 85 para buena compresión y calidad aceptable
                    subprocess.run(['magick', 'convert', temp_input_path, destination_path],
                                   check=True,  # Lanza un error si el comando falla
                                   capture_output=True, text=True)
                    print(
                        f"ImageMagick convirtió '{os.path.basename(temp_input_path)}' a '{os.path.basename(destination_path)}'")

                    # Ahora, abrir el JPG convertido con Pillow para obtener sus propiedades
                    converted_img = Image.open(destination_path)
                    os.remove(temp_input_path)  # Limpiar archivo temporal
                    return True, converted_img.size[0], converted_img.size[1], os.path.getsize(destination_path)

                except subprocess.CalledProcessError as sub_e:
                    error_msg = f"ImageMagick falló para {url} ({sub_e.stderr.strip()})"
                    print(f"Error: {error_msg}")
                    download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
                    if os.path.exists(temp_input_path):
                        os.remove(temp_input_path)
                    return False, 0, 0, 0
                except Exception as ex:
                    error_msg = f"Error inesperado al procesar con ImageMagick: {ex}"
                    print(f"Error: {error_msg}")
                    download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
                    if os.path.exists(temp_input_path):
                        os.remove(temp_input_path)
                    return False, 0, 0, 0

        except requests.exceptions.RequestException as e:
            error_msg = f"Error de red o HTTP al descargar {url}: {e}"
            print(f"Error de descarga (Intento {attempt + 1}/{MAX_RETRIES}): {error_msg}")
            download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
            time.sleep(RETRY_DELAY)
        except Exception as e:
            error_msg = f"Error inesperado al descargar {url}: {e}"
            print(f"Error inesperado (Intento {attempt + 1}/{MAX_RETRIES}): {error_msg}")
            download_errors_by_type[guid_anuncio] = download_errors_by_type.get(guid_anuncio, []) + [error_msg]
            time.sleep(RETRY_DELAY)

    print(f"Fallo la descarga de {url} despues de {MAX_RETRIES} intentos.")
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

        # Intentar extraer la extensión original o usar .jpg por defecto
        # filename = os.path.basename(url).split('?')[0] # Eliminar parámetros de URL
        # if '.' not in filename or filename.split('.')[-1] not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'avif']:
        #    filename = f"x{i+1}.jpg" # Nombre genérico si no hay extensión válida
        # else:
        #    filename = f"x{i+1}_{filename}" # Añadir prefijo para asegurar unicidad y orden

        # Simplificar el nombre del archivo local a x01.jpg, x02.jpg, etc.
        local_filename = f"x{i + 1}.jpg"
        local_image_path = os.path.join(car_image_dir, local_filename)

        print(f"Descargando desde: {url} (Intento 1/{MAX_RETRIES})")
        success, width, height, size_bytes = safe_download_image(url, local_image_path, guid_anuncio)

        if success:
            total_images_downloaded_global_counter.append(1)  # Usar contador global para las métricas
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
            print(f"No se pudo descargar la imagen {url} para el anuncio {guid_anuncio}.")

    return local_images_data


# --- Función principal de procesamiento ---
def main():
    global total_cars_processed, successful_cars, failed_cars, images_per_car_counts

    # Listas globales para acumular métricas
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
        guid_anuncio = row['guid_anuncio']
        image_urls_str = row['url_imagenes']

        if pd.isna(image_urls_str):
            print(f"Anuncio {guid_anuncio}: No hay URLs de imágenes. Saltando.")
            failed_cars += 1
            continue

        # Las URLs están separadas por comas en el CSV
        image_urls = [url.strip() for url in image_urls_str.split(',') if url.strip()]

        print(f"\n--- Procesando anuncio {guid_anuncio} ({index + 1}/{len(df)}) ---")
        print(f"Encontradas {len(image_urls)} URLs de imágenes.")

        downloaded_images = process_image_urls(guid_anuncio, image_urls)

        if downloaded_images:
            successful_cars += 1
            # Añadir las imágenes descargadas al diccionario del listing
            row_dict = row.to_dict()
            row_dict['downloaded_images'] = downloaded_images
            processed_listings.append(row_dict)
            images_per_car_counts.append(len(downloaded_images))
        else:
            print(f"Anuncio {guid_anuncio}: No se pudo descargar ninguna imagen.")
            failed_cars += 1

    # --- Guardar los datos de listings procesados ---
    with open(LOCAL_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(processed_listings, f, ensure_ascii=False, indent=4)
    print(f"\nDatos de listings con rutas locales guardados en '{LOCAL_JSON_PATH}'")

    # --- Calcular y guardar resultados del análisis ---
    avg_images_per_car = sum(images_per_car_counts) / len(images_per_car_counts) if images_per_car_counts else 0

    # Calcular promedios globales de las imágenes descargadas
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
        "promedio_peso_kb": round(avg_total_download_size_bytes / 1024, 2),  # Convertir a KB
        "promedio_dimensiones_px": f"{round(avg_total_image_width)}x{round(avg_total_image_height)}",
        "errores_descarga_por_anuncio": download_errors_by_type,
        # Puedes añadir más métricas aquí si las necesitas, por ejemplo, rangos de precios, km, etc.
    }

    with open(ANALYSIS_RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=4)
    print(f"Resultados del análisis guardados en '{ANALYSIS_RESULTS_PATH}'")

    print("\n--- Resumen del Proceso ---")
    print(f"Total coches procesados: {total_cars_processed}")
    print(f"Coches con imágenes descargadas: {successful_cars}")
    print(f"Coches fallidos (sin imágenes/errores): {failed_cars}")
    print(f"Total de imágenes descargadas y procesadas: {total_actual_images_downloaded}")
    print(f"Promedio de imágenes por coche: {avg_images_per_car:.2f}")
    print(f"Promedio de peso de imagen: {avg_total_download_size_bytes / 1024:.2f} KB")
    print(f"Promedio de dimensiones de imagen: {round(avg_total_image_width)}x{round(avg_total_image_height)} px")


if __name__ == "__main__":
    main()