// script.js

// URL BASE de tu API de Flask
const FLASK_API_BASE_URL = 'http://127.0.0.1:5000'; // ¡Importante: Asegúrate de que Flask corre en este puerto!

let allListings = [];
let currentPage = 1;
const listingsPerPage = 10;

// --- Referencias a elementos del DOM ---
const listingsContainer = document.getElementById('car-listings');
const loadingMessageElement = document.getElementById('loading-message');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');

const errorMessageElement = document.getElementById('error-message') || (function() {
    const el = document.createElement('p');
    el.id = 'error-message';
    el.className = 'has-text-danger is-size-5 has-text-centered';
    el.style.display = 'none';
    if (listingsContainer) {
        listingsContainer.parentNode.insertBefore(el, listingsContainer);
    }
    return el;
})();

const totalImagesElement = document.getElementById('total-images-processed');
const avgWeightElement = document.getElementById('avg-weight');
const avgDimensionsElement = document.getElementById('avg-dimensions');

// Paginación
const prevButton = document.getElementById('prev-page');
const currentPageSpan = document.getElementById('current-page');
const totalPagesSpan = document.getElementById('total-pages');
const nextButton = document.getElementById('next-page');

// Modal de Detalles
const carDetailModal = document.getElementById('car-detail-modal');
const closeModalButton = document.getElementById('close-modal');
const closeModalFooterButton = document.getElementById('close-modal-footer');
const modalCarTitle = document.getElementById('modal-car-title');
const modalImagesGallery = document.getElementById('modal-images-gallery'); // Este será el contenedor del carrusel

// IDs para los detalles del coche en el modal
const modalMarca = document.getElementById('modal-marca');
const modalModelo = document.getElementById('modal-modelo');
const modalPrecio = document.getElementById('modal-precio');
const modalAnyo = document.getElementById('modal-anyo');
const modalConcesionario = document.getElementById('modal-concesionario');
const modalMotor = document.getElementById('modal-motor');
const modalKilometros = document.getElementById('modal-kilometros');
const modalCambio = document.getElementById('modal-cambio');
const modalLocalidad = document.getElementById('modal-localidad');
const modalProvincia = document.getElementById('modal-provincia');
const modalTipoAnuncio = document.getElementById('modal-tipo-anuncio');
const modalClaseVehiculo = document.getElementById('modal-clase_de_vehículo');
const modalCombustible = document.getElementById('modal-combustible');
const modalCarroceria = document.getElementById('modal-carroceria');
const modalGarantia = document.getElementById('modal-garantia');
const modalDescripcion = document.getElementById('modal-descripcion');
const modalPuertas = document.getElementById('modal-puertas');
const modalUrlAnuncio = document.getElementById('modal-url-anuncio');
const modalTour360 = document.getElementById('modal-tour-360'); // Nuevo elemento para el tour 360

// Variables para el carrusel
let currentImageIndex = 0;
let carImages = [];

// --- Funciones de Fetch y Display ---

async function fetchListings() {
    try {
        if (errorMessageElement) errorMessageElement.style.display = 'none';
        if (loadingMessageElement) loadingMessageElement.style.display = 'block';
        if (listingsContainer) listingsContainer.innerHTML = '';

        const response = await fetch(`${FLASK_API_BASE_URL}/api/listings?page=${currentPage}&limit=${listingsPerPage}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        allListings = data.listings;
        displayListings(allListings);
        updatePagination(data.page, data.limit, data.total_listings);

        if (loadingMessageElement) loadingMessageElement.style.display = 'none';
        if (errorMessageElement) errorMessageElement.style.display = 'none';

    } catch (error) {
        console.error('Error fetching listings:', error);
        if (errorMessageElement) {
            errorMessageElement.textContent = `Error al cargar los coches: ${error.message}. Asegúrate de que el servidor API esté funcionando en ${FLASK_API_BASE_URL}.`;
            errorMessageElement.style.display = 'block';
        }
        if (loadingMessageElement) loadingMessageElement.style.display = 'none';
        if (listingsContainer) listingsContainer.innerHTML = '<div class="column is-12 has-text-centered"><p class="is-size-5">No se pudieron cargar los listados de coches.</p></div>';
    }
}

async function fetchAnalysisResults() {
    try {
        const response = await fetch(`${FLASK_API_BASE_URL}/api/analysis`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        // Actualizar los elementos en el HTML con los resultados del análisis
        if (totalImagesElement) {
            totalImagesElement.textContent = data['Total Imágenes Procesadas'] !== null ? data['Total Imágenes Procesadas'] : 'N/A';
        }
        if (avgWeightElement) {
            avgWeightElement.textContent = data['Promedio Peso (KB)'] !== null ? `${data['Promedio Peso (KB)'].toFixed(2)} KB` : 'N/A';
        }
        if (avgDimensionsElement) {
            avgDimensionsElement.textContent = data['Promedio Dimensiones (px)'] !== null ? data['Promedio Dimensiones (px)'] : 'N/A';
        }

    } catch (error) {
        console.error('Error fetching analysis results:', error);
        if (totalImagesElement) totalImagesElement.textContent = 'N/A';
        if (avgWeightElement) avgWeightElement.textContent = 'N/A';
        if (avgDimensionsElement) avgDimensionsElement.textContent = 'N/A';
    }
}


function displayListings(listingsToDisplay) {
    if (!listingsContainer) return;
    listingsContainer.innerHTML = '';

    if (listingsToDisplay.length === 0) {
        listingsContainer.innerHTML = '<div class="column is-12 has-text-centered"><p>No se encontraron coches con esos criterios de búsqueda.</p></div>';
        return;
    }

    listingsToDisplay.forEach(listing => {
        const listingColumn = document.createElement('div');
        listingColumn.className = 'column is-one-quarter-desktop is-half-tablet is-full-mobile';

        const listingCard = document.createElement('div');
        listingCard.className = 'card';

        // ¡CORRECCIÓN AQUÍ! Prefijar FLASK_API_BASE_URL a thumbnail_url
        const imageUrl = listing.thumbnail_url && listing.thumbnail_url !== "N/A"
                         ? `${FLASK_API_BASE_URL}${listing.thumbnail_url}`
                         : 'https://via.placeholder.com/256x192?text=Sin+Imagen';

        // *** AÑADIDO PARA DEPURACIÓN: Ver la URL de la imagen de portada ***
        console.log(`DEBUG: URL de imagen para ${listing.marca || 'Coche'} ${listing.modelo || ''}: ${imageUrl}`);

        listingCard.innerHTML = `
            <div class="card-image">
                <figure class="image is-4by3">
                    <img src="${imageUrl}" alt="${listing.marca || 'Coche'} ${listing.modelo || ''}">
                </figure>
            </div>
            <div class="card-content">
                <div class="media">
                    <div class="media-content">
                        <p class="title is-5">${listing.marca || 'N/A'} ${listing.modelo || 'N/A'}</p>
                    </div>
                </div>
                <div class="content">
                    <p><strong>Precio:</strong> ${listing.precio !== null ? listing.precio.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' }) : 'N/A'}</p>
                    <p><strong>Kilómetros:</strong> ${listing.kilometros !== null ? listing.kilometros.toLocaleString('es-ES') + ' km' : 'N/A'}</p>
                    <p><strong>Año:</strong> ${listing.año !== null ? listing.año : 'N/A'}</p>
                    <p><strong>Concesionario:</strong> ${listing.concesionario || 'N/A'}</p>
                    <button class="button is-info is-small mt-3" onclick="openCarDetailModal('${listing.guid_anuncio}')">Ver Detalles</button>
                </div>
            </div>
        `;
        listingColumn.appendChild(listingCard);
        listingsContainer.appendChild(listingColumn);
    });
}


function updatePagination(page, limit, total) {
    const totalPages = Math.ceil(total / limit);

    if (currentPageSpan) {
        currentPageSpan.textContent = page;
    }
    if (totalPagesSpan) {
        totalPagesSpan.textContent = totalPages;
    }

    if (prevButton) {
        prevButton.disabled = page === 1;
        prevButton.onclick = () => {
            if (currentPage > 1) {
                currentPage--;
                fetchListings();
            }
        };
    }

    if (nextButton) {
        nextButton.disabled = page === totalPages;
        nextButton.onclick = () => {
            if (currentPage < totalPages) {
                currentPage++;
                fetchListings();
            }
        };
    }
}

function performSearch() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    if (!searchTerm) {
        displayListings(allListings);
        return;
    }
    const filteredListings = allListings.filter(listing => {
        const marca = listing.marca ? String(listing.marca).toLowerCase() : '';
        const modelo = listing.modelo ? String(listing.modelo).toLowerCase() : '';
        const concesionario = listing.concesionario ? String(listing.concesionario).toLowerCase() : '';
        return marca.includes(searchTerm) ||
               modelo.includes(searchTerm) ||
               concesionario.includes(searchTerm);
    });
    displayListings(filteredListings);
}

// --- Funciones del Carrusel en el Modal ---
function showImage(index) {
    if (!modalImagesGallery || carImages.length === 0) return;

    const img = carImages[index];
    modalImagesGallery.innerHTML = `
        <div class="carousel-image-container has-text-centered">
            <img src="${img.api_image_url ? `${FLASK_API_BASE_URL}${img.api_image_url}` : 'https://via.placeholder.com/600x450?text=No+Disponible'}" alt="Imagen de coche">
        </div>
        <div class="carousel-navigation has-text-centered mt-2">
            <button class="button is-small is-info mr-2" id="prev-image-btn" ${index === 0 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
            <span class="has-text-weight-bold">${index + 1} / ${carImages.length}</span>
            <button class="button is-small is-info ml-2" id="next-image-btn" ${index === carImages.length - 1 ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
        </div>
    `;

    document.getElementById('prev-image-btn').onclick = () => navigateCarousel(-1);
    document.getElementById('next-image-btn').onclick = () => navigateCarousel(1);
}

function navigateCarousel(direction) {
    currentImageIndex += direction;
    if (currentImageIndex < 0) currentImageIndex = 0;
    if (currentImageIndex >= carImages.length) currentImageIndex = carImages.length - 1;
    showImage(currentImageIndex);
}


// --- Funciones del Modal de Detalles ---

async function openCarDetailModal(guid) {
    if (!carDetailModal) return;

    try {
        const response = await fetch(`${FLASK_API_BASE_URL}/api/listings/${guid}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const carDetails = await response.json();

        // Rellenar el modal con los datos del coche
        if (modalCarTitle) modalCarTitle.textContent = `${carDetails.marca || 'N/A'} ${carDetails.modelo || 'N/A'}`;
        if (modalMarca) modalMarca.textContent = carDetails.marca || 'N/A';
        if (modalModelo) modalModelo.textContent = carDetails.modelo || 'N/A';
        if (modalPrecio) modalPrecio.textContent = carDetails.precio !== null ? carDetails.precio.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' }) : 'N/A';
        if (modalAnyo) modalAnyo.textContent = carDetails.año !== null ? carDetails.año : 'N/A';
        if (modalConcesionario) modalConcesionario.textContent = carDetails.concesionario || 'N/A';
        if (modalMotor) modalMotor.textContent = carDetails.tipo_de_motor || 'N/A';
        if (modalKilometros) modalKilometros.textContent = carDetails.kilometros !== null ? carDetails.kilometros.toLocaleString('es-ES') + ' km' : 'N/A';
        if (modalCambio) modalCambio.textContent = carDetails.cambio || 'N/A';
        if (modalLocalidad) modalLocalidad.textContent = carDetails.localidad || 'N/A';
        if (modalProvincia) modalProvincia.textContent = carDetails.provincia || 'N/A';
        if (modalTipoAnuncio) modalTipoAnuncio.textContent = carDetails.tipo_de_anuncio || 'N/A';
        if (modalClaseVehiculo) modalClaseVehiculo.textContent = carDetails.clase_de_vehículo || 'N/A';
        if (modalCombustible) modalCombustible.textContent = carDetails.combustible || 'N/A';
        if (modalCarroceria) modalCarroceria.textContent = carDetails.carrocería || 'N/A';
        if (modalGarantia) modalGarantia.textContent = carDetails.garantia || 'N/A';
        if (modalDescripcion) modalDescripcion.textContent = carDetails.descripción || 'N/A';
        if (modalPuertas) modalPuertas.textContent = carDetails.puertas !== null ? carDetails.puertas : 'N/A';

        // URL Anuncio
        if (modalUrlAnuncio) {
            if (carDetails.url_anuncio && carDetails.url_anuncio !== "N/A") {
                modalUrlAnuncio.href = carDetails.url_anuncio;
                modalUrlAnuncio.style.display = 'inline';
            } else {
                modalUrlAnuncio.href = '#';
                modalUrlAnuncio.style.display = 'none';
            }
        }

        // Tour 360 (¡Nuevo!)
        if (modalTour360) {
            if (carDetails.tours_url && carDetails.tours_url !== "N/A" && carDetails.tours_url !== "") {
                modalTour360.innerHTML = `<strong>Tour 360:</strong> <a href="${carDetails.tours_url}" target="_blank" rel="noopener noreferrer">Ver Tour 360</a>`;
                modalTour360.style.display = 'block';
            } else {
                modalTour360.style.display = 'none'; // Ocultar si no hay tour
            }
        }


        // Cargar imágenes para el carrusel
        carImages = carDetails.images || [];
        currentImageIndex = 0; // Resetear índice al abrir el modal
        if (carImages.length > 0) {
            showImage(currentImageIndex); // Mostrar la primera imagen del carrusel
        } else {
            if (modalImagesGallery) modalImagesGallery.innerHTML = '<div class="column is-12"><p>No hay imágenes disponibles para este coche.</p></div>';
        }

        // Mostrar el modal
        carDetailModal.classList.add('is-active');

    } catch (error) {
        console.error('Error fetching car details:', error);
        alert('No se pudieron cargar los detalles del coche. Asegúrate de que el servidor API esté funcionando.');
    }
}

function closeCarDetailModal() {
    if (carDetailModal) {
        carDetailModal.classList.remove('is-active');
    }
}

// --- Event Listeners ---

document.addEventListener('DOMContentLoaded', () => {
    fetchListings();
    fetchAnalysisResults();

    if (searchButton) {
        searchButton.addEventListener('click', performSearch);
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                performSearch();
            }
        });
    }

    if (closeModalButton) {
        closeModalButton.addEventListener('click', closeCarDetailModal);
    }
    if (closeModalFooterButton) {
        closeModalFooterButton.addEventListener('click', closeCarDetailModal);
    }
    if (carDetailModal) {
        carDetailModal.querySelector('.modal-background').addEventListener('click', closeCarDetailModal);
    }
});
