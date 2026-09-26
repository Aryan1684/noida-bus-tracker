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
let currentBuses = [];

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
        initializeTradeFairNotice();
        initializeTradeFairControls();

        const locationButton = document.getElementById("locationBtn");
        if (locationButton) {
            locationButton.addEventListener("click", () => getUserLocation("locationBtn"));
        }

        const finderLocationButton = document.getElementById("finderLocationBtn");
        if (finderLocationButton) {
            finderLocationButton.addEventListener("click", () => getUserLocation("finderLocationBtn"));
        }

        const mapLocationButton = document.getElementById("mapLocateBtn");
        if (mapLocationButton) {
            mapLocationButton.addEventListener("click", () => getUserLocation("mapLocateBtn"));
        }



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

        const selectedBusClose = document.getElementById("selectedBusClose");
        if (selectedBusClose) selectedBusClose.addEventListener("click", closeSelectedBusPanel);

        const selectedShareBtn = document.getElementById("selectedShareBtn");
        if (selectedShareBtn) {
            selectedShareBtn.addEventListener("click", () => {
                const bus = currentBuses.find(item => String(item.bus_id) === String(selectedBusId));
                if (bus && typeof navigator.share === "function") {
                    navigator.share({title:"Noida Bus " + bus.bus_id,text:"Track this Noida Electric Bus",url:location.origin + location.pathname + "?bus=" + encodeURIComponent(bus.bus_id)}).catch(() => {});
                } else if (bus && navigator.clipboard) {
                    const url = location.origin + location.pathname + "?bus=" + encodeURIComponent(bus.bus_id);
                    navigator.clipboard.writeText(url).then(() => updateLocationMessage("Live bus link copied."));
                }
            });
        }

        const selectedFollowBtn = document.getElementById("selectedFollowBtn");
        if (selectedFollowBtn) {
            selectedFollowBtn.addEventListener("click", () => {
                const bus = currentBuses.find(item => String(item.bus_id) === String(selectedBusId));
                if (!bus) return;
                selectBus(bus.bus_id);
                updateLocationMessage("Selected " + bus.bus_id + ". Use the Follow action in the bus tools below.");
            });
        }

        const shareLocationBtn = document.getElementById("shareLocationBtn");
        if (shareLocationBtn) {
            shareLocationBtn.addEventListener("click", () => {
                const target = confirmedLocation || userLocation;
                if (!target) {
                    updateLocationMessage("Select or detect a location first.");
                    return;
                }
                const url = location.origin + location.pathname + "?lat=" + encodeURIComponent(target.lat) + "&lon=" + encodeURIComponent(target.lon);
                if (navigator.share) {
                    navigator.share({title:"Noida Bus Tracker",text:"Open this map location in Noida Bus Tracker.",url}).catch(() => {});
                } else if (navigator.clipboard) {
                    navigator.clipboard.writeText(url).then(() => updateLocationMessage("Map location link copied."));
                }
            });
        }
    }
);

function initializeTradeFairNotice() {
    localStorage.removeItem("tradeFairNoticeDismissed");
    const notice = document.getElementById("tradeFairNotice");
    const countdown = document.getElementById("tradeFairCountdown");
    if (!notice || !countdown) return;

    const start = new Date("2026-09-25T00:00:00+05:30");
    const end = new Date("2026-09-30T00:00:00+05:30");

    const update = () => {
        const now = new Date();

        if (now < start || now >= end) {
            notice.classList.add("hidden");
            return;
        }

        if (sessionStorage.getItem("tradeFairNoticeDismissed") === "true") {
            notice.classList.add("hidden");
            return;
        }

        notice.classList.remove("hidden");

        const totalSeconds = Math.max(0, Math.floor((end - now) / 1000));
        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        countdown.textContent =
            days + "d " +
            String(hours).padStart(2, "0") + "h " +
            String(minutes).padStart(2, "0") + "m " +
            String(seconds).padStart(2, "0") + "s";
    };

    update();
    setInterval(update, 1000);
}

function initializeTradeFairControls() {
    const notice = document.getElementById("tradeFairNotice");
    const closeButton = document.getElementById("tradeFairClose");
    const routesButton = document.getElementById("tradeFairRoutesToggle");
    const routes = document.getElementById("tradeFairRoutes");

    if (!notice) return;

    if (sessionStorage.getItem("tradeFairNoticeDismissed") === "true") {
        notice.classList.add("hidden");
    }

    if (closeButton) {
        closeButton.addEventListener("click", () => {
            notice.classList.add("hidden");
            sessionStorage.setItem("tradeFairNoticeDismissed", "true");
        });
    }

    if (routesButton && routes) {
        routesButton.addEventListener("click", () => {
            const expanded = routesButton.getAttribute("aria-expanded") === "true";
            routesButton.setAttribute("aria-expanded", String(!expanded));
            routes.classList.toggle("hidden", expanded);
            routesButton.querySelector(".trade-fair-chevron").textContent = expanded ? "⌄" : "⌃";
        });
    }
}

function initializeWarningModal() {
    const modal =
        document.getElementById(
            "warningModal"
        );

    if (!modal) return;

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


function setLocationButtonState(buttonId, state, message) {
    const button = document.getElementById(buttonId);
    if (!button) return;

    window.clearTimeout(button._locationStateTimer);

    const label = button.querySelector(".location-button-label");
    const originalText = button.dataset.originalText || "Use my location";

    button.classList.remove("location-loading", "location-success", "location-error");
    button.disabled = false;

    if (label) label.textContent = originalText;
    else button.textContent = originalText;

    if (state === "loading") {
        button.disabled = true;
        button.classList.add("location-loading");
        return;
    }

    if (state === "success") {
        button.classList.add("location-success");
        button._locationStateTimer = window.setTimeout(() => {
            if (label) label.textContent = "✓ Location found";
            else button.textContent = "✓ Location found";
        }, 1450);
        return;
    }

    if (state === "error") {
        button.classList.add("location-error");
        const errorText = message || "Location unavailable";
        button._locationStateTimer = window.setTimeout(() => {
            if (label) label.textContent = errorText;
            else button.textContent = errorText;
        }, 1200);
    }
}

function getUserLocation(buttonId = "locationBtn") {
    if (!navigator.geolocation) {
        updateLocationMessage("Your browser does not support location access.");
        return;
    }

    const buttons = [
        document.getElementById("locationBtn"),
        document.getElementById("finderLocationBtn"),
        document.getElementById("mapLocateBtn")
    ].filter(Boolean);

    const activeButton = document.getElementById(buttonId);

    buttons.forEach(button => {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
    });

    if (activeButton) {
        activeButton.dataset.originalText = activeButton.textContent;
        if (!activeButton.querySelector(".location-button-label")) {
            if (!activeButton.querySelector(".location-button-label")) {
                const labelNode = document.createElement("span");
                labelNode.className = "location-button-label";
                labelNode.textContent = activeButton.dataset.originalText;
                activeButton.textContent = "";
                activeButton.appendChild(labelNode);
            }
        }
        setLocationButtonState(buttonId, "loading");
    }

    updateLocationMessage("Requesting your current location...");

    navigator.geolocation.getCurrentPosition(
        position => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            setLocationMarker(lat, lon);
            confirmedLocation = { lat, lon };
            selectedBusId = null;

            const input = document.getElementById("placeSearch");
            if (input) input.value = "";

            const refreshButton = document.getElementById("refreshBtn");
            if (refreshButton) refreshButton.disabled = false;

            const dot = document.getElementById("locationStatusDot");
            if (dot) dot.classList.add("ready");

            updateLocationMessage("Location found. Finding nearby electric buses...");
            loadNearbyBuses(confirmedLocation);
            startAutoRefresh();

            map.setView([lat, lon], 15, { animate: true, duration: 0.5 });
            showAddress(lat, lon);

            buttons.forEach(button => {
                button.disabled = false;
                if (button.id !== buttonId) {
                    button.classList.remove("location-success", "location-loading");
                    button.textContent = button.dataset.originalText || button.textContent;
                }
            });
            setLocationButtonState(buttonId, "success");
        },
        error => {
            console.error("Location error:", error);

            let message = "Unable to get your location.";
            if (error.code === 1) {
                message = "Location permission was denied. Allow location access for this site and try again.";
            } else if (error.code === 2) {
                message = "Your location could not be determined. Check device location services and try again.";
            } else if (error.code === 3) {
                message = "Location request timed out. Try again.";
            }

            updateLocationMessage(message);

            buttons.forEach(button => {
                if (button.id === buttonId) {
                    const errorLabel = error.code === 1 ? "Location denied" : error.code === 2 ? "Location unavailable" : "Try again";
                    if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
                    if (!button.querySelector(".location-button-label")) {
                    if (!button.querySelector(".location-button-label")) {
                        const labelNode = document.createElement("span");
                        labelNode.className = "location-button-label";
                        labelNode.textContent = button.dataset.originalText;
                        button.textContent = "";
                        button.appendChild(labelNode);
                    }
                    }
                    setLocationButtonState(buttonId, "error", errorLabel);
                } else {
                    button.disabled = false;
                    button.classList.remove("location-success", "location-error", "location-loading");
                    button.textContent = button.dataset.originalText || "Use my location";
                }
            });
        },
        {
            enableHighAccuracy: true,
            timeout: 20000,
            maximumAge: 60000
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

                const refreshButton = document.getElementById("refreshBtn");
                if (refreshButton) refreshButton.disabled = false;
                confirmedLocation = { lat: position.lat, lon: position.lng };
                updateLocationMessage("Pin moved. Finding nearby electric buses...");
                loadNearbyBuses(confirmedLocation);
                startAutoRefresh();
            }
        );
    }

    locationMarker
        .bindPopup(
            pinAdjustMode ? "Drag to adjust location" : "Location selected"
        )
        .openPopup();

    const refreshButton = document.getElementById("refreshBtn");
    if (refreshButton) refreshButton.disabled = !confirmedLocation;
    const dot = document.getElementById("locationStatusDot");
    if (dot) dot.classList.add("ready");
    updateLocationMessage(confirmedLocation ? "Location selected. Finding nearby electric buses..." : "Location selected.");
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
                `Live GPS temporarily unavailable. Showing the last available bus positions (${data.count} buses within ${radius} km).`
            );
        } else {
            updateLocationMessage(
                `${data.count} electric buses found within ${radius} km.`
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
    const resultsSection = document.querySelector(".results-section");
    if (resultsSection) {
        resultsSection.classList.remove("is-loading");
        resultsSection.classList.remove("is-empty");
    }

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

    currentBuses = buses.slice();
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
    const card = document.createElement("div");
    card.className = "bus-card rank-" + Math.min(rankIndex + 1, 3);
    card.style.animationDelay = Math.min(rankIndex * 35, 400) + "ms";
    card.id = "bus-card-" + bus.bus_id;
    card.dataset.distance = Number.isFinite(Number(bus.distance_km)) ? String(Number(bus.distance_km)) : "9999";

    const heading = Number.isFinite(Number(bus.heading)) ? Number(bus.heading) : 0;
    let directionHtml;

    if (bus.likely_towards) {
        directionHtml = "<div class='bus-direction'><span class='direction-arrow' style='transform:rotate(" + heading + "deg)'>➤</span><div><small>MOVING TOWARDS</small><strong>" + escapeHtml(bus.likely_towards) + "</strong></div></div>";
    } else if (bus.direction) {
        directionHtml = "<div class='bus-direction'><span class='direction-arrow' style='transform:rotate(" + heading + "deg)'>➤</span><div><small>MOVING</small><strong>" + escapeHtml(bus.direction) + "</strong></div></div>";
    } else {
        directionHtml = "<div class='bus-direction'><span class='direction-wait'>⏳</span><div><small>MOVEMENT</small><strong>Determining...</strong></div></div>";
    }

    const route = getBusRoute(bus.bus_id);
    const status = formatStatus(bus.vehicle_status);
    const movement = bus.movement_km !== undefined ? bus.movement_km : 0;
    const history = bus.history_minutes !== undefined ? bus.history_minutes : 0;
    const sourceLabel = bus.data_stale ? "Last available GPS" : "Live GPS";

    card.innerHTML =
        "<div class='bus-card-top'>" +
            "<h3>" + escapeHtml(bus.bus_id || "Unknown Bus") + "</h3>" +
            (route ? "<span class='route-badge'>" + escapeHtml(route) + "</span>" : "") +
            "<span class='bus-rank'>#" + (rankIndex + 1) + "</span>" +
        "</div>" +
        directionHtml +
        "<div class='bus-meta-row'>" +
            "<span class='bus-meta'>⌖ " + (bus.distance_km ?? "—") + " km</span>" +
            "<span class='bus-meta'>⚡ " + (bus.speed ?? 0) + " km/h</span>" +
            "<span class='bus-meta'>↗ " + movement + " km / " + history + " min</span>" +
        "</div>" +
        "<p class='status'>● " + escapeHtml(status) + "</p>" +
        "<p class='updated'>" + sourceLabel + " · Tap for details</p>";

    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", "Bus " + (bus.bus_id || "unknown") + " at " + (bus.distance_km ?? "unknown") + " kilometres");
    const openBus = () => {
        selectBus(bus.bus_id);
        map.setView([bus.latitude, bus.longitude], 16, {animate:true,duration:.35});
        const marker = busMarkers.find(item => String(item.busId) === String(bus.bus_id));
        if (marker) marker.openPopup();
    };
    card.addEventListener("click", openBus);
    card.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openBus();
        }
    });

    document.getElementById("busList").appendChild(card);
}

function selectBus(busId) {
    selectedBusId = busId;

    const list = document.getElementById("busList");
    const selectedCard = document.getElementById("bus-card-" + busId);

    if (selectedCard && list && list.firstElementChild !== selectedCard) {
        list.prepend(selectedCard);
    }

    document.querySelectorAll(".bus-card").forEach(card => {
        card.classList.toggle("selected", card.id === "bus-card-" + busId);
    });

    document.querySelectorAll(".bus-card").forEach((card, index) => {
        const rank = card.querySelector(".bus-rank");
        if (rank) rank.textContent = "#" + (index + 1);
    });

    document.querySelectorAll(".bus-marker").forEach(marker => {
        marker.classList.remove("selected");
    });

    const selectedMarker = document.getElementById("marker-" + busId);
    if (selectedMarker) selectedMarker.classList.add("selected");

    const bus = currentBuses.find(item => String(item.bus_id) === String(busId));
    updateSelectedBusPanel(bus);

    if (selectedCard) {
        selectedCard.scrollIntoView({behavior:"smooth",block:"nearest"});
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

    clearBusMarkers();
    currentBuses = [];
    selectedBusId = null;

    const busList = document.getElementById("busList");
    if (busList) busList.replaceChildren();

    updateSelectedBusPanel(null);

    const resultsSection = document.querySelector(".results-section");
    if (resultsSection) resultsSection.classList.add("is-loading");

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

    const resultsSection = document.querySelector(".results-section");
    if (resultsSection) resultsSection.classList.add("is-empty");

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

    const resultsSection = document.querySelector(".results-section");
    if (resultsSection) resultsSection.classList.remove("is-loading");
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
                button.textContent = "Done";
                button.classList.add("active");
                updateLocationMessage("Drag the pin to move the search area.");
            } else {
                locationMarker.dragging.disable();
                button.textContent = "Move pin";
                button.classList.remove("active");
                updateLocationMessage("Pin locked.");
            }
        } else {
            button.textContent = "Move pin";
        }
    });
}

function initializePlaceSearch() {
    const input = document.getElementById("placeSearch");
    const suggestions = document.getElementById("searchSuggestions");
    if (!input || !suggestions) return;

    input.addEventListener("input", () => {
        const clearButton = document.getElementById("clearSearch");
        if (clearButton) clearButton.classList.toggle("hidden", input.value.trim().length === 0);
        const query = input.value.trim();
        clearTimeout(searchTimer);

        if (searchController) searchController.abort();

        if (query.length < 2) {
            suggestions.classList.add("hidden");
            suggestions.innerHTML = "";
            return;
        }

        searchTimer = setTimeout(() => searchPlaces(query), 180);
    });

    const clearButton = document.getElementById("clearSearch");
    if (clearButton) {
        clearButton.addEventListener("click", () => {
            input.value = "";
            suggestions.innerHTML = "";
            suggestions.classList.add("hidden");
            clearButton.classList.add("hidden");
            input.focus();
        });
    }

    document.addEventListener("click", event => {
        if (!event.target.closest(".search-wrap")) {
            suggestions.classList.add("hidden");
        }
    });
}

const LOCAL_PLACES = [
    { name: "Botanical Garden, Noida", latitude: 28.5672, longitude: 77.3346 },
    { name: "Sector 37, Noida", latitude: 28.5650, longitude: 77.3440 },
    { name: "Noida City Center", latitude: 28.5740, longitude: 77.3560 },
    { name: "Sector 52, Noida", latitude: 28.5850, longitude: 77.3700 },
    { name: "Parthala, Noida", latitude: 28.6075, longitude: 77.3755 },
    { name: "Chaar Murti, Greater Noida West", latitude: 28.6020, longitude: 77.4180 },
    { name: "Ek Murti, Greater Noida West", latitude: 28.6063, longitude: 77.4337 },
    { name: "Surajpur, Greater Noida", latitude: 28.5185, longitude: 77.4990 },
    { name: "Pari Chowk, Greater Noida", latitude: 28.4652, longitude: 77.5080 }
];

function renderPlaceSuggestions(results, input, suggestions) {
    suggestions.innerHTML = "";

    if (!results.length) {
        suggestions.innerHTML = "<div class='search-empty'>No matching place found</div>";
        return;
    }

    results.slice(0, 7).forEach(result => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "search-result";

        const label = result.name || "Unnamed place";
        item.innerHTML =
            "<strong>" + escapeHtml(label.split(",")[0]) + "</strong>" +
            "<span>" + escapeHtml(label) + "</span>";

        item.addEventListener("click", () => {
            const lat = Number(result.latitude);
            const lon = Number(result.longitude);
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

            setLocationMarker(lat, lon);
            confirmedLocation = { lat, lon };

            const refreshButton = document.getElementById("refreshBtn");
            if (refreshButton) refreshButton.disabled = false;

            updateLocationMessage("Place selected. Finding nearby electric buses...");
            loadNearbyBuses(confirmedLocation);
            startAutoRefresh();

            map.setView([lat, lon], 15, { animate: true, duration: 0.5 });

            input.value = label;
            suggestions.classList.add("hidden");
            pinAdjustMode = false;

            const button = document.getElementById("adjustPinBtn");
            if (button) {
                button.textContent = "Move pin";
                button.classList.remove("active");
            }

            if (locationMarker) locationMarker.dragging.disable();
        });

        suggestions.appendChild(item);
    });
}

async function searchPlaces(query) {
    const input = document.getElementById("placeSearch");
    const suggestions = document.getElementById("searchSuggestions");
    if (!input || !suggestions) return;

    if (searchController) searchController.abort();
    searchController = new AbortController();

    input.setAttribute("aria-busy", "true");

    const q = query.toLowerCase();
    const localResults = LOCAL_PLACES.filter(place =>
        place.name.toLowerCase().includes(q)
    );

    renderPlaceSuggestions(localResults, input, suggestions);
    suggestions.classList.remove("hidden");

    const timeoutId = setTimeout(() => searchController.abort(), 4500);

    try {
        const response = await fetch(
            API_BASE_URL + "/api/search-location?q=" + encodeURIComponent(query),
            { signal: searchController.signal }
        );

        let externalResults = [];

        if (response.ok) {
            const data = await response.json();
            externalResults = Array.isArray(data.results) ? data.results : [];
        }

        if (!externalResults.length) {
            const fallbackResponse = await fetch(
                "https://nominatim.openstreetmap.org/search?format=jsonv2&q=" +
                encodeURIComponent(query) +
                "&countrycodes=in&limit=5&addressdetails=1",
                {
                    signal: searchController.signal,
                    headers: { "Accept": "application/json" }
                }
            );

            if (fallbackResponse.ok) {
                const fallbackData = await fallbackResponse.json();
                externalResults = fallbackData.map(item => ({
                    name: item.display_name,
                    latitude: Number(item.lat),
                    longitude: Number(item.lon)
                }));
            }
        }

        const seen = new Set();
        const merged = [...localResults, ...externalResults].filter(result => {
            const key = String(result.name || "").toLowerCase();
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        renderPlaceSuggestions(merged, input, suggestions);
        suggestions.classList.remove("hidden");
    } catch (error) {
        if (error.name !== "AbortError" && !localResults.length) {
            suggestions.innerHTML = "<div class='search-empty'>Search is temporarily unavailable</div>";
            suggestions.classList.remove("hidden");
        }
    } finally {
        clearTimeout(timeoutId);
        input.setAttribute("aria-busy", "false");
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
        if (!confirmedLocation) message.textContent = "Current location selected.";
        const input = document.getElementById("placeSearch");
        if (input && !input.value) {
            input.value = address.split(",").slice(0, 2).join(", ");
        }
    } catch (error) {
        if (!confirmedLocation) message.textContent = "Current location selected.";
    }
}


function updateSelectedBusPanel(bus) {
    const panel = document.getElementById("selectedBusPanel");
    if (!panel) return;

    if (!bus) {
        panel.classList.add("hidden");
        return;
    }

    const idNode = document.getElementById("selectedBusId");
    const routeNode = document.getElementById("selectedBusRoute");
    const statusNode = document.getElementById("selectedBusStatus");
    const directionNode = document.getElementById("selectedBusDirection");
    const arrowNode = document.getElementById("selectedBusArrow");
    const distanceNode = document.getElementById("selectedBusDistance");
    const speedNode = document.getElementById("selectedBusSpeed");
    const movementNode = document.getElementById("selectedBusMovement");
    const followButton = document.getElementById("selectedFollowBtn");

    if (idNode) idNode.textContent = bus.bus_id || "Unknown Bus";
    if (routeNode) {
        const route = getBusRoute(bus.bus_id);
        routeNode.textContent = route ? route : "";
        routeNode.classList.toggle("hidden", !route);
    }
    if (statusNode) statusNode.textContent = bus.data_stale ? "LAST AVAILABLE" : "LIVE";
    if (directionNode) directionNode.textContent = bus.likely_towards || bus.direction || "Determining...";
    if (arrowNode && Number.isFinite(Number(bus.heading))) arrowNode.style.transform = "rotate(" + Number(bus.heading) + "deg)";
    if (distanceNode) distanceNode.textContent = (bus.distance_km ?? "—") + " km away";
    if (speedNode) speedNode.textContent = (bus.speed ?? 0) + " km/h";
    if (movementNode) movementNode.textContent = (bus.movement_km ?? 0) + " km / " + (bus.history_minutes ?? 0) + " min";
    if (followButton) followButton.textContent = "Follow bus";

    panel.classList.remove("hidden");
}

function closeSelectedBusPanel() {
    selectedBusId = null;
    updateSelectedBusPanel(null);
    clearBusSelection();
}
