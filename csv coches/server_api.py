import os
import json
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS  # Para permitir solicitudes desde el cliente web

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas las rutas

# --- Configuración ---
# Rutas a los archivos JSON generados por parte_1_analisis_imagenes.py
# Estos archivos se encuentran en la carpeta raíz del proyecto (C:\Users\CERO\Desktop\csv coches)
LISTINGS_DATA_FILE = "listings_with_local_data.json"
ANALYSIS_RESULTS_FILE = "analysis_results.json"
# Directorio donde se descargaron las imágenes
# Este es el nuevo nombre de la carpeta y se encuentra en la carpeta raíz del proyecto
DOWNLOAD_DIR = "imagenes_coches_descargadas"  # ¡CORRECCIÓN AQUÍ!

# Datos cargados una vez al iniciar el servidor
listings_data = {}
analysis_results = {}
listings_by_guid = {}  # Un diccionario para acceso rápido por GUID


def load_data():
    """
    Carga los datos de los listings y los resultados del análisis
    desde los archivos JSON.
    """
    global listings_data, analysis_results, listings_by_guid

    # Cargar datos de listings
    if os.path.exists(LISTINGS_DATA_FILE):
        with open(LISTINGS_DATA_FILE, 'r', encoding='utf-8') as f:
            listings_data = json.load(f)
        # Crear un mapeo GUID -> listing para acceso rápido
        # Usamos 'guid_anuncio' que es el nombre de la columna en tu CSV
        listings_by_guid = {listing['guid_anuncio']: listing for listing in listings_data}
        print(f"Datos de listings cargados desde '{LISTINGS_DATA_FILE}'. Total: {len(listings_data)} anuncios.")
    else:
        print(f"Advertencia: '{LISTINGS_DATA_FILE}' no encontrado. Ejecuta 'parte_1_analisis_imagenes.py' primero.")
        listings_data = []  # Asegúrate de que sea una lista vacía para evitar errores
        listings_by_guid = {}

    # Cargar resultados del análisis
    if os.path.exists(ANALYSIS_RESULTS_FILE):
        with open(ANALYSIS_RESULTS_FILE, 'r', encoding='utf-8') as f:
            analysis_results = json.load(f)
        print(f"Resultados del análisis cargados desde '{ANALYSIS_RESULTS_FILE}'.")
    else:
        print(f"Advertencia: '{ANALYSIS_RESULTS_FILE}' no encontrado. Ejecuta 'parte_1_analisis_imagenes.py' primero.")
        analysis_results = {}


# --- Rutas de la API ---

@app.route('/')
def home():
    return "Servidor API de datos de coches en funcionamiento. Usa las rutas /api/listings o /api/analysis."


@app.route('/api/listings', methods=['GET'])
def get_listings():
    """
    Devuelve una lista paginada de todos los listings de coches.
    Soporta paginación con 'page' y 'limit' como parámetros de query.
    """
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)

    start_index = (page - 1) * limit
    end_index = start_index + limit

    # Manejar caso de índice fuera de rango si listings_data es pequeño
    if start_index >= len(listings_data):
        paginated_listings = []
    else:
        paginated_listings = listings_data[start_index:end_index]

    safe_listings = []
    for listing in paginated_listings:
        safe_listing = listing.copy()
        # En la respuesta de lista, solo se muestran URLs de imagen si se han descargado
        if 'downloaded_images' in safe_listing and safe_listing['downloaded_images']:
            # Tomar la primera imagen descargada para la miniatura
            first_image = safe_listing['downloaded_images'][0]
            safe_listing[
                'thumbnail_url'] = f"/api/images/{safe_listing['guid_anuncio']}/{os.path.basename(first_image['local_path'])}"
        else:
            safe_listing['thumbnail_url'] = None  # No hay imagen disponible

        # Eliminar 'downloaded_images' y otras claves internas para una respuesta más limpia
        safe_listing.pop('downloaded_images', None)
        # Puedes eliminar otras claves aquí si no quieres que aparezcan en la lista inicial
        safe_listing.pop('url_imagenes', None)  # Eliminar la URL original del CSV
        safe_listing.pop('URL Carpeta Drive Imágenes', None)
        safe_listing.pop('Tours', None)
        safe_listing.pop('precio_financiado', None)  # Se maneja en detalle
        safe_listing.pop('km', None)  # Se maneja en detalle
        safe_listing.pop('anyo', None)  # Se maneja en detalle

        # Asegurar que los nombres de las claves coincidan con lo que espera el frontend
        # El frontend espera 'marca', 'modelo', 'precio_contado', 'kilometros', 'año'
        safe_listing['marca'] = safe_listing.get('Marca')
        safe_listing['modelo'] = safe_listing.get('Modelo')
        safe_listing['precio'] = safe_listing.get('Precio Contado')  # Usa Precio Contado para la lista
        safe_listing['concesionario'] = safe_listing.get('Concesionario')
        safe_listing['kilometros'] = safe_listing.get('Kilómetros')
        safe_listing['año'] = safe_listing.get('Año Matriculación')
        # ... y así con las demás claves que el frontend necesite para la vista de lista

        safe_listings.append(safe_listing)

    return jsonify({
        "page": page,
        "limit": limit,
        "total_listings": len(listings_data),
        "listings": safe_listings
    })


@app.route('/api/listings/<guid>', methods=['GET'])
def get_listing_by_guid(guid):
    """
    Devuelve los detalles de un listing específico por su GUID.
    """
    listing = listings_by_guid.get(guid)
    if listing:
        safe_listing = listing.copy()

        # Procesar las imágenes descargadas para el detalle
        processed_images = []
        if 'downloaded_images' in safe_listing and safe_listing['downloaded_images']:
            for img_info in safe_listing['downloaded_images']:
                processed_images.append({
                    "original_url": img_info['original_url'],
                    "size_bytes": img_info['size_bytes'],
                    "width": img_info['width'],
                    "height": img_info['height'],
                    # Aquí, la URL de la API para cargar la imagen real desde el servidor
                    "api_image_url": f"/api/images/{guid}/{os.path.basename(img_info['local_path'])}"
                })
        safe_listing['images'] = processed_images  # Renombrar a 'images' para el frontend

        # Normalizar los nombres de las claves para que el frontend pueda usarlas fácilmente
        # Asegúrate de que estos nombres coincidan con los IDs que usas en index.html y script.js
        safe_listing['marca'] = safe_listing.get('Marca')
        safe_listing['modelo'] = safe_listing.get('Modelo')
        safe_listing['precio'] = safe_listing.get('Precio Contado')  # O el que quieras mostrar en detalle
        safe_listing['precio_financiado_display'] = safe_listing.get(
            'Precio Financiado')  # Nombre diferente si es solo para mostrar
        safe_listing['año'] = safe_listing.get('Año Matriculación')
        safe_listing['concesionario'] = safe_listing.get('Concesionario')
        safe_listing['tipo_de_motor'] = safe_listing.get('Tipo Combustible')  # Ajustar a lo que tu CSV tenga
        safe_listing['kilometros'] = safe_listing.get('Kilómetros')
        safe_listing['cambio'] = safe_listing.get('Transmisión')
        safe_listing['localidad'] = safe_listing.get('Ubicación Concesionario')  # Asumiendo que esto es la localidad
        safe_listing[
            'provincia'] = "N/A"  # Si no tienes esta columna, pon N/A o intenta extraerla de Ubicación Concesionario
        safe_listing['tipo_de_anuncio'] = "Coche de ocasión"  # Si no tienes esta columna, un valor fijo
        safe_listing['clase_de_vehículo'] = "Turismo"  # Si no tienes esta columna, un valor fijo
        safe_listing['combustible'] = safe_listing.get('Tipo Combustible')
        safe_listing['carrocería'] = safe_listing.get('Carrocería')  # Asegúrate de que esta columna exista
        safe_listing['garantía'] = safe_listing.get('Garantía Oficial')
        safe_listing['descripción'] = safe_listing.get('Descripción')  # Asegúrate de que esta columna exista
        safe_listing['puertas'] = safe_listing.get('Puertas')  # Asegúrate de que esta columna exista
        safe_listing['url_anuncio'] = safe_listing.get('URL Anuncio')

        # Eliminar claves originales para evitar duplicados o datos internos en el JSON final
        # Puedes ajustar esto según lo que quieras que vea el frontend
        safe_listing.pop('downloaded_images', None)
        safe_listing.pop('url_imagenes', None)
        safe_listing.pop('Marca', None)
        safe_listing.pop('Modelo', None)
        safe_listing.pop('Precio Contado', None)
        safe_listing.pop('Precio Financiado', None)
        safe_listing.pop('Año Matriculación', None)
        safe_listing.pop('Kilómetros', None)
        safe_listing.pop('Tipo Combustible', None)
        safe_listing.pop('Concesionario', None)
        safe_listing.pop('Transmisión', None)
        safe_listing.pop('Ubicación Concesionario', None)
        safe_listing.pop('Garantía Oficial', None)
        safe_listing.pop('Descripción', None)
        safe_listing.pop('Puertas', None)
        safe_listing.pop('URL Anuncio', None)
        safe_listing.pop('URL Carpeta Drive Imágenes', None)
        safe_listing.pop('Tours', None)
        # Puedes añadir más .pop() para eliminar otras claves del CSV que no quieras exponer

        return jsonify(safe_listing)
    return jsonify({"error": "Listing no encontrado"}), 404


@app.route('/api/analysis', methods=['GET'])
def get_analysis_results():
    """
    Devuelve los resultados del análisis.
    """
    return jsonify(analysis_results)


@app.route('/api/images/<listing_guid>/<filename>', methods=['GET'])
def serve_image(listing_guid, filename):
    """
    Sirve archivos de imagen descargados para un listing específico.
    """
    # La carpeta 'imagenes_coches_descargadas' está en la raíz del proyecto
    # y dentro de ella, las subcarpetas con el GUID del anuncio.
    image_base_path = os.path.join(os.getcwd(), DOWNLOAD_DIR, listing_guid)

    if not os.path.isdir(image_base_path):
        return jsonify({"error": "Directorio de imágenes no encontrado para este listing o ruta incorrecta"}), 404

    # send_from_directory automáticamente maneja rutas seguras
    return send_from_directory(image_base_path, filename)


# --- Punto de entrada para el servidor ---
if __name__ == '__main__':
    load_data()  # Carga los datos cuando el servidor arranca
    app.run(debug=True, port=5000)