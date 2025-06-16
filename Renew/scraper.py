import requests  # Todavía lo necesitamos para descargar las imágenes directamente
from playwright.sync_api import sync_playwright, expect
import re  # Necesario para parsear el número de imágenes


def fetch_car_data_and_images_with_playwright(url: str) -> tuple[str, list]:
    """
    Obtiene el contenido HTML completo y las URLs de las imágenes de una página de detalle de coche usando Playwright.
    Maneja el contenido dinámico y las interacciones.
    Retorna una tupla: (contenido_html_string, lista_de_urls_imagenes)
    """
    html_content = None
    image_urls = []
    print(f"Iniciando Playwright para extraer HTML y imágenes de: {url}")

    with sync_playwright() as p:
        browser = None
        try:
            # Puedes cambiar 'headless=True' a 'headless=False' para ver el navegador en acción
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navega a la URL y espera a que la red esté inactiva (indicando que la página cargó)
            page.goto(url, wait_until='networkidle')

            # --- Manejo de la ventana emergente de cookies (si existe) ---
            try:
                # Intenta encontrar un botón que tenga "Aceptar todas" o "Entendido" o "Aceptar"
                cookie_button = page.locator(
                    'button:has-text("Aceptar todas"), button:has-text("Entendido"), button:has-text("Aceptar")')
                if cookie_button.is_visible(timeout=5000):  # Espera hasta 5 segundos
                    cookie_button.click()
                    print("Clic en botón de aceptar cookies.")
                    page.wait_for_load_state('networkidle')  # Espera a que la página se estabilice tras el clic
            except Exception:
                # No hay botón de cookies o no es visible a tiempo, o ya se aceptaron
                pass

            # Obtener el contenido HTML completo después de que la página se haya cargado y estabilizado
            html_content = page.content()

            # --- Lógica de Extracción de Imágenes (la misma que ya teníamos) ---
            # Localiza y haz clic en el botón "X imágenes" para abrir el carrusel
            images_button = page.get_by_role("button", name=re.compile(r'\d+\s+imágenes'))
            images_button_to_click = images_button.first

            if images_button_to_click.is_visible(timeout=10000):
                button_text = images_button_to_click.text_content()
                num_images_match = re.search(r'(\d+)\s+imágenes', button_text)
                total_images = int(num_images_match.group(1)) if num_images_match else 0

                print(f"Botón de imágenes encontrado: '{button_text}'. Clicando...")
                images_button_to_click.click()

                page.wait_for_selector('div.lg-item.lg-current img.lg-object.lg-image', timeout=15000)

                extracted_urls = set()

                current_img_tag = page.locator('div.lg-item.lg-current img.lg-object.lg-image').first
                if current_img_tag.is_visible() and current_img_tag.get_attribute('src'):
                    extracted_urls.add(current_img_tag.get_attribute('src'))

                next_button = page.locator('button.lg-next.lg-icon')

                if not next_button.is_visible():
                    print("Botón 'siguiente' del carrusel no visible (carrusel con una sola imagen o problema).")
                else:
                    clicks_to_perform = total_images - 1 if total_images > 0 else 30

                    for i in range(clicks_to_perform):
                        if next_button.is_enabled():
                            next_button.click()
                            page.wait_for_timeout(500)

                            visible_images_locators = page.locator(
                                'div.lg-item.lg-current img.lg-object.lg-image').all()
                            for img_loc in visible_images_locators:
                                src = img_loc.get_attribute('src')
                                if src:
                                    extracted_urls.add(src)

                            if total_images > 0 and len(extracted_urls) >= total_images:
                                print(
                                    f"Hemos extraído {len(extracted_urls)} imágenes únicas, que es el número esperado. Finalizando clicks.")
                                break
                        else:
                            print("Botón 'siguiente' deshabilitado o no visible. Posible fin del carrusel.")
                            break

                        if not next_button.is_visible():
                            print("Botón 'siguiente' no visible después de clic. Asumiendo fin del carrusel.")
                            break

                image_urls = list(extracted_urls)
                print(f"Imágenes extraídas con Playwright: {len(image_urls)}")

            else:
                print("Botón 'X imágenes' no encontrado o no visible en la página. No se extraerán imágenes dinámicas.")

        except Exception as e:
            print(f"Error durante la extracción de datos e imágenes con Playwright para {url}: {e}")
            html_content = None  # Asegurarse de que html_content sea None en caso de error
            image_urls = []
        finally:
            if browser:
                browser.close()
    return html_content, image_urls