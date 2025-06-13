from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import json
import re  # Para expresiones regulares en parse_numeric_value
import numpy as np  # Necesario para np.isnan, np.isinf

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas las rutas

# --- Configuración de rutas y archivos ---
# BASE_PROJECT_PATH debe apuntar a la raíz de tu proyecto (donde está .venv, etc.)
# Si tu server_api.py está en 'PythonProject1/csv coches/', entonces la base es 'PythonProject1'
BASE_PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DATA_DIR = os.path.join(BASE_PROJECT_PATH, 'csv coches')

LISTINGS_DATA_FILE = os.path.join(CSV_DATA_DIR, 'listings_with_local_data.json')
ANALYSIS_RESULTS_FILE = os.path.join(CSV_DATA_DIR, 'analysis_results.json')
DOWNLOAD_DIR_FULL_PATH = os.path.join(CSV_DATA_DIR, 'imagenes_coches_descargadas')

# --- Verificación de existencia de archivos/directorios al inicio ---
print(f"DEBUG: BASE_PROJECT_PATH: {BASE_PROJECT_PATH}")
print(f"DEBUG: CSV_DATA_DIR: {CSV_DATA_DIR}")
print(f"DEBUG: LISTINGS_DATA_FILE: {LISTINGS_DATA_FILE}")
print(f"DEBUG: ANALYSIS_RESULTS_FILE: {ANALYSIS_RESULTS_FILE}")
print(f"DEBUG: DOWNLOAD_DIR_FULL_PATH: {DOWNLOAD_DIR_FULL_PATH}")

print(f"DEBUG: ¿Existe LISTINGS_DATA_FILE?: {os.path.exists(LISTINGS_DATA_FILE)}")
print(f"DEBUG: ¿Existe ANALYSIS_RESULTS_FILE?: {os.path.exists(ANALYSIS_RESULTS_FILE)}")  # Corregido
print(f"DEBUG: ¿Existe DOWNLOAD_DIR_FULL_PATH?: {os.path.isdir(DOWNLOAD_DIR_FULL_PATH)}")

# --- Carga de datos global ---
listings_data = []
analysis_results = {}
listings_by_guid = {}  # Un diccionario para acceso rápido por GUID (se llenará en load_data)


def load_data():
    global listings_data, analysis_results, listings_by_guid
    try:
        if os.path.exists(LISTINGS_DATA_FILE):
            with open(LISTINGS_DATA_FILE, 'r', encoding='utf-8') as f:
                raw_listings = json.load(f)
                # Limpiar NaN/Infinity durante la carga inicial del JSON si fuera necesario (doble seguridad)
                listings_data = []
                for item in raw_listings:
                    cleaned_item = {}
                    for key, value in item.items():
                        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                            cleaned_item[key] = None
                        else:
                            cleaned_item[key] = value
                    listings_data.append(cleaned_item)

            listings_by_guid = {listing.get('guid_anuncio'): listing for listing in listings_data if
                                listing.get('guid_anuncio')}
            print(f"Datos de listings cargados desde '{LISTINGS_DATA_FILE}'. Total: {len(listings_data)} anuncios.")
        else:
            print(f"Advertencia: El archivo '{LISTINGS_DATA_FILE}' no se encontró. Los listados estarán vacíos.")

        if os.path.exists(ANALYSIS_RESULTS_FILE):
            with open(ANALYSIS_RESULTS_FILE, 'r', encoding='utf-8') as f:
                analysis_results_raw = json.load(f)
                # Limpiar NaN/Infinity para los resultados de análisis
                analysis_results.clear()  # Limpiar el diccionario global antes de rellenar
                for key, value in analysis_results_raw.items():
                    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                        analysis_results[key] = None
                    else:
                        analysis_results[key] = value
            print(f"Resultados del análisis cargados desde '{ANALYSIS_RESULTS_FILE}'.")
            print(f"DEBUG: Contenido de analysis_results después de la carga: {analysis_results}")  # Debug print
        else:
            print(
                f"Advertencia: El archivo '{ANALYSIS_RESULTS_FILE}' no se encontró. Los resultados del análisis estarán vacíos.")

    except json.JSONDecodeError as e:
        print(
            f"ERROR: No se pudo decodificar el archivo JSON. Revisa la sintaxis del JSON y los literales NaN/Infinity. Error: {e}")
        listings_data = []  # Vaciar para evitar errores posteriores
        analysis_results = {}
        listings_by_guid = {}
    except Exception as e:
        print(f"ERROR: Ocurrió un error al cargar los datos: {e}")
        listings_data = []
        analysis_results = {}
        listings_by_guid = {}


# Cargar datos al iniciar el servidor
load_data()


# --- Función auxiliar para manejar valores numéricos y "N/A" ---
def parse_numeric_value(value, value_type=float):
    """
    Intenta convertir un valor a numérico, manejando "N/A", vacíos, y formatos de moneda.
    Devuelve None si no es numérico o se limpia a una cadena vacía.
    """
    if value is None:
        return None

    if isinstance(value, str):
        cleaned_value = value.strip().upper()
        if cleaned_value == "N/A" or cleaned_value == "":
            return None  # Si es N/A o vacío, devolver None (se convierte a null en JSON)

        # Si no es N/A ni vacío, intentar limpiar para numérico
        cleaned_value = value.replace('\u20ac', '').replace('€', '').strip()

        # Manejar comas como separadores decimales si el formato es europeo (ej: "1.234,56")
        if ',' in cleaned_value and '.' in cleaned_value and cleaned_value.rfind(',') > cleaned_value.rfind('.'):
            cleaned_value = cleaned_value.replace('.', '').replace(',', '.')
        elif ',' in cleaned_value:
            cleaned_value = cleaned_value.replace(',', '.')
        else:
            cleaned_value = cleaned_value.replace('.',
                                                  '')  # Eliminar solo puntos, asumiendo que son separadores de miles

        # Validar que después de la limpieza, solo queden dígitos y un posible punto decimal.
        # La regex permite números negativos y decimales.
        if not re.match(r"^-?\d+(\.\d+)?$", cleaned_value):
            return None  # Si no se parece a un número, devolver None

        # Si la cadena resultante está vacía después de la limpieza, también es None
        if not cleaned_value:
            return None

        value = cleaned_value

    # Intentar la conversión final
    try:
        return value_type(value)
    except (ValueError, TypeError):
        return None


# --- Rutas de la API ---

@app.route('/')
def home():
    """
    Ruta de inicio para verificar que el servidor está funcionando.
    No devuelve HTML para la aplicación, solo un mensaje de estado.
    """
    return jsonify({"message": "API de Coches funcionando. Accede a /api/listings para los datos."})


@app.route('/api/listings', methods=['GET'])
def get_listings():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)

    if not listings_data:
        return jsonify({"error": "No listings data available on server"}), 500

    start_index = (page - 1) * limit
    end_index = start_index + limit

    paginated_raw_listings = listings_data[start_index:end_index]

    total_listings = len(listings_data)

    processed_listings_for_frontend = []
    for raw_listing in paginated_raw_listings:
        # Construye un nuevo diccionario con solo las claves esperadas por el frontend
        processed_listing = {
            "guid_anuncio": raw_listing.get("guid_anuncio"),
            "marca": raw_listing.get("Marca"),  # Usa la clave original del CSV
            "modelo": raw_listing.get("Modelo"),  # Usa la clave original del CSV
            "precio": parse_numeric_value(raw_listing.get("Precio Contado")),  # Usa la clave original del CSV
            "kilometros": parse_numeric_value(raw_listing.get("Kilómetros")),  # Usa la clave original del CSV
            "año": parse_numeric_value(raw_listing.get("Año Matriculación"), int),  # Usa la clave original del CSV
            "concesionario": raw_listing.get("Concesionario"),  # Usa la clave original del CSV
            "tours_url": raw_listing.get("Tours"),  # Asegúrate de que 'Tours' es el nombre de la clave en tu JSON
            "thumbnail_url": None  # Se llenará a continuación
        }

        # --- Lógica para la thumbnail_url ---
        # Verificamos si 'downloaded_images' es una lista no vacía
        if isinstance(raw_listing.get('downloaded_images'), list) and raw_listing['downloaded_images']:
            first_image_info = raw_listing['downloaded_images'][0]
            # Asegúrate de que first_image_info es un diccionario y contiene 'local_path'
            if isinstance(first_image_info, dict) and 'local_path' in first_image_info:
                image_filename = os.path.basename(first_image_info['local_path'])
                processed_listing['thumbnail_url'] = f"/api/images/{processed_listing['guid_anuncio']}/{image_filename}"
            # else: no se asigna thumbnail_url, se queda como None

        # Limpiar tours_url si es "N/A" o vacío
        if isinstance(processed_listing.get('tours_url'), str) and (
                processed_listing['tours_url'].strip().upper() == "N/A" or processed_listing[
            'tours_url'].strip() == ""):
            processed_listing['tours_url'] = None

        processed_listings_for_frontend.append(processed_listing)
        print(
            f"DEBUG: Listing procesado para frontend (ejemplo thumbnail_url): {processed_listing.get('thumbnail_url')}")  # Debug print

    response_data = {
        "listings": processed_listings_for_frontend,
        "page": page,
        "limit": limit,
        "total_listings": total_listings
    }

    return jsonify(response_data)


@app.route('/api/listings/<guid>', methods=['GET'])
def get_listing_by_guid(guid):
    # Encuentra el anuncio por GUID
    raw_listing = next((item for item in listings_data if item.get("guid_anuncio") == guid), None)

    if not raw_listing:
        return jsonify({"error": "Listing not found"}), 404

    # Construye un nuevo diccionario con todas las claves esperadas por el modal de detalles
    processed_listing = {
        "guid_anuncio": raw_listing.get("guid_anuncio"),
        "marca": raw_listing.get("Marca"),
        "modelo": raw_listing.get("Modelo"),
        "precio": parse_numeric_value(raw_listing.get("Precio Contado")),
        "precio_financiado_display": parse_numeric_value(raw_listing.get("Precio Financiado")),
        "año": parse_numeric_value(raw_listing.get("Año Matriculación"), int),
        "kilometros": parse_numeric_value(raw_listing.get("Kilómetros")),
        "puertas": parse_numeric_value(raw_listing.get("Puertas"), int),
        "concesionario": raw_listing.get("Concesionario"),
        "tipo_de_motor": raw_listing.get("Tipo Combustible"),
        "cambio": raw_listing.get("Transmisión"),
        "localidad": raw_listing.get("Ubicación Concesionario"),
        "provincia": raw_listing.get("Provincia", "N/A"),  # Asume que puede existir o usa N/A
        "tipo_de_anuncio": raw_listing.get("Tipo de Anuncio", "Coche de ocasión"),
        # Asume que puede existir o usa por defecto
        "clase_de_vehículo": raw_listing.get("Clase de Vehículo", "Turismo"),
        # Asume que puede existir o usa por defecto
        "combustible": raw_listing.get("Tipo Combustible"),
        "carrocería": raw_listing.get("Carrocería"),
        "garantia": raw_listing.get("Garantía Oficial"),
        "descripción": raw_listing.get("Descripción"),
        "url_anuncio": raw_listing.get("URL Anuncio"),
        "tours_url": raw_listing.get("Tours"),  # Asegúrate de que 'Tours' es el nombre de la clave
        "images": []  # Se llenará a continuación
    }

    # Limpiar campos de texto específicos que pueden ser "N/A"
    for key in ["garantia", "descripción", "url_anuncio", "provincia", "tipo_de_anuncio", "clase_de_vehículo",
                "carrocería", "combustible", "tipo_de_motor", "cambio", "localidad", "concesionario"]:
        current_value = processed_listing.get(key)
        if isinstance(current_value, str) and (current_value.strip().upper() == "N/A" or current_value.strip() == ""):
            processed_listing[key] = "N/A"
        # else: mantener el valor original, ya sea cadena o None

    # Limpiar tours_url si es "N/A" o vacío
    if isinstance(processed_listing.get('tours_url'), str) and (
            processed_listing['tours_url'].strip().upper() == "N/A" or processed_listing['tours_url'].strip() == ""):
        processed_listing['tours_url'] = None

    # Formatear URLs para las imágenes del detalle del coche (para el carrusel)
    if 'downloaded_images' in raw_listing and isinstance(raw_listing['downloaded_images'], list) and raw_listing[
        'downloaded_images']:
        for img_info in raw_listing['downloaded_images']:
            if isinstance(img_info, dict) and 'local_path' in img_info:
                image_filename = os.path.basename(img_info['local_path'])
                processed_listing['images'].append({
                    "api_image_url": f"/api/images/{guid}/{image_filename}",
                })

    return jsonify(processed_listing)


@app.route('/api/images/<guid>/<filename>')
def get_image(guid, filename):
    image_dir = os.path.join(DOWNLOAD_DIR_FULL_PATH, guid)

    print(f"DEBUG: Solicitud de imagen para GUID: {guid}, Archivo: {filename}")
    print(f"DEBUG: Directorio de imagen esperado: {image_dir}")
    print(f"DEBUG: Ruta completa del archivo esperado: {os.path.join(image_dir, filename)}")

    if not os.path.isdir(image_dir):
        print(f"ERROR: Directorio de imágenes no encontrado: {image_dir}")
        return "Directory not found", 404

    if not os.path.exists(os.path.join(image_dir, filename)):
        print(f"ERROR: Archivo de imagen no encontrado: {os.path.join(image_dir, filename)}")
        return "Image not found", 404

    return send_from_directory(image_dir, filename)


@app.route('/api/analysis', methods=['GET'])
def get_analysis_results():
    print(f"DEBUG: Sirviendo resultados del análisis. Contenido actual: {analysis_results}")  # Debug print

    # Mapear las claves internas del análisis a las claves esperadas por el frontend
    # Usar .get() con un valor por defecto si la clave no existe en analysis_results
    total_images_processed = analysis_results.get('total_imagenes_descargadas', 'N/A')
    promedio_peso_kb = analysis_results.get('promedio_peso_kb', 'N/A')
    promedio_dimensiones_px = analysis_results.get('promedio_dimensiones_px', 'N/A')

    # Convertir a None si es un número (ej. 0.0) que no queremos mostrar como "N/A" por un error previo
    if isinstance(total_images_processed, (int, float)) and (
            total_images_processed == 0 or np.isnan(total_images_processed)):
        total_images_processed = 'N/A'
    if isinstance(promedio_peso_kb, (int, float)) and (promedio_peso_kb == 0 or np.isnan(promedio_peso_kb)):
        promedio_peso_kb = 'N/A'
    if isinstance(promedio_dimensiones_px, str) and (
            promedio_dimensiones_px.strip().upper() == "N/A" or promedio_dimensiones_px.strip() == ""):
        promedio_dimensiones_px = 'N/A'

    response_data = {
        "Total Imágenes Procesadas": total_images_processed,
        "Promedio Peso (KB)": promedio_peso_kb,
        "Promedio Dimensiones (px)": promedio_dimensiones_px
    }

    return jsonify(response_data)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
