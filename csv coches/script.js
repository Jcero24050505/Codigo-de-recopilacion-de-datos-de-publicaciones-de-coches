document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = 'http://127.0.0.1:5000/api';
    const listingsContainer = document.getElementById('car-listings');
    const totalImagesProcessedSpan = document.getElementById('total-images-processed');
    const avgWeightSpan = document.getElementById('avg-weight');
    const avgDimensionsSpan = document.getElementById('avg-dimensions');
    const loadingMessage = document.getElementById('loading-message');

    // Paginación
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const currentPageSpan = document.getElementById('current-page');
    const totalPagesSpan = document.getElementById('total-pages');
    const ITEMS_PER_PAGE = 20; // Número de coches por página
    let currentPage = 1;
    let totalListings = 0; // Se actualizará al cargar los listings
    let currentListings = []; // Para la búsqueda/filtrado (la lista completa en la página actual)

    // Modal de detalle
    const carDetailModal = document.getElementById('car-detail-modal');
    const closeModalBtn = document.getElementById('close-modal');
    const closeModalFooterBtn = document.getElementById('close-modal-footer');
    const modalCarTitle = document.getElementById('modal-car-title');
    const modalMarca = document.getElementById('modal-marca');
    const modalModelo = document.getElementById('modal-modelo');
    const modalPrecio = document.getElementById('modal-precio');
    const modalAnyo = document.getElementById('modal-anyo');
    const modalConcesionario = document.getElementById('modal-concesionario');
    const modalMotor = document.getElementById('modal-motor');
    const modalKilometros = document.getElementById('modal-kilometros');
    const modalCambio = document = document.getElementById('modal-cambio');
    const modalLocalidad = document.getElementById('modal-localidad');
    const modalProvincia = document.getElementById('modal-provincia');
    const modalTipoAnuncio = document.getElementById('modal-tipo-anuncio');
    const modalClaseVehiculo = document.getElementById('modal-clase-vehiculo');
    const modalCombustible = document.getElementById('modal-combustible');
    const modalCarroceria = document.getElementById('modal-carroceria');
    const modalGarantia = document.getElementById('modal-garantia');
    const modalDescripcion = document.getElementById('modal-descripcion');
    const modalPuertas = document.getElementById('modal-puertas');
    const modalUrlAnuncio = document.getElementById('modal-url-anuncio');
    const modalImagesGallery = document.getElementById('modal-images-gallery');

    // Búsqueda
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');

    // --- Funciones para cargar datos de la API ---

    async function fetchAnalysisResults() {
        try {
            const response = await fetch(`${API_BASE_URL}/analysis`);
            const data = await response.json();

            // Ajustar según la estructura REAL de analysis_results.json que tu server_api.py devuelve
            totalImagesProcessedSpan.textContent = data.total_imagenes_descargadas ? data.total_imagenes_descargadas.toLocaleString() : 'N/A';

            // AHORA ESTOS DEBERÍAN ESTAR EN EL JSON
            avgWeightSpan.textContent = data.promedio_peso_kb ? `${data.promedio_peso_kb.toFixed(2)} KB` : 'N/A';
            avgDimensionsSpan.textContent = data.promedio_dimensiones_px || 'N/A';

        } catch (error) {
            console.error('Error fetching analysis results:', error);
            totalImagesProcessedSpan.textContent = 'Error';
            avgWeightSpan.textContent = 'Error';
            avgDimensionsSpan.textContent = 'Error';
        }
    }

    async function fetchListings(page = 1, limit = ITEMS_PER_PAGE, query = '') {
        loadingMessage.style.display = 'block'; // Mostrar mensaje de carga
        listingsContainer.innerHTML = ''; // Limpiar listados anteriores
        prevPageBtn.disabled = true;
        nextPageBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE_URL}/listings?page=${page}&limit=${limit}`);
            const data = await response.json();

            totalListings = data.total_listings;
            const paginatedAndFilteredListings = data.listings;

            const totalPages = Math.ceil(totalListings / ITEMS_PER_PAGE);
            currentPageSpan.textContent = page;
            totalPagesSpan.textContent = totalPages;

            if (page > 1) prevPageBtn.disabled = false;
            if (page < totalPages) nextPageBtn.disabled = false;

            const filteredListings = query ? paginatedAndFilteredListings.filter(listing =>
                (listing.marca && listing.marca.toLowerCase().includes(query.toLowerCase())) ||
                (listing.modelo && listing.modelo.toLowerCase().includes(query.toLowerCase())) ||
                (listing.concesionario && listing.concesionario.toLowerCase().includes(query.toLowerCase()))
            ) : paginatedAndFilteredListings;


            if (filteredListings.length === 0 && query) {
                listingsContainer.innerHTML = '<div class="column is-12 has-text-centered"><p class="is-size-5">No se encontraron resultados para su búsqueda.</p></div>';
            } else if (filteredListings.length === 0) {
                 listingsContainer.innerHTML = '<div class="column is-12 has-text-centered"><p class="is-size-5">No hay coches disponibles.</p></div>';
            } else {
                displayListings(filteredListings);
            }


        } catch (error) {
            console.error('Error fetching listings:', error);
            listingsContainer.innerHTML = '<div class="column is-12 has-text-centered"><p class="has-text-danger is-size-5">Error al cargar los coches. Asegúrate de que el servidor API esté funcionando.</p></div>';
        } finally {
            loadingMessage.style.display = 'none'; // Ocultar mensaje de carga
        }
    }

    function displayListings(listings) {
        listingsContainer.innerHTML = ''; // Limpiar antes de añadir
        listings.forEach(listing => {
            const carCard = document.createElement('div');
            carCard.className = 'column is-one-quarter-desktop is-half-tablet is-full-mobile';

            // La API devuelve 'thumbnail_url' en la vista de lista, lista para usar.
            const thumbnailUrl = listing.thumbnail_url || 'https://via.placeholder.com/800x600?text=No+Image';

            carCard.innerHTML = `
                <div class="card">
                    <div class="card-image">
                        <figure class="image is-4by3">
                            <img src="${thumbnailUrl}" alt="${listing.marca || 'Coche'} ${listing.modelo || ''}">
                        </figure>
                    </div>
                    <div class="card-content">
                        <p class="title is-5">${listing.marca || 'N/A'} ${listing.modelo || 'N/A'}</p>
                        <p class="subtitle is-6">${listing.precio || 'N/A'}</p>
                        <div class="content">
                            <p><i class="fas fa-building"></i> ${listing.concesionario || 'N/A'}</p>
                            <p><i class="fas fa-road"></i> ${listing.kilometros ? listing.kilometros.toLocaleString() + ' km' : 'N/A'}</p>
                            <p><i class="fas fa-calendar-alt"></i> ${listing.año || 'N/A'}</p>
                        </div>
                    </div>
                    <footer class="card-footer">
                        <a href="#" class="card-footer-item view-details-btn" data-guid="${listing.guid_anuncio}">Ver Detalles</a>
                    </footer>
                </div>
            `;
            listingsContainer.appendChild(carCard);
        });

        // Adjuntar event listeners a los botones de "Ver Detalles"
        document.querySelectorAll('.view-details-btn').forEach(button => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                const guid = event.target.dataset.guid;
                openCarDetailModal(guid);
            });
        });
    }

    async function openCarDetailModal(guid) {
        try {
            const response = await fetch(`${API_BASE_URL}/listings/${guid}`);
            const car = await response.json();

            if (car.error) {
                console.error('Error fetching car details:', car.error);
                alert('No se pudo cargar los detalles del coche.');
                return;
            }

            modalCarTitle.textContent = `${car.marca || 'N/A'} ${car.modelo || 'N/A'} (${car.año || 'N/A'})`;
            modalMarca.textContent = car.marca || 'N/A';
            modalModelo.textContent = car.modelo || 'N/A';
            modalPrecio.textContent = car.precio || 'N/A';
            modalAnyo.textContent = car.año || 'N/A';
            modalConcesionario.textContent = car.concesionario || 'N/A';
            modalMotor.textContent = car.tipo_de_motor || 'N/A';
            modalKilometros.textContent = car.kilometros ? car.kilometros.toLocaleString() + ' km' : 'N/A';
            modalCambio.textContent = document.getElementById('modal-cambio');
            modalLocalidad.textContent = car.localidad || 'N/A';
            modalProvincia.textContent = car.provincia || 'N/A';
            modalTipoAnuncio.textContent = car.tipo_de_anuncio || 'N/A';
            modalClaseVehiculo.textContent = car.clase_de_vehículo || 'N/A';
            modalCombustible.textContent = car.combustible || 'N/A';
            modalCarroceria.textContent = car.carrocería || 'N/A';
            modalGarantia.textContent = car.garantía || 'N/A';
            modalDescripcion.textContent = car.descripción || 'N/A';
            modalPuertas.textContent = car.puertas || 'N/A';
            modalUrlAnuncio.href = car.url_anuncio || '#';
            modalUrlAnuncio.textContent = car.url_anuncio ? 'Ver Anuncio Original' : 'N/A';


            // Cargar imágenes del modal
            modalImagesGallery.innerHTML = '';
            if (car.images && car.images.length > 0) {
                car.images.forEach(img => {
                    const imgColumn = document.createElement('div');
                    imgColumn.className = 'column is-one-quarter'; // 4 imágenes por fila en el modal
                    imgColumn.innerHTML = `
                        <figure class="image is-4by3">
                            <img src="${API_BASE_URL}${img.api_image_url}" alt="Imagen del coche" onclick="window.open('${API_BASE_URL}${img.api_image_url}', '_blank');">
                        </figure>
                    `;
                    modalImagesGallery.appendChild(imgColumn);
                });
            } else {
                modalImagesGallery.innerHTML = '<div class="column is-full"><p>No hay imágenes disponibles para este coche.</p></div>';
            }

            carDetailModal.classList.add('is-active'); // Mostrar el modal

        } catch (error) {
            console.error('Error fetching car details for modal:', error);
            alert('Error al cargar los detalles del coche.');
        }
    }

    function closeCarDetailModal() {
        carDetailModal.classList.remove('is-active');
    }

    // --- Event Listeners ---

    closeModalBtn.addEventListener('click', closeCarDetailModal);
    closeModalFooterBtn.addEventListener('click', closeCarDetailModal);
    carDetailModal.querySelector('.modal-background').addEventListener('click', closeCarDetailModal);

    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            fetchListings(currentPage);
        }
    });

    nextPageBtn.addEventListener('click', () => {
        const totalPages = Math.ceil(totalListings / ITEMS_PER_PAGE);
        if (currentPage < totalPages) {
            currentPage++;
            fetchListings(currentPage);
        }
    });

    searchButton.addEventListener('click', () => {
        currentPage = 1; // Reiniciar página al buscar
        const query = searchInput.value.trim();
        fetchListings(currentPage, ITEMS_PER_PAGE, query);
    });

    searchInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') {
            searchButton.click();
        }
    });


    // --- Carga inicial de datos ---
    fetchAnalysisResults();
    fetchListings(currentPage);
});