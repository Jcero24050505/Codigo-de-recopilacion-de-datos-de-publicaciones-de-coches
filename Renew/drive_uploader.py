import os
import pickle  # Importamos pickle para guardar/cargar tokens
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Si modificas estos 'scopes', elimina el archivo token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def authenticate_google_drive():
    """Autentica con la API de Google Drive, solicitando verificación si es necesario."""
    creds = None
    # El archivo token.pickle almacena los tokens de acceso y actualización del usuario.
    # Se crea automáticamente cuando el flujo de autorización se completa por primera vez.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # Si no hay credenciales (válidas) o están expiradas, se le pide al usuario que inicie sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Comprobar si credentials.json existe
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "credentials.json no encontrado. Por favor, descarga tus credenciales de Google API desde Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)  # Esto abrirá una ventana del navegador para la autenticación
        # Guardar las credenciales para la próxima ejecución en token.pickle
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service


def create_drive_folder_if_not_exists(service, folder_name, parent_folder_id=None):
    """
    Crea una carpeta en Google Drive si no existe.
    Retorna el ID de la carpeta.
    """
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_folder_id:
        query += f" and '{parent_folder_id}' in parents"

    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])

    if not items:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        file = service.files().create(body=file_metadata, fields='id').execute()
        print(f"Carpeta creada: {folder_name} (ID: {file.get('id')})")
        return file.get('id')
    else:
        print(f"La carpeta '{folder_name}' ya existe (ID: {items[0].get('id')})")
        return items[0].get('id')


def upload_image_to_drive(service, file_path, folder_id):
    """
    Sube un archivo de imagen a una carpeta específica de Google Drive.
    Retorna el ID del archivo y un enlace de vista web.
    """
    file_name = os.path.basename(file_path)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg', resumable=True)

    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        print(f"Subido '{file_name}' (ID: {file.get('id')})")
        return file.get('id'), file.get('webViewLink')  # Retorna tanto el ID como el webViewLink
    except Exception as e:
        print(f"Error al subir {file_name}: {e}")
        return None, None