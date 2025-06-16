from playwright.sync_api import sync_playwright
from datetime import datetime
import csv
import os
import re
import time

# Importar funciones de data_processor.py
from data_processor import extract_car_data, generate_guid_from_data

# Lista de URLs a scrapear (puedes añadir más si lo deseas)
URLS_TO_SCRAPE = [
    "https://www.autofer.com/coches/segunda-mano/madrid/renault/clio/gasolina/1-0-tce-90cv-intens/1062915/",
    "https://www.autofer.com/coches/segunda-mano/madrid/renault/austral/gasolina/e-tech-full-hybrid-200cv-evolution/1056593/",
    "https://www.autofer.com/coches/segunda-mano/madrid/renault/arkana/gasolina/1-3-tce-140cv-edc-microhibrido-zen/1038292/",
    "https://www.autofer.com/coches/segunda-mano/madrid/dacia/sandero-stepway/gasolina/0-9-tce-90cv-stepway-comfort/1000546/",
    "https://www.autofer.com/coches/segunda-mano/madrid/dacia/duster/hibrido/1-0-tce-100cv-glp-4x2-sl-aniversario/1011551/",
    "https://www.autofer.com/coches/segunda-mano/madrid/dacia/sandero-stepway/gasolina/1-0-tce-90cv-stepway-expression/1036354/",
    "https://www.autofer.com/coches/segunda-mano/madrid/renault/megane/gasolina/tce-74kw-100cv-tech-road-energy/1000597/",
    "https://www.autofer.com/coches/segunda-mano/madrid/renault/megane/gasolina/tce-140cv-gpf-techno-fast-track/895637/",
    "https://www.autofer.com/coches/segunda-mano/madrid/renault/arkana/gasolina/1-6-e-tech-145cv-rs-line/1058061/",
    "https://www.autofer.com/coches/segunda-mano/madrid/renault/clio/hibrido/1-6-e-tech-hibrido-140cv-zen/914544/"
    # "https://www.autofer.com/coches/segunda-mano/madrid/otro-ejemplo/url-aqui/1234567/", # Añade más URLs aquí
]

# --- Configuración del carrusel de imágenes ---
GALLERY_OPEN_BUTTON_TEXT_REGEX = re.compile(r'\d+\s*imágenes', re.IGNORECASE)
NEXT_BUTTON_SELECTOR = 'button.lg-next.lg-icon'
IMAGE_SELECTOR = 'img.lg-object.lg-image'

MAX_IMAGE_ITERATIONS = 50  # Un límite de seguridad para el bucle


def scrape_car_details(url: str, playwright_page) -> dict:
    car_data = {}
    image_urls = []

    try:
        print(f"--- Scraping details for: {url} ---")
        playwright_page.goto(url, wait_until='domcontentloaded')
        print("Página de detalle cargada.")

        # Aceptar cookies
        accept_cookies_button = playwright_page.locator('button.iubenda-cs-accept-btn')
        if accept_cookies_button.is_visible():
            accept_cookies_button.click()
            print("DEBUG: Cookies aceptadas.")
            playwright_page.wait_for_timeout(1000)
        else:
            print("DEBUG: Botón de aceptar cookies NO encontrado o no visible.")

        # Abrir la galería
        gallery_open_button = playwright_page.get_by_role("button", name=GALLERY_OPEN_BUTTON_TEXT_REGEX)
        if gallery_open_button.is_visible():
            gallery_open_button.click()
            print("DEBUG: Clic en el botón para abrir la galería ('X imágenes').")
            try:
                # Esperamos a que la imagen principal sea visible y también el botón de siguiente
                playwright_page.wait_for_selector(f'{IMAGE_SELECTOR}:visible', state='visible', timeout=5000)
                playwright_page.wait_for_selector(NEXT_BUTTON_SELECTOR, state='visible', timeout=5000)
                print("DEBUG: Galería LightGallery abierta y elementos visibles.")
            except Exception as e:
                print(
                    f"DEBUG: Fallo al esperar selectores de galería: {e}. Puede que la galería no se haya abierto correctamente.")
        else:
            print(f"DEBUG: Botón para abrir la galería (con texto 'X imágenes') NO encontrado o no visible.")

        # Recopilar URLs de imágenes del carrusel
        # Capturar la primera imagen
        current_image_element = playwright_page.locator(IMAGE_SELECTOR).first
        if current_image_element.is_visible():
            src = current_image_element.get_attribute('src')
            if src and src not in image_urls:
                image_urls.append(src)
                print(f"DEBUG: Imagen inicial de galería añadida: {src}")
        else:
            print("DEBUG: La primera imagen de la galería no está visible después de intentar abrirla.")

        next_button = playwright_page.locator(NEXT_BUTTON_SELECTOR)
        if next_button.is_visible():
            print("DEBUG: Botón 'siguiente' del carrusel de LightGallery encontrado. Recopilando imágenes...")
            for i in range(MAX_IMAGE_ITERATIONS):
                try:
                    # Comprobamos si el botón 'siguiente' tiene la clase 'lg-disabled'
                    # Si la tiene, significa que hemos llegado al final del carrusel.
                    # Se añade un pequeño timeout para get_attribute por si el atributo no está inmediatamente disponible.
                    next_button_class = next_button.get_attribute('class', timeout=100)
                    if next_button_class and (
                            'lg-disabled' in next_button_class or 'lg-next-disabled' in next_button_class):
                        print("DEBUG: Botón 'siguiente' deshabilitado. Fin del carrusel.")
                        break

                    # Obtener el SRC de la imagen actual ANTES de hacer clic
                    current_src_before_click = playwright_page.locator(IMAGE_SELECTOR).first.get_attribute('src')

                    next_button.click()

                    # CAMBIO CLAVE: Esperar a que se cargue una nueva imagen por red.
                    # Esto es más fiable que esperar el cambio de atributo en el DOM.
                    try:
                        response = playwright_page.wait_for_response(lambda res:
                                                                     res.url.startswith(
                                                                         'https://cdn.dealerk.es/dealer/datafiles/vehicle/images/') and
                                                                     res.request.resource_type == 'image' and
                                                                     res.url != current_src_before_click,
                                                                     # Asegurar que la URL sea diferente
                                                                     timeout=10000
                                                                     # Se le da más tiempo para la respuesta de red (10 segundos)
                                                                     )
                        print(f"DEBUG: Nueva respuesta de imagen detectada: {response.url}")
                        # Después de la respuesta, damos un pequeño tiempo para que el DOM se actualice.
                        playwright_page.wait_for_timeout(200)
                    except Exception as e_wait_response:
                        print(
                            f"DEBUG: No se detectó una nueva respuesta de imagen o timeout. Posible fin del carrusel o fallo: {e_wait_response}")
                        break  # Salir del bucle si no hay nueva imagen por red

                    # Obtener el SRC de la imagen actual DESPUÉS de la espera por la respuesta
                    new_image_element = playwright_page.locator(IMAGE_SELECTOR).first
                    if new_image_element.is_visible():
                        src = new_image_element.get_attribute('src')
                        if src and src not in image_urls:
                            image_urls.append(src)
                            print(f"DEBUG: Imagen {len(image_urls)} añadida: {src}")
                        else:
                            if src in image_urls:
                                print(f"DEBUG: Imagen {src} ya vista. Fin del carrusel o repetición.")
                            else:
                                print("DEBUG: No se pudo obtener src de la imagen actual después de click.")
                            break
                    else:
                        print("DEBUG: No hay imagen visible después de click. Fin del carrusel.")
                        break
                except Exception as e:
                    print(f"DEBUG: Error general en el bucle del carrusel (click o obtención de imagen): {e}")
                    break  # Salir del bucle ante cualquier error

        else:
            print(
                "DEBUG: Botón 'siguiente' del carrusel de LightGallery NO encontrado o no visible (después de intentar abrir galería).")

        # Cerrar la galería LightGallery
        close_button = playwright_page.locator('button.lg-close.lg-icon')
        if close_button.is_visible():
            close_button.click()
            print("DEBUG: Galería LightGallery cerrada.")
            playwright_page.wait_for_timeout(500)
        else:
            print("DEBUG: Botón para cerrar la galería (lg-close) NO encontrado o no visible.")

        html_content = playwright_page.content()
        print("HTML completo de la página de detalle obtenido.")

        car_data = extract_car_data(html_content, url, image_urls)

        print(f"Datos extraídos para {car_data.get('model', 'N/A')}:")
        print(f"  Marca: {car_data.get('brand', 'N/A')}, Modelo: {car_data.get('model', 'N/A')}")
        print(f"  Km: {car_data.get('kilometros', 'N/A')}, Año: {car_data.get('registration_year', 'N/A')}")
        print(f"  Combustible: {car_data.get('fuel_type', 'N/A')}, Potencia: {car_data.get('engine_cv', 'N/A')}")
        print(f"  Imágenes: {len(car_data.get('images', []))} encontradas.")

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        car_data = {'original_url': url, 'error': str(e), 'guid': generate_guid_from_data(url), 'images': []}

    return car_data


def save_to_csv(data: list[dict], filename: str):
    if not data:
        print("No hay datos para guardar en CSV.")
        return

    all_keys = set()
    for row in data:
        all_keys.update(row.keys())

    fieldnames_ordered_start = ['original_url', 'guid', 'brand', 'model', 'price_cash', 'price_financed',
                                'kilometros', 'registration_year', 'fuel_type', 'engine_cv',
                                'transmission', 'condition', 'body_type', 'traction', 'seats']

    fieldnames_ordered_end = ['images']

    fieldnames = []
    for key in fieldnames_ordered_start:
        if key in all_keys:
            fieldnames.append(key)
            all_keys.remove(key)

    remaining_keys = sorted(list(all_keys - set(fieldnames_ordered_end)))
    fieldnames.extend(remaining_keys)

    for key in fieldnames_ordered_end:
        if key in all_keys:
            fieldnames.append(key)

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in data:
            row_to_write = row.copy()
            if 'images' in row_to_write and isinstance(row_to_write['images'], list):
                row_to_write['images'] = '|'.join(row_to_write['images'])
            writer.writerow(row_to_write)
    print(f"Datos guardados en {filename}")


def main():
    all_scraped_cars_data = []

    with sync_playwright() as p:
        # ¡RECUERDA ACTIVAR headless=False para depurar visualmente!
        # browser = p.chromium.launch(headless=False, slow_mo=500)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for url in URLS_TO_SCRAPE:
            car_data = scrape_car_details(url, page)
            all_scraped_cars_data.append(car_data)
            print("-" * 50)

        browser.close()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"scraped_cars_{timestamp}.csv"
    save_to_csv(all_scraped_cars_data, csv_filename)
    print("Scraping finalizado.")


if __name__ == "__main__":
    main()