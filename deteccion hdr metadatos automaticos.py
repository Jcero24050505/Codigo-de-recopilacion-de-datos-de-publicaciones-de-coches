import cv2
import numpy as np
import piexif
import os
import csv
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed  # ¡NUEVOS IMPORTS!

# --- CONFIGURACIÓN DE RUTAS Y HOJA DE CÁLCULO ---
SPREADSHEET_NAME = 'Hoja 1'
TEMP_DOWNLOAD_FOLDER = 'temp_images'
CREDENTIALS_FILE = '4490LSW/coches-listado-d9ad2cc89ddd.json'

# Columnas en tu hoja de cálculo (base 0)
URL_COLUMN_INDEX = 4  # Columna E es la 4 (0=A, 1=B, ..., 4=E)
RESULT_COLUMN_INDEX = 11  # Columna L es la 11 (0=A, ..., 11=L)

# Google Sheet ID
GOOGLE_SHEET_ID = '1vpbqNSCzVmca4sTj_zLUY4aU7iWrgJtrIG371c3rW_k'

# --- CONFIGURACIÓN PARA REANUDAR Y RANGO DE LECTURA ---
# Define la fila de la hoja de cálculo (base 1) desde donde quieres empezar a procesar datos.
# Si quieres empezar desde la primera fila de datos (después del encabezado), usa 2.
# Si quieres empezar desde la fila 160 de la hoja, usa 160.
START_PROCESSING_FROM_ROW = 2  # <--- ¡AJUSTA ESTE NÚMERO!

# --- CONFIGURACIÓN PARA PROCESAMIENTO PARALELO ---
# Número de descargas y análisis de imágenes concurrentes.
# Un buen punto de partida es 5-10. Experimenta con este valor.
# Demasiado alto podría generar errores por límites de la API o sobrecargar tu red.
MAX_CONCURRENT_IMAGE_PROCESSES = 8


# --- FUNCIONES DE DETECCIÓN HDR (sin cambios, ya optimizadas) ---
def detectar_hdr_en_jpg_ricoh_theta_z1(ruta_imagen):
    """
    Intenta detectar si una imagen JPG tiene características HDR.
    Devuelve si es HDR y la razón de la detección.
    """
    compensacion_exposicion = None
    es_ricoh_z1 = False
    exposure_time = None
    iso_speed = None

    razones_hdr = []
    exif_error_reason = None

    if not os.path.exists(ruta_imagen) or not ruta_imagen.lower().endswith(('.jpg', '.jpeg')):
        return False, None, "No es JPG o archivo no encontrado."

    try:
        exif_dict = piexif.load(ruta_imagen)

        try:
            if "0th" in exif_dict and piexif.ImageIFD.Make in exif_dict["0th"] and piexif.ImageIFD.Model in exif_dict[
                "0th"]:
                make = exif_dict["0th"][piexif.ImageIFD.Make].decode('utf-8', errors='ignore')
                model = exif_dict["0th"][piexif.ImageIFD.Model].decode('utf-8', errors='ignore')
                if "RICOH" in make.upper() and "THETA Z1" in model.upper():
                    es_ricoh_z1 = True
        except Exception as e:
            exif_error_reason = f"Error Make/Model: {e}"

        try:
            if "Exif" in exif_dict and piexif.ExifIFD.ExposureBiasValue in exif_dict["Exif"]:
                num, den = exif_dict["Exif"][piexif.ExifIFD.ExposureBiasValue]
                if den != 0:
                    compensacion_exposicion = num / den
        except Exception as e:
            if exif_error_reason:
                exif_error_reason += f"; ExpBias: {e}"
            else:
                exif_error_reason = f"Error ExpBias: {e}"

        try:
            if "Exif" in exif_dict and piexif.ExifIFD.ExposureTime in exif_dict["Exif"]:
                num, den = exif_dict["Exif"][piexif.ExifIFD.ExposureTime]
                if den != 0:
                    exposure_time = num / den
        except Exception as e:
            if exif_error_reason:
                exif_error_reason += f"; ExpTime: {e}"
            else:
                exif_error_reason = f"Error ExpTime: {e}"

        try:
            if "Exif" in exif_dict and piexif.ExifIFD.ISOSpeedRatings in exif_dict["Exif"]:
                iso_raw = exif_dict["Exif"][piexif.ExifIFD.ISOSpeedRatings]
                if isinstance(iso_raw, tuple) and len(iso_raw) > 0:
                    iso_speed = iso_raw[0]
                elif isinstance(iso_raw, int):
                    iso_speed = iso_raw
        except Exception as e:
            if exif_error_reason:
                exif_error_reason += f"; ISO: {e}"
            else:
                exif_error_reason = f"Error ISO: {e}"

        for ifd_name in ["0th", "Exif", "GPS", "Interop"]:
            if ifd_name in exif_dict:
                for tag, value in exif_dict[ifd_name].items():
                    try:
                        raw_tag_name = piexif.TAGS[ifd_name].get(tag, str(tag))
                        if not isinstance(raw_tag_name, str):
                            tag_name = str(raw_tag_name)
                        else:
                            tag_name = raw_tag_name

                        valor_str = ""
                        if isinstance(value, (bytes, bytearray)):
                            try:
                                valor_str = value.decode('utf-8', errors='ignore')
                            except Exception:
                                valor_str = str(value)
                        elif isinstance(value, (int, float, bool)):
                            valor_str = str(value)
                        elif isinstance(value, (list, tuple)):
                            valor_str = ' '.join(str(x) for x in value)
                        elif isinstance(value, dict):
                            valor_str = str(value)
                        else:
                            valor_str = str(value)

                        valor_str_upper = valor_str.upper()

                        if "HDR" in tag_name.upper() or "HIGH DYNAMIC RANGE" in tag_name.upper():
                            razones_hdr.append(f"Metadato '{tag_name}' contiene 'HDR' en nombre")
                        if "HDR" in valor_str_upper or "HIGH DYNAMIC RANGE" in valor_str_upper:
                            razones_hdr.append(f"Valor de metadato '{tag_name}' contiene 'HDR'")
                        if es_ricoh_z1 and "BRACKET" in tag_name.upper():
                            razones_hdr.append(f"Ricoh Z1: Metadato '{tag_name}' contiene 'BRACKET'")
                        if es_ricoh_z1 and "EXPOSURE PROGRAM" in tag_name.upper() and "HDR" in valor_str_upper:
                            razones_hdr.append(f"Ricoh Z1: 'Exposure Program' indica 'HDR'")
                    except Exception as e:
                        if exif_error_reason:
                            exif_error_reason += f"; Tag {tag}: {e}"
                        else:
                            exif_error_reason = f"Error Tag {tag}: {e}"

    except Exception as e:
        exif_error_reason = f"Error general al cargar EXIF: {e}"

    if exposure_time is not None and iso_speed is not None:
        if exposure_time > 0.5 and iso_speed <= 100:
            razones_hdr.append(f"Heurística: T_Exposicion ({exposure_time:.2f}s) > 0.5 y ISO ({iso_speed}) <= 100")

    if compensacion_exposicion is not None and 0.6 <= compensacion_exposicion <= 0.8:
        razones_hdr.append(f"Compensación de Exposición: {compensacion_exposicion:.2f} (entre 0.6 y 0.8)")

    try:
        img = cv2.imread(ruta_imagen)
        if img is None:
            if not razones_hdr:
                return False, compensacion_exposicion, "No se pudo cargar la imagen con OpenCV." + (
                    f" ({exif_error_reason})" if exif_error_reason else "")
            else:
                return True, compensacion_exposicion, ", ".join(razones_hdr) + (
                    f" (Advertencia: Fallo OpenCV, {exif_error_reason})" if exif_error_reason else "")

        gris_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        hist = cv2.calcHist([gris_img], [0], None, [256], [0, 256])
        hist_norm = hist.ravel() / hist.sum()

        entropia = -np.sum(hist_norm * np.log2(hist_norm + 1e-10))

        total_pixeles = gris_img.size
        pixeles_sombra = np.sum(hist[:int(256 * 0.005)]) / total_pixeles
        pixeles_luces_altas = np.sum(hist[int(256 * 0.995):]) / total_pixeles

        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        canal_saturacion = hsv_img[:, :, 1]
        saturacion_promedio = np.mean(canal_saturacion)

        if entropia > 7.3 and pixeles_sombra < 0.001 and pixeles_luces_altas < 0.001:
            razones_hdr.append(
                f"Análisis imagen: Entropía {entropia:.2f}, Sombras {pixeles_sombra:.4f}%, Luces {pixeles_luces_altas:.4f}% (Criterio 1)")

        if entropia > 6.8 and pixeles_sombra < 0.005 and pixeles_luces_altas < 0.005:
            razones_hdr.append(
                f"Análisis imagen: Entropía {entropia:.2f}, Sombras {pixeles_sombra:.4f}%, Luces {pixeles_luces_altas:.4f}% (Criterio 2)")

        if saturacion_promedio > 160 and entropia > 6.5:
            razones_hdr.append(
                f"Análisis imagen: Saturación {saturacion_promedio:.2f}, Entropía {entropia:.2f} (Criterio 3)")

        if es_ricoh_z1 and iso_speed is not None and iso_speed <= 200 and entropia > 6.0 and pixeles_sombra < 0.01 and pixeles_luces_altas < 0.01:
            razones_hdr.append(
                f"Ricoh Z1 Análisis imagen: Entropía {entropia:.2f}, Sombras {pixeles_sombra:.4f}%, Luces {pixeles_luces_altas:.4f}% (Criterio Ricoh)")

    except Exception as e:
        if not razones_hdr:
            return False, compensacion_exposicion, f"Error en análisis estadístico: {e}" + (
                f" ({exif_error_reason})" if exif_error_reason else "")
        else:
            return True, compensacion_exposicion, ", ".join(razones_hdr) + (
                f" (Advertencia: Fallo OpenCV, {e})" if exif_error_reason else "")

    if razones_hdr:
        return True, compensacion_exposicion, ", ".join(razones_hdr) + (
            f" (Advertencia: Error EXIF previo: {exif_error_reason})" if exif_error_reason else "")

    final_reason = "No HDR según todos los criterios."
    if exif_error_reason:
        final_reason += f" (Detalle EXIF: {exif_error_reason})"
    return False, compensacion_exposicion, final_reason


# --- FUNCIONES DE INTERACCIÓN CON GOOGLE DRIVE Y SHEETS ---

def get_drive_folder_id(drive_url):
    """Extrae el ID de la carpeta de Google Drive de una URL."""
    try:
        if '/folders/' in drive_url:
            return drive_url.split('/folders/')[1].split('?')[0].split('/')[0]
        return None
    except Exception:
        return None


def download_file_from_google_drive(file_id, filename, destination_folder, creds):
    """
    Descarga un archivo desde Google Drive usando el ID del archivo y credenciales de servicio.
    """
    download_url = f'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media'
    headers = {
        'Authorization': f'Bearer {creds.token}'
    }

    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(download_url, headers=headers, stream=True)
            response.raise_for_status()

            file_path = os.path.join(destination_folder, filename)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return file_path
        except requests.exceptions.RequestException as e:
            print(f"    Error descargando '{filename}' (ID: {file_id}), intento {attempt + 1}/{retries}: {e}")
            if e.response is not None and e.response.status_code == 403:
                print(
                    "    Error 403: Permiso denegado. Asegúrate de que la cuenta de servicio tenga acceso al archivo/carpeta de Drive.")
                return None
            time.sleep(1 + attempt)
        except Exception as e:
            print(f"    Error inesperado al descargar '{filename}': {e}")
            return None
    print(f"    Falló la descarga de '{filename}' después de {retries} intentos.")
    return None


def list_files_in_drive_folder(folder_id, drive_service):
    """
    Lista archivos JPG/PNG en una carpeta de Google Drive usando el servicio ya autenticado.
    """
    files_info = []
    page_token = None

    q_query = f"'{folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png') and trashed=false"

    while True:
        try:
            results = drive_service.files().list(
                q=q_query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token
            ).execute()

            items = results.get('files', [])
            for item in items:
                if 'mimeType' in item and (item['mimeType'] == 'image/jpeg' or item['mimeType'] == 'image/png'):
                    files_info.append({'id': item['id'], 'name': item['name']})

            page_token = results.get('nextPageToken', None)
            if not page_token:
                break
        except HttpError as error:
            print(f'Ocurrió un error al listar archivos en la carpeta {folder_id}: {error}')
            if error.resp.status == 403:
                print(
                    "Error 403: Permiso denegado. Asegúrate de que la cuenta de servicio tenga acceso a la carpeta de Drive.")
            break
        except Exception as e:
            print(f"Error inesperado al listar archivos: {e}")
            break
    return files_info


# --- NUEVA FUNCIÓN PARA PROCESAR UNA ÚNICA IMAGEN EN PARALELO ---
def process_single_image_task(file_info, folder_id, temp_folder, creds, detector_func):
    """
    Descarga y analiza una única imagen, devuelve si es HDR y la ruta para limpieza.
    Esta función se ejecutará en un hilo separado.
    """
    file_id = file_info['id']
    file_name_original = file_info['name']

    # Asegurarse de que el nombre de archivo temporal sea único para evitar colisiones entre hilos
    temp_filename = f"drive_img_{folder_id}_{file_id}_{file_name_original}"
    downloaded_path = None  # Inicializar a None

    try:
        downloaded_path = download_file_from_google_drive(file_id, temp_filename, temp_folder, creds)

        if downloaded_path:
            es_hdr, _, razon = detector_func(downloaded_path)
            # print(f"        Procesado: '{file_name_original}' -> HDR={es_hdr}") # Comentado para reducir verbosidad
            return es_hdr, downloaded_path  # Devolver el resultado y la ruta para limpieza
        else:
            # print(f"        No se pudo descargar '{file_name_original}'.") # Comentado para reducir verbosidad
            return None, None  # Indicar que no se pudo procesar
    except Exception as e:
        print(f"        Error inesperado al procesar imagen '{file_name_original}': {e}")
        return None, downloaded_path  # Devolver None en caso de error, y la ruta si se llegó a descargar para limpieza
    finally:
        # Asegurarse de que el archivo temporal se elimine, incluso si hay un error en el análisis
        if downloaded_path and os.path.exists(downloaded_path):
            try:
                os.remove(downloaded_path)
            except Exception as e:
                print(f"        Error al eliminar archivo temporal '{downloaded_path}': {e}")


def main():
    if not os.path.exists(TEMP_DOWNLOAD_FOLDER):
        os.makedirs(TEMP_DOWNLOAD_FOLDER)

    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
        gc = gspread.authorize(creds)

        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet(SPREADSHEET_NAME)

        drive_service = build('drive', 'v3', credentials=creds)

    except Exception as e:
        print(f"Error crítico al autenticarse o inicializar APIs: {e}")
        print(
            "Asegúrate de que el archivo de credenciales existe, la cuenta de servicio tiene acceso al Google Sheet y a las carpetas de Drive, y y el nombre de la hoja es correcto.")
        return

    print(f"\n--- Iniciando análisis de URLs de CARPETAS en Google Sheet '{SPREADSHEET_NAME}' ---")

    # --- Manejo del encabezado y rango de lectura ---
    # Actualizar encabezado de la columna L si está vacío
    try:
        header_cell_value = worksheet.cell(1, RESULT_COLUMN_INDEX + 1).value
        if not header_cell_value or header_cell_value.strip() == '':
            worksheet.update_cell(1, RESULT_COLUMN_INDEX + 1, "Estado HDR (Carpeta)")
            print("Encabezado de columna L actualizado.")
    except Exception as e:
        print(f"Error al verificar/actualizar encabezado de columna L: {e}")

    # Obtener el número total de filas en la hoja (para saber hasta dónde leer)
    total_rows = worksheet.row_count

    # Definir el rango de lectura. Empezamos desde START_PROCESSING_FROM_ROW
    # hasta la última fila que contiene datos en la hoja.
    def get_column_letter(col_idx):
        if col_idx < 0: return ""
        result = ""
        while col_idx >= 0:
            result = chr(65 + col_idx % 26) + result
            col_idx = col_idx // 26 - 1
        return result

    end_column_letter = get_column_letter(URL_COLUMN_INDEX)

    range_to_fetch = f'A{START_PROCESSING_FROM_ROW}:{end_column_letter}{total_rows}'  # Asegura que se lee hasta la última fila de datos

    print(
        f"\nObteniendo datos desde la fila {START_PROCESSING_FROM_ROW} hasta la {total_rows} en el rango: {range_to_fetch}")

    fetched_rows_data = []
    try:
        fetched_rows_data = worksheet.get_values(range_to_fetch)
        if not fetched_rows_data:
            print(
                f"No se encontraron datos para procesar en el rango {range_to_fetch}. Posiblemente ya todo procesado o rango incorrecto.")
            return
    except Exception as e:
        print(f"Error al obtener las filas de la hoja de cálculo desde el rango {range_to_fetch}: {e}")
        print("Asegúrate de que el rango es válido y hay datos en esas filas.")
        return

    print(f"\n--- Iniciando análisis de URLs de CARPETAS ---")

    # Iterar sobre las filas obtenidas.
    # local_idx es el índice dentro del array fetched_rows_data (0, 1, 2...)
    # current_sheet_row_number es el número real de la fila en la hoja de cálculo (base 1).
    for local_idx, row_data in enumerate(fetched_rows_data):
        current_sheet_row_number = START_PROCESSING_FROM_ROW + local_idx

        # Asegurarse de que la fila tenga suficientes columnas para acceder a la URL_COLUMN_INDEX.
        if not row_data or len(row_data) <= URL_COLUMN_INDEX:
            folder_url = ""
        else:
            folder_url = row_data[URL_COLUMN_INDEX].strip()

        result_summary = ""

        if not folder_url:
            result_summary = "Sin URL de Carpeta"
            print(f"Fila {current_sheet_row_number}: {result_summary}. Omitiendo análisis.")
        else:
            print(f"\nFila {current_sheet_row_number}: Procesando URL de Carpeta: {folder_url}")
            folder_id = get_drive_folder_id(folder_url)

            if not folder_id:
                result_summary = "Error: ID de Carpeta de Drive no encontrado en la URL."
                print(result_summary)
            else:
                files_in_folder = list_files_in_drive_folder(folder_id, drive_service)

                if not files_in_folder:
                    result_summary = "Carpeta vacía o no contiene JPGs/PNGs."
                    print(f"  {result_summary}")
                else:
                    hdr_count = 0
                    no_hdr_count = 0
                    total_processed = 0

                    print(
                        f"  Encontradas {len(files_in_folder)} imágenes en la carpeta. Procesando en paralelo con {MAX_CONCURRENT_IMAGE_PROCESSES} workers...")

                    # --- Implementación del procesamiento paralelo aquí ---
                    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_IMAGE_PROCESSES) as executor:
                        futures = []
                        for file_info in files_in_folder:
                            # Submit la tarea de procesamiento de cada imagen al executor
                            futures.append(executor.submit(
                                process_single_image_task,
                                file_info,
                                folder_id,
                                TEMP_DOWNLOAD_FOLDER,
                                creds,  # Se pasan las credenciales para la descarga
                                detectar_hdr_en_jpg_ricoh_theta_z1
                            ))

                        # Recoger los resultados a medida que las tareas se completan
                        for future in as_completed(futures):
                            es_hdr_result, _ = future.result()  # _ es la ruta, que ya se limpió en la tarea

                            if es_hdr_result is not None:  # Si la tarea se intentó y devolvió un resultado
                                if es_hdr_result:
                                    hdr_count += 1
                                else:
                                    no_hdr_count += 1
                                total_processed += 1
                            # else: # Esto indicaría que la descarga o el análisis falló para esa imagen
                            # print(f"        Una imagen no pudo ser procesada en el hilo.") # Esto se maneja en la función de tarea

                    if total_processed == 0:
                        result_summary = "Carpeta: No se procesaron imágenes válidas."
                    elif hdr_count > 0 and no_hdr_count > 0:
                        result_summary = f"Carpeta: {hdr_count} HDR, {no_hdr_count} No HDR"
                    elif hdr_count > 0:
                        result_summary = f"Carpeta: TODAS HDR ({hdr_count} imágenes)"
                    else:  # no_hdr_count > 0 y hdr_count == 0
                        result_summary = f"Carpeta: TODAS NO HDR ({no_hdr_count} imágenes)"

                    print(f"  Resumen para carpeta: {result_summary}")

        try:
            worksheet.update_cell(current_sheet_row_number, RESULT_COLUMN_INDEX + 1, result_summary)
            print(f"  Sheet actualizado para Fila {current_sheet_row_number}.")
        except Exception as e:
            print(f"  Error al actualizar Sheet para Fila {current_sheet_row_number}: {e}")

    print("\n--- Proceso de análisis de carpetas completado ---")

    # La limpieza de archivos temporales se hace ahora en process_single_image_task
    # pero aseguramos que la carpeta en sí se elimine al final si está vacía.
    if os.path.exists(TEMP_DOWNLOAD_FOLDER):
        if not os.listdir(TEMP_DOWNLOAD_FOLDER):  # Si la carpeta está vacía
            os.rmdir(TEMP_DOWNLOAD_FOLDER)
            print(f"Carpeta temporal '{TEMP_DOWNLOAD_FOLDER}' eliminada.")
        else:
            print(
                f"Advertencia: La carpeta temporal '{TEMP_DOWNLOAD_FOLDER}' no está vacía al final del script. Contiene archivos residuales.")


if __name__ == "__main__":
    main()