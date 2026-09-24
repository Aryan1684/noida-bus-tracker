let map;
let locationMarker;
let userLocation = null;
let confirmedLocation = null;
let busMarkers = [];
let selectedBusId = null;
let refreshInterval = null;
let isLoading = false;
let pinAdjustMode = false;
let searchTimer = null;
let searchController = null;

const API_BASE_URL = "https://noida-bus-tracker.onrender.com";

const BUS_ROUTES = {
    "UP80KT3702": "R1",
    "UP80KT4582": "R1",
    "UP70PT6077": "R1",
    "UP70PT6268": "R1",
    "UP80LT4113": "R1",
    "UP80LT4117": "R1",
    "UP80LT4126": "R1",
    "UP80KT3630": "R1",
    "UP80KT3703": "R1",
    "UP70PT6330": "R1",
    "UP80LT4114": "R1",
    "UP80LT4120": "R1"
};

function getBusRoute(busId) {
    return BUS_ROUTES[String(busId || "").trim().toUpperCase()] || null;
}



document.addEventListener(
    "DOMContentLoaded",
    () => {
        initializeMap();
        initializeWarningModal();

        document
            .getElementById("locationBtn")
            .addEventListener(
                "click",
                getUserLocation
            );

        document
            .getElementById("confirmBtn")
            .addEventListener(
                "click",
                confirmLocation
            );

        document
            .getElementById("refreshBtn")
            .addEventListener(
                "click",
                refreshBuses
            );

        document
            .getElementById("retryBtn")
            .addEventListener(
                "click",
                refreshBuses
            );

        document
            .getElementById("radiusSelect")
            .addEventListener(
                "change",
                () => {
                    if (confirmedLocation) {
                        loadNearbyBuses(
                            confirmedLocation
                        );
                    }
                }
            );

        map.on(
            "click",
            event => {
                if (pinAdjustMode) {
                    setLocationMarker(
                        event.latlng.lat,
                        event.latlng.lng
                    );
                    return;
                }

                clearBusSelection();
            }
        );

        initializePlaceSearch();
        initializePinControl();
    }
);

function initializeWarningModal() {
    const modal =
        document.getElementById(
            "warningModal"
        );

    const acceptButton =
        document.getElementById(
            "warningAcceptBtn"
        );

    const acknowledged =
        localStorage.getItem(
            "movementWarningAcknowledged"
        );

    if (acknowledged === "true") {
        modal.classList.add(
            "hidden"
        );
    }

    acceptButton.addEventListener(
        "click",
        () => {
            localStorage.setItem(
                "movementWarningAcknowledged",
                "true"
            );

            modal.classList.add(
                "hidden"
            );
        }
    );
}

function initializeMap() {
    map =
        L.map("map").setView(
            [
                28.5355,
                77.3910
            ],
            12
        );

    L.tileLayer(
        "https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=zDrcI9pwHS3FLOHuWQm3",
        {
            tileSize: 512,
            zoomOffset: -1,
            minZoom: 1,
            maxZoom: 20,
            attribution:
                "&copy; MapTiler &copy; OpenStreetMap contributors"
        }
    ).addTo(map);
}

function getUserLocation() {
    if (!navigator.geolocation) {
        alert(
            "Geolocation is not supported by your browser."
        );

        return;
    }

    const button =
        document.getElementById(
            "locationBtn"
        );

    button.textContent =
        "Getting Location...";

    button.disabled = true;

    navigator.geolocation.getCurrentPosition(
        position => {
            setLocationMarker(
                position.coords.latitude,
                position.coords.longitude
            );

            showAddress(
                position.coords.latitude,
                position.coords.longitude
            );

            map.setView(
                [
                    position.coords.latitude,
                    position.coords.longitude
                ],
                15
            );

            button.innerHTML =
                "<span>✓</span> Location Found";

            button.disabled = false;
        },
        error => {
            console.error(
                "Location error:",
                error
            );

            button.innerHTML =
                "<span>📍</span> Find Buses Near Me";

            button.disabled = false;

            alert(
                "Unable to get your location. Please allow location access."
            );
        },
        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 30000
        }
    );
}

function setLocationMarker(
    latitude,
    longitude
) {
    userLocation = {
        lat: latitude,
        lon: longitude
    };

    confirmedLocation = null;
    selectedBusId = null;

    if (locationMarker) {
        locationMarker.setLatLng(
            [
                latitude,
                longitude
            ]
        );
    } else {
        const icon =
            L.divIcon({
                className: "",
                html:
                    '<div class="location-marker"></div>',
                iconSize: [
                    32,
                    32
                ],
                iconAnchor: [
                    16,
                    16
                ]
            });

        locationMarker =
            L.marker(
                [
                    latitude,
                    longitude
                ],
                {
                    draggable: true,
                    icon: icon
                }
            ).addTo(map);

        locationMarker.dragging.disable();

        locationMarker.on(
            "dragstart",
            event => {
                if (!pinAdjustMode) {
                    locationMarker.dragging.disable();
                }
            }
        );

        locationMarker.on(
            "dragend",
            event => {
                const position =
                    event.target.getLatLng();

                userLocation = {
                    lat: position.lat,
                    lon: position.lng
                };

                confirmedLocation = null;
                selectedBusId = null;

                clearBusMarkers();

                document.getElementById(
                    "busList"
                ).innerHTML = "";

                hideAllStates();

                document.getElementById(
                    "busCount"
                ).textContent =
                    "0 buses";

                document.getElementById(
                    "refreshBtn"
                ).disabled = true;

                document.getElementById(
                    "confirmBtn"
                ).disabled = false;

                updateLocationMessage(
                    "Pin moved. Confirm this location to find nearby buses."
                );
            }
        );
    }

    locationMarker
        .bindPopup(
            pinAdjustMode ? "Drag to adjust location" : "Location selected"
        )
        .openPopup();

    document.getElementById(
        "confirmBtn"
    ).disabled = false;

    document.getElementById(
        "refreshBtn"
    ).disabled = true;

    updateLocationMessage(
        "Drag the pin to adjust the location, then click Confirm Location."
    );
}

function confirmLocation() {
    if (!userLocation) {
        return;
    }

    confirmedLocation = {
        lat: userLocation.lat,
        lon: userLocation.lon
    };

    selectedBusId = null;

    document.getElementById(
        "confirmBtn"
    ).disabled = true;

    document.getElementById(
        "refreshBtn"
    ).disabled = false;

    updateLocationMessage(
        "Location confirmed. Finding nearby electric buses..."
    );

    loadNearbyBuses(
        confirmedLocation
    );

    startAutoRefresh();
}

function startAutoRefresh() {
    if (refreshInterval) {
        clearInterval(
            refreshInterval
        );
    }

    refreshInterval =
        setInterval(
            () => {
                if (
                    confirmedLocation &&
                    !isLoading
                ) {
                    loadNearbyBuses(
                        confirmedLocation,
                        true
                    );
                }
            },
            45000
        );
}

async function refreshBuses() {
    if (
        !confirmedLocation ||
        isLoading
    ) {
        return;
    }

    await loadNearbyBuses(
        confirmedLocation
    );
}

async function loadNearbyBuses(
    location,
    automaticRefresh = false
) {
    if (
        !location ||
        isLoading
    ) {
        return;
    }

    isLoading = true;

    const radius =
        document.getElementById(
            "radiusSelect"
        ).value;

    const refreshButton =
        document.getElementById(
            "refreshBtn"
        );

    if (!automaticRefresh) {
        refreshButton.disabled =
            true;

        showLoadingState();
    }

    refreshButton.classList.add(
        "loading"
    );

    const url =
        `${API_BASE_URL}/api/buses/nearby` +
        `?lat=${encodeURIComponent(
            location.lat
        )}` +
        `&lon=${encodeURIComponent(
            location.lon
        )}` +
        `&radius=${encodeURIComponent(
            radius
        )}`;

    console.log(
        "Fetching buses:",
        url
    );

    try {
        const response =
            await fetch(url);

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        console.log(
            "Bus response:",
            data
        );

        displayBuses(
            data.buses || []
        );

        updateLastRefreshed();

        if (data.data_stale || (data.buses || []).some(bus => bus.data_stale)) {
            updateLocationMessage(
                `Live GPS temporarily unavailable. Showing the last available bus positions (\${data.count} buses within \${radius} km).`
            );
        } else {
            updateLocationMessage(
                `\${data.count} electric buses found within \${radius} km.`
            );
        }

    } catch (error) {
        console.error(
            "Failed to load buses:",
            error
        );

        const busList =
            document.getElementById(
                "busList"
            );

        if (
            automaticRefresh &&
            busList.children.length > 0
        ) {
            document.getElementById(
                "lastRefreshed"
            ).textContent =
                "Refresh failed";

            updateLocationMessage(
                "Unable to refresh bus data. Showing the previous results."
            );
        } else {
            showErrorState(
                "UPSRTC MARGDARSHI website is currently down. Please try again in 15 minutes."
            );
        }
    } finally {
        isLoading = false;

        refreshButton.classList.remove(
            "loading"
        );

        refreshButton.disabled =
            !confirmedLocation;
    }
}

function displayBuses(buses) {
    clearBusMarkers();

    const busList = document.getElementById("busList");
    const busCount = document.getElementById("busCount");

    buses = (buses || []).slice().sort((a, b) => {
        if (selectedBusId) {
            const aSelected = String(a.bus_id) === String(selectedBusId);
            const bSelected = String(b.bus_id) === String(selectedBusId);

            if (aSelected && !bSelected) return -1;
            if (!aSelected && bSelected) return 1;
        }

        const da = Number(a.distance_km);
        const db = Number(b.distance_km);

        return (Number.isFinite(da) ? da : 9999) - (Number.isFinite(db) ? db : 9999);
    });

    busCount.textContent = buses.length + " buses";
    hideAllStates();
    busList.innerHTML = "";

    if (!buses.length) {
        showEmptyState();
        return;
    }

    buses.forEach((bus, index) => {
        bus._rank = index + 1;
        createBusMarker(bus);
        createBusCard(bus, index);
    });

    if (selectedBusId) highlightBus(selectedBusId);
}

function createBusMarker(bus) {
    const icon = L.divIcon({
        className: "",
        html: `
            <div class="bus-marker" id="marker-${bus.bus_id}" aria-label="Bus ${bus.bus_id}">
                <span class="bus-body">
                    <i class="bus-window"></i>
                    <b class="bus-wheel wheel-left"></b>
                    <b class="bus-wheel wheel-right"></b>
                </span>
            </div>
        `,
        iconSize: [54, 54],
        iconAnchor: [27, 27]
    });

    const marker = L.marker(
        [bus.latitude, bus.longitude],
        { icon: icon }
    ).addTo(map);

    marker.bindPopup(createPopupContent(bus));

    marker.on("click", event => {
        L.DomEvent.stopPropagation(event);
        selectBus(bus.bus_id);
        marker.openPopup();
    });

    marker.busId = bus.bus_id;
    busMarkers.push(marker);
}

function createBusCard(bus, rankIndex = 0) {
    const card =
        document.createElement(
            "div"
        );

    card.className = "bus-card rank-" + Math.min(rankIndex + 1, 3);
    card.style.animationDelay = Math.min(rankIndex * 45, 500) + "ms";

    card.id =
        `bus-card-${bus.bus_id}`;

    card.dataset.distance = Number.isFinite(Number(bus.distance_km))
        ? String(Number(bus.distance_km))
        : "9999";

    let directionHtml;

    const heading =
        Number.isFinite(
            Number(bus.heading)
        )
            ? Number(bus.heading)
            : 0;

    if (bus.likely_towards) {
        directionHtml = `
            <div class="bus-direction">

                <span
                    class="direction-arrow"
                    style="transform: rotate(${heading}deg)"
                >➤</span>

                <div>
                    <small>
                        MOVING TOWARDS
                    </small>

                    <strong>
                        ${bus.likely_towards}
                    </strong>
                </div>

            </div>
        `;
    } else if (bus.direction) {
        directionHtml = `
            <div class="bus-direction">

                <span
                    class="direction-arrow"
                    style="transform: rotate(${heading}deg)"
                >➤</span>

                <div>
                    <small>
                        MOVING
                    </small>

                    <strong>
                        ${bus.direction}
                    </strong>
                </div>

            </div>
        `;
    } else {
        directionHtml = `
            <div class="bus-direction">

                <span class="direction-wait">
                    ⏳
                </span>

                <div>
                    <small>
                        MOVEMENT
                    </small>

                    <strong>
                        Determining...
                    </strong>
                </div>

            </div>
        `;
    }

    const movement =
        bus.movement_km !== undefined
            ? bus.movement_km
            : 0;

    const history =
        bus.history_minutes !== undefined
            ? bus.history_minutes
            : 0;

    const route = getBusRoute(bus.bus_id);

    card.innerHTML = `
        <div class="bus-card-top">
            <span class="bus-rank">#${rankIndex + 1}</span>
            <h3>${bus.bus_id || "Unknown Bus"}</h3>
            ${route ? `<span class="route-badge">R1</span>` : ""}
        </div>

        ${directionHtml}

        <div class="bus-distance">⌖ ${bus.distance_km ?? "—"} km away</div>    <p>
            Speed:
            ${bus.speed ?? 0} km/h
        </p>

        <p>
            Movement:
            ${movement} km
            in ${history} min
        </p>

        <p class="status">
            Status:
            ${formatStatus(
                bus.vehicle_status
            )}
        </p>

        <p class="updated">
            ● Live GPS position
        </p>
    `;

    card.addEventListener(
        "click",
        () => {
            selectBus(
                bus.bus_id
            );

            map.setView(
                [
                    bus.latitude,
                    bus.longitude
                ],
                16
            );

            const marker =
                busMarkers.find(
                    item =>
                        item.busId ===
                        bus.bus_id
                );

            if (marker) {
                marker.openPopup();
            }
        }
    );

    document
        .getElementById(
            "busList"
        )
        .appendChild(card);
}

function selectBus(busId) {
    selectedBusId = busId;

    const list = document.getElementById("busList");
    const selectedCard = document.getElementById(`bus-card-${busId}`);

    if (selectedCard && list && list.firstElementChild !== selectedCard) {
        list.prepend(selectedCard);
    }

    document.querySelectorAll(".bus-card").forEach(card => {
        card.classList.toggle("selected", card.id === `bus-card-${busId}`);
    });

    document.querySelectorAll(".bus-card").forEach((card, index) => {
        const rank = card.querySelector(".bus-rank");
        if (rank) rank.textContent = `#${index + 1}`;
    });

    if (selectedCard) {
        selectedCard.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });
    }

    document.querySelectorAll(".bus-marker").forEach(marker => {
        marker.classList.remove("selected");
    });

    const selectedMarker = document.getElementById(`marker-${busId}`);

    if (selectedMarker) {
        selectedMarker.classList.add("selected");
    }
}

function clearBusSelection() {
    selectedBusId = null;

    document.querySelectorAll(".bus-card.selected").forEach(card => {
        card.classList.remove("selected");
    });

    document.querySelectorAll(".bus-marker.selected").forEach(marker => {
        marker.classList.remove("selected");
    });

    const list = document.getElementById("busList");
    if (list) {
        const cards = Array.from(list.querySelectorAll(".bus-card"));

        cards.sort((a, b) => {
            const aDistance = Number(a.dataset.distance);
            const bDistance = Number(b.dataset.distance);

            return (Number.isFinite(aDistance) ? aDistance : 9999) -
                (Number.isFinite(bDistance) ? bDistance : 9999);
        });

        cards.forEach((card, index) => {
            list.appendChild(card);
            const rank = card.querySelector(".bus-rank");
            if (rank) rank.textContent = `#${index + 1}`;
        });
    }
}

function highlightBus(busId) {
    selectBus(
        busId
    );
}

function createPopupContent(bus) {
    let directionText;

    if (bus.likely_towards) {
        directionText =
            `Moving towards: ${bus.likely_towards}`;
    } else if (bus.direction) {
        directionText =
            `Moving: ${bus.direction}`;
    } else {
        directionText =
            "Movement: Determining...";
    }

    return `
        <strong>
            ${bus.bus_id || "Unknown Bus"}
        </strong>

        <br><br>

        🚌 ${directionText}

        <br>

        Speed:
        ${bus.speed ?? 0} km/h

        <br>

        Distance:
        ${bus.distance_km ?? "Unknown"} km

        <br>

        Movement:
        ${bus.movement_km ?? 0} km
        in ${bus.history_minutes ?? 0} min

        <br>

        Status:
        ${formatStatus(
            bus.vehicle_status
        )}

        <br><br>

        <strong>
            Live GPS position
        </strong>
    `;
}

function clearBusMarkers() {
    busMarkers.forEach(
        marker => {
            map.removeLayer(
                marker
            );
        }
    );

    busMarkers = [];
}

function showLoadingState() {
    hideAllStates();

    document
        .getElementById(
            "loadingState"
        )
        .classList.remove(
            "hidden"
        );
}

function showErrorState(message) {
    hideAllStates();

    document.getElementById(
        "errorMessage"
    ).textContent =
        message;

    document
        .getElementById(
            "errorState"
        )
        .classList.remove(
            "hidden"
        );
}

function showEmptyState() {
    hideAllStates();

    document
        .getElementById(
            "emptyState"
        )
        .classList.remove(
            "hidden"
        );
}

function hideAllStates() {
    document
        .getElementById(
            "loadingState"
        )
        .classList.add(
            "hidden"
        );

    document
        .getElementById(
            "errorState"
        )
        .classList.add(
            "hidden"
        );

    document
        .getElementById(
            "emptyState"
        )
        .classList.add(
            "hidden"
        );
}

function updateLocationMessage(
    message
) {
    document.getElementById(
        "locationMessage"
    ).textContent =
        message;
}

function updateLastRefreshed() {
    const now =
        new Date();

    document.getElementById(
        "lastRefreshed"
    ).textContent =
        `Last checked: ${now.toLocaleTimeString(
            "en-IN",
            {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit"
            }
        )}`;
}

function formatStatus(status) {
    if (!status) {
        return "Unknown";
    }

    return String(status)
        .replace(
            /_/g,
            " "
        )
        .replace(
            /\b\w/g,
            char =>
                char.toUpperCase()
        );
}


function initializePinControl() {
    const button = document.getElementById("adjustPinBtn");
    if (!button) return;

    button.addEventListener("click", () => {
        pinAdjustMode = !pinAdjustMode;

        if (locationMarker) {
            if (pinAdjustMode) {
                locationMarker.dragging.enable();
                button.textContent = "✓ Done adjusting";
                button.classList.add("active");
                updateLocationMessage("Pin adjustment is on. Drag the pin or tap the map.");
            } else {
                locationMarker.dragging.disable();
                button.textContent = "📍 Adjust pin";
                button.classList.remove("active");
                updateLocationMessage("Pin locked. Confirm this location to find nearby buses.");
            }
        } else {
            button.textContent = "📍 Adjust pin";
        }
    });
}

function initializePlaceSearch() {
    const input = document.getElementById("placeSearch");
    const suggestions = document.getElementById("searchSuggestions");
    if (!input || !suggestions) return;

    input.addEventListener("input", () => {
        const query = input.value.trim();
        clearTimeout(searchTimer);

        if (searchController) searchController.abort();

        if (query.length < 2) {
            suggestions.classList.add("hidden");
            suggestions.innerHTML = "";
            return;
        }

        searchTimer = setTimeout(() => searchPlaces(query), 350);
    });

    document.addEventListener("click", event => {
        if (!event.target.closest(".map-search")) {
            suggestions.classList.add("hidden");
        }
    });
}

async function searchPlaces(query) {
    const suggestions = document.getElementById("searchSuggestions");
    if (!suggestions) return;

    searchController = new AbortController();

    try {
        const response = await fetch(
            "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&countrycodes=in&viewbox=77.25,28.70,77.65,28.30&bounded=1&q=" +
            encodeURIComponent(query + ", Noida"),
            {
                headers: {"Accept": "application/json"},
                signal: searchController.signal
            }
        );

        if (!response.ok) throw new Error("Search failed");

        const results = await response.json();

        suggestions.innerHTML = "";

        if (!results.length) {
            suggestions.innerHTML = "<div class='search-empty'>No matching place found</div>";
            suggestions.classList.remove("hidden");
            return;
        }

        results.forEach(result => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "search-result";
            item.innerHTML = "<strong>" + escapeHtml(result.display_name.split(",")[0]) + "</strong><span>" + escapeHtml(result.display_name) + "</span>";

            item.addEventListener("click", () => {
                const lat = Number(result.lat);
                const lon = Number(result.lon);
                setLocationMarker(lat, lon);
                map.setView([lat, lon], 15, {animate: true, duration: 0.7});
                input.value = result.display_name.split(",")[0];
                suggestions.classList.add("hidden");
                pinAdjustMode = false;
                if (locationMarker) locationMarker.dragging.disable();
                const button = document.getElementById("adjustPinBtn");
                if (button) {
                    button.textContent = "📍 Adjust pin";
                    button.classList.remove("active");
                }
            });

            suggestions.appendChild(item);
        });

        suggestions.classList.remove("hidden");
    } catch (error) {
        if (error.name !== "AbortError") {
            suggestions.innerHTML = "<div class='search-empty'>Search is temporarily unavailable</div>";
            suggestions.classList.remove("hidden");
        }
    }
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({
        "&":"&amp;",
        "<":"&lt;",
        ">":"&gt;",
        '"':"&quot;",
        "'":"&#039;"
    }[char]));
}


async function showAddress(latitude, longitude) {
    const message = document.getElementById("locationMessage");
    if (!message) return;

    message.textContent = "Finding your current address...";

    try {
        const response = await fetch(
            "https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=" +
            encodeURIComponent(latitude) +
            "&lon=" +
            encodeURIComponent(longitude) +
            "&zoom=18&addressdetails=1"
        );

        if (!response.ok) throw new Error("Reverse geocoding failed");

        const data = await response.json();
        const address = data.display_name || "Current location selected";
        message.textContent = "Current location: " + address;
        const input = document.getElementById("placeSearch");
        if (input && !input.value) {
            input.value = address.split(",").slice(0, 2).join(", ");
        }
    } catch (error) {
        message.textContent = "Current location selected. Adjust the pin if needed.";
    }
}
