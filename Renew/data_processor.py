import re
from bs4 import BeautifulSoup
import hashlib


def clean_value(text: str) -> str:
    """
    Limpia espacios en blanco y elimina caracteres no deseados o unidades de un VALOR.
    """
    if text is None:
        return ''
    text = text.strip()
    # Remove common units and symbols that are part of values
    text = text.replace('€', '').replace('Km', '').replace('CV', '').replace('/ Mes', '').replace('KW', '')
    text = text.replace('m', '').replace('Kg', '').replace('L', '').replace('/100', '')
    text = text.replace('CO₂', '').replace('seg', '').replace('km/h', '')
    text = text.replace(':', '').replace('(', '').replace(')', '')  # Keep periods if they are decimal separators
    text = re.sub(r'\s+', ' ', text)  # Normalize multiple spaces to one single space
    return text.strip()


def clean_label_for_comparison(text: str) -> str:
    """
    Limpia una etiqueta para una comparación robusta:
    - Elimina espacios al inicio/final.
    - Convierte caracteres acentuados comunes a sus equivalentes sin acento.
    - Convierte a minúsculas.
    - Elimina todos los espacios.
    """
    if text is None:
        return ''
    text = text.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    text = text.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
    text = text.replace('ñ', 'n').replace('Ñ', 'N')
    text = text.strip().lower().replace(' ', '')
    return text


def extract_car_data(html_content: str, original_url: str, image_urls_from_playwright: list) -> dict:
    """
    Extrae datos específicos de la ficha de un coche desde su contenido HTML.
    Ahora también recibe las URLs de las imágenes recopiladas por Playwright.
    Retorna un diccionario con los datos del coche, eliminando campos 'N/A'.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    car_data = {}

    car_data['original_url'] = original_url

    # Inicializar todos los campos a 'N/A' por defecto para asegurar consistencia
    # antes de eliminarlos si no se encuentran
    default_fields = [
        'brand', 'model', 'price_cash', 'price_financed', 'registration_year',
        'kilometros', 'fuel_type', 'engine_cv', 'transmission', 'condition',
        'body_type', 'traction', 'seats', 'official_warranty', 'dealer_location',
        'unique_owner', 'itv_valid_until', 'iva_type', 'number_of_keys',
        'co2_class_combined', 'co2_combined_grams', 'environmental_label',
        'demo_status', 'engine_displacement', 'num_cylinders', 'num_gears',
        'num_doors', 'exterior_color', 'color_type', 'details_exterior',
        'details_interior', 'details_confort', 'details_seguridad', 'details_extras'
    ]
    for field in default_fields:
        car_data[field] = 'N/A'

    # --- Extracción de Marca y Modelo ---
    make_model_span = soup.find('span', class_='stock-vehicle-detail__header--make-model')
    if make_model_span:
        full_make_model = make_model_span.get_text(strip=True)
        parts = full_make_model.split(maxsplit=1)
        if len(parts) > 0:
            car_data['brand'] = parts[0]
        if len(parts) > 1:
            car_data['model'] = parts[1]

    trim_span = soup.find('span', class_='stock-vehicle-detail__header--trim')
    if trim_span and car_data['model'] != 'N/A':
        trim_text = clean_value(trim_span.get_text())
        car_data['model'] = f"{car_data['model']} {trim_text}".strip()
    elif trim_span:
        car_data['model'] = clean_value(trim_span.get_text())

    # --- Extracción de Precios ---
    price_wrapper = soup.find('div', class_='stock-vehicle-detail__header--price-wrapper')
    if price_wrapper:
        cash_price_div = price_wrapper.find('div', class_='price-financed--header__cash')
        if cash_price_div:
            cash_value_p = cash_price_div.find('p', class_='price__value')
            if cash_value_p:
                car_data['price_cash'] = clean_value(cash_value_p.get_text())

        financed_price_div = price_wrapper.find('div', class_='price-financed--header__financed')
        if financed_price_div:
            financed_value_p = financed_price_div.find('p', class_='price__value')
            if financed_value_p:
                car_data['price_financed'] = clean_value(financed_value_p.get_text())

    # --- Extracción de Stock Vehicle Highlights List ---
    highlights_list = soup.find('ul', class_='stock-vehicle-highlights-list')
    if highlights_list:
        list_items = highlights_list.find_all('li', class_=re.compile(r'stock-vehicle-highlights-list__item'))
        if list_items:
            for item in list_items:
                label_span = item.find('span', class_='stock-vehicle-highlights-list__item-label')
                value_span = item.find('span', class_='stock-vehicle-highlights-list__item-value')

                if label_span and value_span:
                    raw_label = label_span.get_text()
                    cleaned_label_for_comp = clean_label_for_comparison(raw_label)
                    raw_value = value_span.get_text()

                    if cleaned_label_for_comp == 'condicion':
                        car_data['condition'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'carroceria':
                        car_data['body_type'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'matriculacion':
                        match = re.search(r'(\d{4})$', raw_value)
                        if match:
                            car_data['registration_year'] = match.group(1)
                        else:
                            car_data['registration_year'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'kilometros':
                        car_data['kilometros'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'combustible':
                        car_data['fuel_type'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'eficienciaco2':
                        car_data['co2_class_combined'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'cambio':
                        car_data['transmission'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'potencia':
                        match_cv_parentheses = re.search(r'\((\d+)\s*CV\)', raw_value, re.IGNORECASE)
                        if match_cv_parentheses:
                            car_data['engine_cv'] = match_cv_parentheses.group(1)
                        else:
                            cleaned_val_for_numbers = clean_value(raw_value)
                            numbers_only_match = re.search(r'(\d+)', cleaned_val_for_numbers)
                            if numbers_only_match:
                                car_data['engine_cv'] = numbers_only_match.group(1)
                            else:
                                car_data['engine_cv'] = cleaned_val_for_numbers
                    elif cleaned_label_for_comp == 'traccion':
                        car_data['traction'] = clean_value(raw_value)
                    elif cleaned_label_for_comp == 'plazas':
                        car_data['seats'] = clean_value(raw_value)

    # --- Extracción de Detalles de Pestañas y Especificaciones Adicionales ---
    # Estos campos se inicializan a N/A y solo se llenarán si se encuentran en el HTML inicial.
    # Dado que no se interactúa con pestañas, seguirán siendo N/A si están detrás de una interacción.

    # Especificaciones adicionales (Único Propietario, ITV, IVA, Llaves)
    specs_rows = soup.find_all('div', class_='stock-vehicle-detail__specs--row')
    if specs_rows:
        for row in specs_rows:
            label_tag = row.find('div', class_='stock-vehicle-detail__specs--label')
            value_tag = row.find('div', class_='stock-vehicle-detail__specs--value')
            if label_tag and value_tag:
                raw_label = label_tag.get_text()
                cleaned_label_for_comp = clean_label_for_comparison(raw_label.replace(':', ''))
                raw_value = value_tag.get_text()

                if cleaned_label_for_comp == 'unicopropietario':
                    car_data['unique_owner'] = clean_value(raw_value)
                elif cleaned_label_for_comp == 'itvvalidahasta':
                    car_data['itv_valid_until'] = clean_value(raw_value)
                elif cleaned_label_for_comp == 'tipodeiva':
                    car_data['iva_type'] = clean_value(raw_value)
                elif cleaned_label_for_comp == 'numerodellaves':
                    car_data['number_of_keys'] = clean_value(raw_value)

    # Equipamiento (Exterior, Interior, Confort, Seguridad, Extras)
    equipamiento_tabs_content_wrapper = soup.find('div', class_='elektra-tabs__content-wrapper')
    if equipamiento_tabs_content_wrapper:
        tab_categories_mapping = {
            'exterior': 'panel-equipamiento-exterior',
            'interior': 'panel-equipamiento-interior',
            'confort': 'panel-equipamiento-confort',
            'seguridad': 'panel-equipamiento-seguridad',
            'extras': 'panel-equipamiento-extras',
        }
        for category_key, panel_id in tab_categories_mapping.items():
            panel = equipamiento_tabs_content_wrapper.find('div', id=panel_id)
            if panel:
                items = panel.find_all('p', class_='text__body-default')
                if items:
                    car_data[f'details_{category_key}'] = "; ".join([clean_value(item.get_text()) for item in items])

    # Asignar las URLs de las imágenes recopiladas por Playwright
    car_data['images'] = image_urls_from_playwright

    # Generar el GUID
    car_data['guid'] = generate_guid_from_data(original_url)

    # Eliminar campos cuyo valor sea 'N/A'
    car_data_cleaned = {k: v for k, v in car_data.items() if v != 'N/A'}

    return car_data_cleaned


def generate_guid_from_data(url: str) -> str:
    """
    Genera un GUID (identificador único global) basado en la URL del coche.
    Esto asegura que cada coche tenga un identificador único y consistente.
    """
    return hashlib.md5(url.encode('utf-8')).hexdigest()