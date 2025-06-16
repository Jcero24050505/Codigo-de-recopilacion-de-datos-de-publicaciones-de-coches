# Google Drive API Configuration
# Coloca tu archivo de credenciales de Google API (credentials.json) en el mismo directorio que main.py
# El archivo 'token.pickle' se generará automáticamente después de la primera autenticación exitosa.

# ID de la carpeta principal en Google Drive donde quieres crear subcarpetas para las imágenes de los coches.
# Si lo dejas en None, las subcarpetas se crearán en la raíz de tu Google Drive.
DRIVE_PARENT_FOLDER_ID = None # Ejemplo: '1-abcdefg1234567890abcdefg'

# Nombre de la carpeta principal donde se almacenarán todas las imágenes de los coches (ej. 'Renew_Autofer_Scrapes')
# Las subcarpetas para cada coche se crearán dentro de esta carpeta principal.
MAIN_DRIVE_FOLDER_NAME = 'Renew_Autofer_Scrapes'

# Ruta al directorio temporal para descargar imágenes antes de subirlas a Drive
TEMP_IMAGE_DIR = 'temp_renew_images'

# Nombre del archivo donde se guardarán las URLs de los coches.
URLS_FILE = 'urls.txt'