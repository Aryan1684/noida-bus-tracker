let map;
let locationMarker;
let userLocation = null;
let confirmedLocation = null;
let busMarkers = [];
let selectedBusId = null;
let refreshInterval = null;
const busMarkerAnimations = new Map();
const BUS_MARKER_ANIMATION_MS = 4200;
let isLoading = false;
let pinAdjustMode = false;
let searchTimer = null;
let searchController = null;
let currentBuses = [];
let routeCatalog = [];
let selectedRouteLayer = null;
let favoriteBusIds = new Set(JSON.parse(localStorage.getItem("noidaBusFavorites") || "[]"));

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

function getBusFreshness(bus) {
    const rawAge = bus && bus.gps_age_seconds;
    const ageSeconds = rawAge !== undefined && rawAge !== null && rawAge !== ""
        ? Number(rawAge)
        : NaN;
    const hasAge = Number.isFinite(ageSeconds) && ageSeconds >= 0;
    const staleFlag = bus && (
        bus.data_stale === true ||
        bus.data_stale === 1 ||
        String(bus.data_stale).toLowerCase() === "true"
    );
    const stale = Boolean(staleFlag) || (hasAge && ageSeconds > 120);
    const ageLabel = hasAge
        ? ageSeconds < 60
            ? "Updated " + Math.round(ageSeconds) + "s ago"
            : "Updated " + Math.round(ageSeconds / 60) + "m ago"
        : "GPS timestamp unavailable";
    const sourceLabel = stale
        ? "Last known location"
        : hasAge
        ? "Live GPS"
        : "GPS freshness unknown";

    return {ageSeconds, hasAge, stale, ageLabel, sourceLabel};
}

function getBusMovementState(bus) {
    const status = String(bus && bus.vehicle_status || "").toLowerCase();
    const movementStatus = String(bus && bus.movement_status || "").toLowerCase();
    const rawSpeed = bus && bus.speed;
    const speed = rawSpeed !== undefined && rawSpeed !== null && rawSpeed !== ""
        ? Number(rawSpeed)
        : NaN;
    const rawMovement = bus && bus.movement_km;
    const movement = rawMovement !== undefined && rawMovement !== null && rawMovement !== ""
        ? Number(rawMovement)
        : NaN;

    if (status === "no_signal") {
        return "no_signal";
    }

    if (Number.isFinite(speed) && speed >= 5) {
        return "moving";
    }

    if (movementStatus === "moving") {
        return "moving";
    }

    if (status === "stationary") {
        return "stationary";
    }

    if (Number.isFinite(speed) && speed <= 1.5) {
        return "stationary";
    }

    if (Number.isFinite(movement) && movement >= 0.08) {
        return "moving";
    }

    return "unknown";
}

function isBusMoving(bus) {
    return getBusMovementState(bus) === "moving";
}

function compareBusRanking(a, b) {
    const aMoving = isBusMoving(a);
    const bMoving = isBusMoving(b);

    if (aMoving !== bMoving) {
        return aMoving ? -1 : 1;
    }

    const da = Number(a.distance_km);
    const db = Number(b.distance_km);

    return (Number.isFinite(da) ? da : 9999) -
        (Number.isFinite(db) ? db : 9999);
}



function initializeAppComingSoon() {
    const openButton = document.getElementById("appComingSoonBtn");
    const modal = document.getElementById("appComingSoonModal");
    const closeButton = document.getElementById("appComingSoonClose");
    const okayButton = document.getElementById("appComingSoonOkay");

    if (!openButton || !modal) return;

    function open() {
        modal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
        if (closeButton) closeButton.focus();
        if (window.noidaBusAnalytics && window.noidaBusAnalytics.track) {
            window.noidaBusAnalytics.track("pwa_install", {source:"android_app_button"});
        }
    }

    function close() {
        modal.classList.add("hidden");
        document.body.style.overflow = "";
        openButton.focus();
    }

    openButton.addEventListener("click", open);
    if (closeButton) closeButton.addEventListener("click", close);
    if (okayButton) okayButton.addEventListener("click", close);

    modal.addEventListener("click", event => {
        if (event.target === modal) close();
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !modal.classList.contains("hidden")) {
            close();
        }
    });
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        initializeMap();
        initializeRouteCatalog();
        initializeAppComingSoon();
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
    const modal = document.getElementById("warningModal");
    if (!modal) return;

    const acceptButton = document.getElementById("warningAcceptBtn");
    const feedbackButton = document.getElementById("warningFeedbackBtn");

    modal.classList.remove("hidden");

    function close() {
        modal.classList.add("hidden");
    }

    if (acceptButton) {
        acceptButton.addEventListener("click", close);
    }

    if (feedbackButton) {
        feedbackButton.addEventListener("click", () => {
            close();
            const siteFeedbackButton = document.getElementById("feedbackBtn");
            if (siteFeedbackButton) {
                window.setTimeout(() => siteFeedbackButton.click(), 350);
            }
        });
    }

    modal.addEventListener("click", event => {
        if (event.target === modal) close();
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !modal.classList.contains("hidden")) {
            close();
        }
    });
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
            if (label) label.textContent = "Location found";
            else button.textContent = "Location found";
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
        refreshButton.disabled = true;
        if (!currentBuses.length) {
            showLoadingState();
        } else {
            updateLocationMessage("Refreshing GPS data… current verified positions remain visible.");
            document.querySelector(".results-section")?.classList.add("is-refreshing");
        }
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
        )}` +
        `&_refresh=${Date.now()}`;

    try {
        let data;
        try {
            const response = await fetch(url, { cache: "no-store", mode: "cors" });
            if (!response.ok) {
                const detail = await response.text().catch(() => "");
                throw new Error("Nearby API HTTP " + response.status + ": " + detail.slice(0, 250));
            }
            data = await response.json();
        } catch (nearbyError) {
            console.error("Nearby API failed; falling back to all-buses API:", nearbyError);
            const fallbackResponse = await fetch(API_BASE_URL + "/api/buses?_refresh=" + Date.now(), {
                cache: "no-store",
                mode: "cors"
            });
            if (!fallbackResponse.ok) {
                const detail = await fallbackResponse.text().catch(() => "");
                throw new Error("Nearby and all-buses APIs failed. Fallback HTTP " + fallbackResponse.status + ": " + detail.slice(0, 250));
            }
            const fallbackData = await fallbackResponse.json();
            const allBuses = Array.isArray(fallbackData) ? fallbackData : (fallbackData.buses || []);
            const toRadians = value => value * Math.PI / 180;
            const distanceKm = (lat1, lon1, lat2, lon2) => {
                const dLat = toRadians(lat2 - lat1);
                const dLon = toRadians(lon2 - lon1);
                const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
                return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            };
            data = {
                buses: allBuses.filter(bus => {
                    const lat = Number(bus.latitude);
                    const lon = Number(bus.longitude);
                    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
                    const distance = distanceKm(location.lat, location.lon, lat, lon);
                    if (distance > Number(radius)) return false;
                    bus.distance_km = Math.round(distance * 100) / 100;
                    return true;
                }),
                count: 0,
                total_buses: allBuses.length,
                fallback: true
            };
            data.count = data.buses.length;
            console.warn("Using client-side nearby filtering fallback.", {total: data.total_buses, nearby: data.count});
        }
        displayBuses(data.buses || []);

        updateLastRefreshed();

        if (data.fallback) {
            updateLocationMessage("Showing " + data.count + " nearby buses using the direct GPS feed.");
        } else if (data.count === 0 && data.total_buses === 0) {
            updateLocationMessage("No Noida Electric buses are currently present in the live feed. The feed may be temporarily empty.");
        } else if (data.count === 0) {
            updateLocationMessage(`No electric buses found within ${radius} km. ${data.total_buses} buses are present in the wider feed.`);
        } else if (data.data_stale || (data.buses || []).some(bus => bus.data_stale)) {
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
            const message = error.message === "BUS_DATA_WARMING"
                ? "Bus data is warming up after a restart. Please retry in a few seconds."
                : error.message === "BUS_DATA_EXPIRED"
                ? "Live bus data has not refreshed in time. The upstream feed may be unavailable; please retry shortly."
                : (error && error.message ? "Unable to load bus data: " + error.message : "Unable to load bus data right now. Please retry in a few seconds.");
            showErrorState(message);
        }
    } finally {
        isLoading = false;

        refreshButton.classList.remove("loading");
        document.querySelector(".results-section")?.classList.remove("is-refreshing");
        refreshButton.disabled = !confirmedLocation;
    }
}

function displayBuses(buses) {
    const resultsSection = document.querySelector(".results-section");
    if (resultsSection) {
        resultsSection.classList.remove("is-loading");
        resultsSection.classList.remove("is-empty");
    }

    const busList = document.getElementById("busList");
    const busCount = document.getElementById("busCount");

    buses = (buses || []).slice().sort((a, b) => {
        if (selectedBusId) {
            const aSelected = String(a.bus_id) === String(selectedBusId);
            const bSelected = String(b.bus_id) === String(selectedBusId);

            if (aSelected && !bSelected) return -1;
            if (!aSelected && bSelected) return 1;
        }

        return compareBusRanking(a, b);
    });

    currentBuses = buses.slice();
    busCount.textContent = buses.length + " buses";
    hideAllStates();
    const existingCards = new Map(
        Array.from(busList.querySelectorAll(".bus-card")).map(card => [
            card.id,
            card
        ])
    );

    if (!buses.length) {
        clearBusMarkers();
        busList.replaceChildren();
        showEmptyState();
        return;
    }

    const nextIds = new Set();

    buses.forEach((bus, index) => {
        bus._rank = index + 1;
        nextIds.add(String(bus.bus_id));
        updateOrCreateBusMarker(bus);
        const existing = existingCards.get("bus-card-" + bus.bus_id);
        if (existing) existing.remove();
        createBusCard(bus, index);
    });

    Array.from(existingCards.values()).forEach(card => {
        if (!nextIds.has(String(card.dataset.busId || ""))) card.remove();
    });

    if (selectedBusId) highlightBus(selectedBusId);
}

function getBusDisplayPosition(bus) {
    const predictedLatitude = Number(bus.display_latitude);
    const predictedLongitude = Number(bus.display_longitude);

    if (
        bus.prediction_applied &&
        Number.isFinite(predictedLatitude) &&
        Number.isFinite(predictedLongitude)
    ) {
        return {
            latitude: predictedLatitude,
            longitude: predictedLongitude
        };
    }

    return {
        latitude: Number(bus.latitude),
        longitude: Number(bus.longitude)
    };
}

function animateBusMarker(marker, targetPosition) {
    const target = L.latLng(targetPosition.latitude, targetPosition.longitude);
    const from = marker.getLatLng();
    const distance = map.distance(from, target);

    if (!Number.isFinite(distance) || distance < 2) {
        marker.setLatLng(target);
        return;
    }

    const state = busMarkerAnimations.get(marker.busId);
    if (state?.frame) cancelAnimationFrame(state.frame);

    const startedAt = performance.now();
    const start = {lat: from.lat, lng: from.lng};

    const tick = now => {
        const progress = Math.min(1, (now - startedAt) / BUS_MARKER_ANIMATION_MS);
        const eased = progress < 0.5
            ? 2 * progress * progress
            : 1 - Math.pow(-2 * progress + 2, 2) / 2;

        marker.setLatLng([
            start.lat + (target.lat - start.lat) * eased,
            start.lng + (target.lng - start.lng) * eased
        ]);

        if (progress < 1) {
            const frame = requestAnimationFrame(tick);
            busMarkerAnimations.set(marker.busId, {frame});
        } else {
            busMarkerAnimations.delete(marker.busId);
        }
    };

    const frame = requestAnimationFrame(tick);
    busMarkerAnimations.set(marker.busId, {frame});
}

function updateOrCreateBusMarker(bus) {
    const existing = busMarkers.find(
        item => String(item.busId) === String(bus.bus_id)
    );

    if (!existing) {
        createBusMarker(bus);
        return;
    }

    animateBusMarker(existing, getBusDisplayPosition(bus));

    if (Number.isFinite(Number(bus.heading))) {
        const body = document.getElementById("marker-" + bus.bus_id)?.querySelector(".bus-body");
        if (body) body.style.transform = "rotate(" + Number(bus.heading) + "deg)";
    }

    const markerNode = document.getElementById("marker-" + bus.bus_id);
    if (markerNode) {
        markerNode.classList.remove("confidence-high", "confidence-medium", "confidence-low");
        markerNode.classList.add("confidence-" + String(bus.position_confidence || "medium").toLowerCase());
    }
}

function createBusMarker(bus) {
    const position = getBusDisplayPosition(bus);
    const confidenceClass = String(bus.position_confidence || "medium").toLowerCase();
    const icon = L.divIcon({
        className: "",
        html: `
            <div class="bus-marker confidence-${escapeHtml(confidenceClass)}" id="marker-${bus.bus_id}" aria-label="Bus ${bus.bus_id}">
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
        [position.latitude, position.longitude],
        { icon: icon }
    ).addTo(map);

    marker.on("click", event => {
        L.DomEvent.stopPropagation(event);
        selectBus(bus.bus_id);
    });

    marker.busId = bus.bus_id;
    busMarkers.push(marker);
}

function createBusCard(bus, rankIndex = 0) {
    const card = document.createElement("div");
    card.className = "bus-card rank-" + Math.min(rankIndex + 1, 3);
    card.style.animationDelay = Math.min(rankIndex * 35, 400) + "ms";
    card.id = "bus-card-" + bus.bus_id;
    card.dataset.busId = String(bus.bus_id || "");
    card.dataset.distance = Number.isFinite(Number(bus.distance_km)) ? String(Number(bus.distance_km)) : "9999";

    const heading = Number.isFinite(Number(bus.heading)) ? Number(bus.heading) : 0;
    const movementState = getBusMovementState(bus);
    const freshness = getBusFreshness(bus);
    const rawSpeed = bus && bus.speed;
    const currentSpeed = rawSpeed !== undefined && rawSpeed !== null && rawSpeed !== ""
        ? Number(rawSpeed)
        : NaN;
    const isCurrentlyMoving = movementState === "moving";
    card.dataset.moving = isCurrentlyMoving ? "true" : "false";

    const nextStopValue = String(bus.likely_next_stop || bus.likely_towards || "").trim();
    const hasMatchedNextStop = Boolean(nextStopValue && (bus.route_path_id || bus.route_id) && bus.route_confidence);
    const rawDirection = String(bus.direction || "").trim();
    const cardinalDirection = /^(moving|stationary|unknown|direction unavailable)$/i.test(rawDirection) ? "" : rawDirection;
    const currentPlace = String(bus.nearby_place || "").trim();
    let directionHtml = "";

    if (isCurrentlyMoving) {
        const directionLabel = freshness.stale
            ? hasMatchedNextStop ? "LAST KNOWN MOVEMENT TOWARDS" : "LAST KNOWN LOCATION"
            : hasMatchedNextStop ? "MOVING TOWARDS" : "CURRENTLY MOVING THROUGH";
        const directionText = hasMatchedNextStop
            ? nextStopValue
            : [currentPlace, cardinalDirection].filter(Boolean).join(" · ") || "Nearby location being resolved";
        directionHtml = "<div class='bus-direction'><span class='direction-arrow' style='transform:rotate(" + heading + "deg)'></span><div><small>" + directionLabel + "</small><strong>" + escapeHtml(directionText) + "</strong></div></div>";
    } else if (movementState === "no_signal") {
        directionHtml = "<div class='bus-direction'><span class='direction-wait' aria-hidden='true'></span><div><small>LAST KNOWN MOVEMENT</small><strong>" + escapeHtml(direction || "No signal") + "</strong></div></div>";
    } else if (movementState === "stationary") {
        directionHtml = "<div class='bus-direction'><span class='direction-wait stationary' aria-hidden='true'></span><div><small>STATUS</small><strong>" + (freshness.stale ? "Last known stationary" : "Stationary") + "</strong></div></div>";
    }

    const route = getBusRoute(bus.bus_id);
    const status = freshness.stale
        ? "Location update delayed"
        : movementState === "moving"
        ? "Moving"
        : movementState === "stationary"
        ? "Stationary"
        : movementState === "no_signal"
        ? "No signal"
        : "Movement status unavailable";
    const statusClass = freshness.stale || movementState === "no_signal"
        ? "offline"
        : movementState === "stationary"
        ? "stationary"
        : "live";

    const rawLatitude = bus && bus.latitude;
    const rawLongitude = bus && bus.longitude;
    const latitude = rawLatitude !== undefined && rawLatitude !== null && rawLatitude !== "" ? Number(rawLatitude) : NaN;
    const longitude = rawLongitude !== undefined && rawLongitude !== null && rawLongitude !== "" ? Number(rawLongitude) : NaN;
    const locationText = Number.isFinite(latitude) && Number.isFinite(longitude)
        ? latitude.toFixed(5) + ", " + longitude.toFixed(5)
        : "Unavailable";
    const rawDistance = bus && bus.distance_km;
    const distance = rawDistance !== undefined && rawDistance !== null && rawDistance !== "" ? Number(rawDistance) : NaN;
    const distanceText = Number.isFinite(distance) ? distance.toFixed(2) + " km" : "Unavailable";
    const speedText = Number.isFinite(currentSpeed)
        ? (Number.isInteger(currentSpeed) ? String(currentSpeed) : currentSpeed.toFixed(1)) + " km/h"
        : "Unavailable";

    const rawMovement = bus && bus.movement_km;
    const movement = rawMovement !== undefined && rawMovement !== null && rawMovement !== "" ? Number(rawMovement) : NaN;
    const rawHistory = bus && bus.history_minutes;
    const history = rawHistory !== undefined && rawHistory !== null && rawHistory !== "" ? Number(rawHistory) : NaN;
    const movementHtml = Number.isFinite(movement) && movement >= 0 && Number.isFinite(history) && history > 0
        ? "<span class='bus-meta'>Movement " + movement.toFixed(2) + " km / " + history.toFixed(1) + " min</span>"
        : "";

    const nextStop = String(bus && (bus.likely_next_stop || bus.likely_towards) || "").trim();
    const routeMatched = Boolean(bus && (bus.route_path_id || bus.route_id) && nextStop && bus.route_confidence);
    const routeStopLabel = routeMatched && /^(high|medium)$/i.test(String(bus.route_confidence))
        ? "LIKELY NEXT STOP"
        : routeMatched
        ? "POSSIBLE NEXT STOP"
        : "LIKELY TOWARDS";
    const nextStopHtml = nextStop && !/unknownroute|^unknown$/i.test(nextStop)
        ? "<div class='bus-terminal-stop'><small>" + routeStopLabel + "</small><strong>" + escapeHtml(nextStop) + "</strong></div>"
        : "";
    const lastPassedStop = String(bus && (bus.last_passed_stop || bus.last_stop) || "").trim();
    const lastStopHtml = lastPassedStop && !/not enough route history|unknownroute|^unknown$/i.test(lastPassedStop)
        ? "<div class='bus-terminal-stop'><small>LAST PASSED STOP</small><strong>" + escapeHtml(lastPassedStop) + "</strong></div>"
        : "";
    const etaValue = String(bus && bus.eta_label || "").trim();
    const etaLabel = /disabled/i.test(etaValue)
        ? "ETA unavailable while estimates refresh"
        : etaValue || "ETA unavailable";
    const historyCount = Number(bus && bus.history_points_used);
    const historyHtml = Number.isFinite(historyCount) && historyCount > 0
        ? "<span class='bus-meta'>History " + Math.round(historyCount) + " recent points</span>"
        : "";
    const etaHtml = "<p class='updated bus-eta'>" + escapeHtml(etaLabel) + "</p>";

    card.innerHTML =
        "<div class='bus-card-top'>" +
            "<h3>" + escapeHtml(bus.bus_id || "Unknown Bus") + "</h3>" +
            (route ? "<span class='route-badge'>" + escapeHtml(route) + "</span>" : "") +
            "<button class='favorite-button' type='button' disabled aria-disabled='true' aria-label='Favorites coming soon'><span class='favorite-icon' aria-hidden='true'><svg viewBox='0 0 24 24' focusable='false'><path d='M6 3.5h12a1 1 0 0 1 1 1v16l-7-4.4-7 4.4v-16a1 1 0 0 1 1-1-1Z'></path></svg></span></button>" +
            "<span class='bus-rank'>#" + (rankIndex + 1) + "</span>" +
        "</div>" +
        directionHtml +
        lastStopHtml +
        nextStopHtml +
        "<div class='bus-meta-row'>" +
            "<span class='bus-meta'>Location " + escapeHtml(String(bus.nearby_place || locationText)) + "</span>" +
            "<span class='bus-meta'>Distance " + escapeHtml(distanceText) + "</span>" +
            "<span class='bus-meta'>Speed " + escapeHtml(speedText) + "</span>" +
            movementHtml +
            historyHtml +
        "</div>" +
        "<p class='status status-" + statusClass + "'><span class='status-dot' aria-hidden='true'></span>" + escapeHtml(status) + "</p>" +
        etaHtml +
        "<p class='updated'>" + escapeHtml(freshness.ageLabel) + " · " + escapeHtml(freshness.sourceLabel) + "</p>";

    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", "Bus " + (bus.bus_id || "unknown") + " at " + (bus.distance_km ?? "unknown") + " kilometres");
    const openBus = () => {
        selectBus(bus.bus_id);
        const position = getBusDisplayPosition(bus);
        map.setView([position.latitude, position.longitude], 16, {animate:true,duration:.35});
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
    highlightSelectedRoute(bus);

    if (selectedCard) {
        selectedCard.scrollIntoView({behavior:"smooth",block:"nearest"});
    }
}

function clearBusSelection() {
    selectedBusId = null;
    updateSelectedBusPanel(null);
    if (selectedRouteLayer) {
        map.removeLayer(selectedRouteLayer);
        selectedRouteLayer = null;
    }

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
            const aMoving = a.dataset.moving === "true";
            const bMoving = b.dataset.moving === "true";

            if (aMoving !== bMoving) return aMoving ? -1 : 1;

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
    const movementState = getBusMovementState(bus);
    const freshness = getBusFreshness(bus);
    const rawSpeed = bus && bus.speed;
    const popupSpeed = rawSpeed !== undefined && rawSpeed !== null && rawSpeed !== ""
        ? Number(rawSpeed)
        : NaN;
    const rawMovement = bus && bus.movement_km;
    const popupMovement = rawMovement !== undefined && rawMovement !== null && rawMovement !== ""
        ? Number(rawMovement)
        : NaN;
    const rawHistory = bus && bus.history_minutes;
    const historyMinutes = rawHistory !== undefined && rawHistory !== null && rawHistory !== ""
        ? Number(rawHistory)
        : NaN;

    const nextStop = String(bus.likely_next_stop || bus.likely_towards || "").trim();
    const lastPassedStop = String(bus.last_passed_stop || bus.last_stop || "").trim();
    const routeMatched = Boolean(nextStop && (bus.route_path_id || bus.route_id) && bus.route_confidence);

    let movementText = "Direction unavailable";
    if (movementState === "moving") {
        movementText = routeMatched
            ? "Moving towards " + escapeHtml(nextStop)
            : "Currently moving" + (bus.direction && !/^(moving|stationary|unknown)$/i.test(String(bus.direction)) ? " " + escapeHtml(String(bus.direction)) : "");
    } else if (movementState === "no_signal") {
        const towards = bus.likely_towards || bus.direction;
        movementText = towards
            ? "Last known movement towards " + escapeHtml(String(towards)) + " · No signal"
            : "No signal";
    } else if (movementState === "stationary") {
        movementText = freshness.stale ? "Last known stationary" : "Stationary";
    }

    const speedText = Number.isFinite(popupSpeed)
        ? (Number.isInteger(popupSpeed) ? String(popupSpeed) : popupSpeed.toFixed(1)) + " km/h"
        : "Unavailable";
    const rawLatitude = bus && bus.latitude;
    const rawLongitude = bus && bus.longitude;
    const latitude = rawLatitude !== undefined && rawLatitude !== null && rawLatitude !== "" ? Number(rawLatitude) : NaN;
    const longitude = rawLongitude !== undefined && rawLongitude !== null && rawLongitude !== "" ? Number(rawLongitude) : NaN;
    const coordinates = Number.isFinite(latitude) && Number.isFinite(longitude)
        ? latitude.toFixed(5) + ", " + longitude.toFixed(5)
        : "Unavailable";
    const locationText = String(bus.nearby_place || bus.location_label || coordinates);
    const rawDistance = bus && bus.distance_km;
    const distanceValue = rawDistance !== undefined && rawDistance !== null && rawDistance !== "" ? Number(rawDistance) : NaN;
    const distanceText = Number.isFinite(distanceValue)
        ? distanceValue.toFixed(2) + " km away"
        : "Unavailable";
    const movementStats = Number.isFinite(popupMovement) && popupMovement >= 0 && Number.isFinite(historyMinutes) && historyMinutes > 0
        ? "<br>Movement: " + popupMovement.toFixed(2) + " km in " + historyMinutes.toFixed(1) + " min"
        : "";
    const historyPoints = Number(bus.history_points_used);
    const historySummary = Number.isFinite(historyPoints) && historyPoints > 1
        ? "<br>History: " + Math.round(historyPoints) + " recent points"
        : "";
    const lastStopLine = lastPassedStop && !/not enough route history|unknownroute|^unknown$/i.test(lastPassedStop)
        ? "<br>Last passed stop: " + escapeHtml(lastPassedStop)
        : "";
    const nextStopLine = nextStop && !/unknownroute|^unknown$/i.test(nextStop)
        ? "<br>Upcoming stop: " + escapeHtml(nextStop) + (routeMatched ? "" : " · unconfirmed")
        : "<br>Upcoming stop: Not route-matched yet";
    const etaLine = "<br>ETA: " + escapeHtml(String(bus.eta_label || "Unavailable").replace(/^ETA:\s*/i, ""));
    const statusText = freshness.stale
        ? "Location update delayed"
        : movementState === "moving"
        ? "Moving"
        : movementState === "stationary"
        ? "Stationary"
        : movementState === "no_signal"
        ? "No signal"
        : "Movement status unavailable";

    return `
        <strong>${escapeHtml(bus.bus_id || "Unknown Bus")}</strong>
        <br><br>
        <span class="bus-inline-icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="M5 5.5h14a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-1v1.5a1.5 1.5 0 0 1-3 0V18H9v1.5a1.5 1.5 0 0 1-3 0V18H5a2 2 0 0 1-2-2V7.5a2 2 0 0 1 2-2Z"></path><path d="M6 8h12v4H6z"></path><circle cx="7" cy="15.5" r="1.2"></circle><circle cx="17" cy="15.5" r="1.2"></circle></svg></span> ${movementText}
        <br>
        Currently near: ${escapeHtml(locationText)}
        <br>
        GPS fix: ${escapeHtml(coordinates)}
        <br>
        Speed: ${escapeHtml(speedText)}
        <br>
        Distance: ${escapeHtml(distanceText)}
        ${lastStopLine}
        ${nextStopLine}
        ${movementStats}
        ${historySummary}
        ${etaLine}
        <br>
        Status: ${escapeHtml(statusText)}
        <br>
        ${escapeHtml(freshness.ageLabel)} · ${escapeHtml(freshness.sourceLabel)}
    `;
}

async function initializeRouteCatalog() {
    try {
        const response = await fetch(API_BASE_URL + "/api/routes");
        if (!response.ok) return;
        const data = await response.json();
        routeCatalog = Array.isArray(data.routes) ? data.routes : [];
    } catch (error) {
        routeCatalog = [];
    }
}

function isFavoriteBus(busId) {
    return favoriteBusIds.has(String(busId));
}

function toggleFavoriteBus(busId) {
    const id = String(busId);
    if (favoriteBusIds.has(id)) favoriteBusIds.delete(id);
    else favoriteBusIds.add(id);
    localStorage.setItem("noidaBusFavorites", JSON.stringify([...favoriteBusIds]));
    displayBuses(currentBuses);
}

function highlightSelectedRoute(bus) {
    if (selectedRouteLayer) {
        map.removeLayer(selectedRouteLayer);
        selectedRouteLayer = null;
    }

    if (!bus || !bus.route) return;

    const route = routeCatalog.find(item => item.name === bus.route);
    if (!route || !Array.isArray(route.points) || route.points.length < 2) return;

    selectedRouteLayer = L.polyline(
        route.points.map(point => [point.latitude, point.longitude]),
        {color:"#E85D26", weight:5, opacity:.72, lineCap:"round", lineJoin:"round", interactive:false}
    ).addTo(map);
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
            if (searchController) {
                searchController.abort();
                searchController = null;
            }
            input.setAttribute("aria-busy", "false");
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
    { name: "Botanical Garden Metro Station, Noida", latitude: 28.5672, longitude: 77.3346, aliases: ["botanical garden", "botanical metro"] },
    { name: "Sector 37, Noida", latitude: 28.5650, longitude: 77.3440, aliases: ["sec 37"] },
    { name: "Noida City Center Metro Station", latitude: 28.5740, longitude: 77.3560, aliases: ["noida city center", "sector 32 metro", "city centre"] },
    { name: "Sector 52 Metro Station, Noida", latitude: 28.5850, longitude: 77.3700, aliases: ["sector 52", "sec 52", "sector 52 metro", "noida sector 52"] },
    { name: "Parthala Flyover, Noida", latitude: 28.6075, longitude: 77.3755, aliases: ["parthala", "parthala flyover"] },
    { name: "Chaar Murti, Greater Noida West", latitude: 28.6020, longitude: 77.4180, aliases: ["char murti", "chaarmurti", "gaur chowk"] },
    { name: "Ek Murti Chowk, Greater Noida West", latitude: 28.6063, longitude: 77.4337, aliases: ["ek murti", "ekmurti"] },
    { name: "Jagat Farm Market, Gamma I, Greater Noida", latitude: 28.4812, longitude: 77.4996, aliases: ["jagat farm", "jagat farm market", "gamma i market"] },
    { name: "Surajpur, Greater Noida", latitude: 28.5185, longitude: 77.4990, aliases: ["surajpur"] },
    { name: "Pari Chowk, Greater Noida", latitude: 28.4652, longitude: 77.5080, aliases: ["pari chowk", "pari chowk metro"] }
];

function getLocalPlaceMatches(query) {
    const normalizedQuery = String(query || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    if (!normalizedQuery) return [];
    const terms = normalizedQuery.split(/\s+/).filter(Boolean);

    return LOCAL_PLACES.filter(place => {
        const searchable = [place.name, ...(place.aliases || [])]
            .join(" ")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, " ");
        return searchable.includes(normalizedQuery) || terms.every(term => searchable.includes(term));
    }).sort((a, b) => {
        const aName = String(a.name || "").toLowerCase();
        const bName = String(b.name || "").toLowerCase();
        const aExact = aName.includes(normalizedQuery) ? 0 : 1;
        const bExact = bName.includes(normalizedQuery) ? 0 : 1;
        return aExact - bExact || aName.length - bName.length;
    }).slice(0, 5);
}

function renderPlaceSuggestions(results, input, suggestions, emptyMessage = "No matching place found", searching = false) {
    suggestions.innerHTML = "";

    if (!results.length) {
        const empty = document.createElement("div");
        empty.className = searching ? "search-empty search-loading" : "search-empty";
        empty.setAttribute("role", "status");
        empty.setAttribute("aria-live", "polite");
        empty.textContent = emptyMessage;
        suggestions.appendChild(empty);
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

    if (searching) {
        const loading = document.createElement("div");
        loading.className = "search-empty search-loading";
        loading.setAttribute("role", "status");
        loading.setAttribute("aria-live", "polite");
        loading.textContent = "Searching for more places…";
        suggestions.appendChild(loading);
    }
}

async function searchPlaces(query) {
    const input = document.getElementById("placeSearch");
    const suggestions = document.getElementById("searchSuggestions");
    if (!input || !suggestions) return;

    const cleanQuery = String(query || "").trim();
    if (cleanQuery.length < 2) return;

    if (searchController) searchController.abort();
    const controller = new AbortController();
    searchController = controller;

    input.setAttribute("aria-busy", "true");

    const localResults = getLocalPlaceMatches(cleanQuery);
    renderPlaceSuggestions(
        localResults,
        input,
        suggestions,
        "Searching places…",
        true
    );
    suggestions.classList.remove("hidden");

    const timeoutId = setTimeout(() => controller.abort(), 18000);

    try {
        let externalResults = [];
        let backendFailed = false;

        try {
            const response = await fetch(
                API_BASE_URL + "/api/search-location?q=" + encodeURIComponent(cleanQuery),
                { signal: controller.signal, cache: "no-store" }
            );

            if (response.ok) {
                const data = await response.json();
                externalResults = Array.isArray(data.results) ? data.results : [];
            } else {
                backendFailed = true;
            }
        } catch (error) {
            if (error.name === "AbortError") throw error;
            backendFailed = true;
        }

        const normalizedQuery = cleanQuery.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
        const queryTokens = normalizedQuery.split(/\s+/).filter(token => token.length > 1);
        const hasRelevantExternalResult = externalResults.some(result => {
            const normalizedName = String(result.name || "").toLowerCase().replace(/[^a-z0-9]+/g, " ");
            return queryTokens.length > 0 && queryTokens.every(token => normalizedName.includes(token));
        });

        if ((!externalResults.length || externalResults.length < 3 || !hasRelevantExternalResult) && !controller.signal.aborted) {
            try {
                const fallbackResponse = await fetch(
                    "https://nominatim.openstreetmap.org/search?format=jsonv2&q=" +
                    encodeURIComponent(cleanQuery) +
                    "&countrycodes=in&limit=7&addressdetails=1",
                    {
                        signal: controller.signal,
                        headers: { "Accept": "application/json" },
                        cache: "no-store"
                    }
                );

                if (fallbackResponse.ok) {
                    const fallbackData = await fallbackResponse.json();
                    externalResults = externalResults.concat(fallbackData.map(item => ({
                        name: item.display_name,
                        latitude: Number(item.lat),
                        longitude: Number(item.lon)
                    })));
                }
            } catch (error) {
                if (error.name === "AbortError") throw error;
            }
        }

        if (controller.signal.aborted || input.value.trim() !== cleanQuery) return;

        const seen = new Set();
        const merged = [...localResults, ...externalResults].filter(result => {
            const latitude = Number(result.latitude);
            const longitude = Number(result.longitude);
            if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return false;
            const key = String(result.name || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        renderPlaceSuggestions(
            merged,
            input,
            suggestions,
            backendFailed && !merged.length
                ? "Search is temporarily unavailable. Please try again."
                : "No matching place found. Try a sector, metro station, or nearby landmark.",
            false
        );
        suggestions.classList.remove("hidden");
    } catch (error) {
        if (input.value.trim() === cleanQuery) {
            renderPlaceSuggestions(
                localResults,
                input,
                suggestions,
                error.name === "AbortError"
                    ? "Search timed out. Please try again."
                    : "Search is temporarily unavailable. Please try again.",
                false
            );
            suggestions.classList.remove("hidden");
        }
    } finally {
        clearTimeout(timeoutId);
        if (searchController === controller) {
            searchController = null;
            input.setAttribute("aria-busy", "false");
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


let selectedPlaceLookupToken = 0;

async function resolveSelectedBusPlace(bus) {
    const token = ++selectedPlaceLookupToken;
    const busId = String(bus && bus.bus_id || "");
    const placeNode = document.getElementById("selectedBusPlace");
    const coordinateNode = document.getElementById("selectedBusCoordinates");
    const rawLatitude = bus && bus.latitude;
    const rawLongitude = bus && bus.longitude;
    const latitude = rawLatitude !== undefined && rawLatitude !== null && rawLatitude !== "" ? Number(rawLatitude) : NaN;
    const longitude = rawLongitude !== undefined && rawLongitude !== null && rawLongitude !== "" ? Number(rawLongitude) : NaN;

    if (coordinateNode) {
        coordinateNode.textContent = Number.isFinite(latitude) && Number.isFinite(longitude)
            ? "GPS fix " + latitude.toFixed(5) + ", " + longitude.toFixed(5)
            : "GPS coordinates unavailable";
    }

    const fallback = String(bus && (bus.nearby_place || bus.location_label) || "").trim();
    if (placeNode) placeNode.textContent = fallback || "Finding nearest landmark...";
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;

    try {
        const response = await fetch(
            API_BASE_URL + "/api/location-label?lat=" + encodeURIComponent(latitude) + "&lon=" + encodeURIComponent(longitude),
            {cache:"no-store"}
        );
        if (!response.ok) return;
        const data = await response.json();
        if (
            token !== selectedPlaceLookupToken ||
            String(selectedBusId || "") !== busId
        ) return;
        if (placeNode && data.label) placeNode.textContent = String(data.label);
        const selected = currentBuses.find(item => String(item.bus_id) === busId);
        const selectedDirectionNode = document.getElementById("selectedBusDirection");
        const selectedDirectionLabel = document.getElementById("selectedBusDirectionLabel");
        const selectedNextStop = String(selected && (selected.likely_next_stop || selected.likely_towards) || "").trim();
        const hasMatchedNextStop = Boolean(
            selectedNextStop &&
            selected && (selected.route_path_id || selected.route_id) &&
            selected.route_confidence &&
            /^(high|medium)$/i.test(String(selected.route_confidence))
        );
        if (selected && selectedDirectionNode && getBusMovementState(selected) === "moving" && !hasMatchedNextStop) {
            const direction = String(selected.direction || "").trim();
            const safeDirection = /^(moving|stationary|unknown|direction unavailable)$/i.test(direction) ? "" : direction;
            selectedDirectionNode.textContent = [String(data.label), safeDirection].filter(Boolean).join(" · ") || "Nearby location resolved";
            if (selectedDirectionLabel) selectedDirectionLabel.textContent = "CURRENTLY MOVING THROUGH";
        }
    } catch (error) {
        if (token === selectedPlaceLookupToken && placeNode && fallback) {
            placeNode.textContent = fallback;
        }
    }
}

function updateSelectedBusPanel(bus) {
    const panel = document.getElementById("selectedBusPanel");
    if (!panel) return;

    if (!bus) {
        selectedPlaceLookupToken += 1;
        panel.classList.add("hidden");
        return;
    }

    const idNode = document.getElementById("selectedBusId");
    const routeNode = document.getElementById("selectedBusRoute");
    const statusNode = document.getElementById("selectedBusStatus");
    const directionNode = document.getElementById("selectedBusDirection");
    const directionLabelNode = document.getElementById("selectedBusDirectionLabel");
    const lastStopNode = document.getElementById("selectedBusLastStop");
    const nextStopNode = document.getElementById("selectedBusNextStop");
    const arrowNode = document.getElementById("selectedBusArrow");
    const distanceNode = document.getElementById("selectedBusDistance");
    const speedNode = document.getElementById("selectedBusSpeed");
    const movementNode = document.getElementById("selectedBusMovement");
    const etaNode = document.getElementById("selectedBusEta");
    const followButton = document.getElementById("selectedFollowBtn");

    const movementState = getBusMovementState(bus);
    const freshness = getBusFreshness(bus);
    const moving = movementState === "moving";
    const nextStop = String(bus.likely_next_stop || bus.likely_towards || "").trim();
    const hasRouteStop = Boolean(
        nextStop &&
        (bus.route_path_id || bus.route_id) &&
        bus.route_confidence &&
        !/unknownroute|^unknown$/i.test(nextStop)
    );
    const matchedNextStop = Boolean(hasRouteStop && /^(high|medium)$/i.test(String(bus.route_confidence)));
    const place = String(bus.nearby_place || bus.location_label || "").trim();
    const cardinalDirection = String(bus.direction || "").trim();
    const normalizedDirection = /^(moving|stationary|unknown|direction unavailable)$/i.test(cardinalDirection)
        ? ""
        : cardinalDirection;

    if (idNode) idNode.textContent = bus.bus_id || "Unknown Bus";

    if (routeNode) {
        const route = getBusRoute(bus.bus_id) || bus.route_id || "";
        routeNode.textContent = route;
        routeNode.classList.toggle("hidden", !route);
    }

    if (statusNode) {
        statusNode.textContent = freshness.stale
            ? "LOCATION DELAYED"
            : movementState === "no_signal"
            ? "NO SIGNAL"
            : movementState === "stationary"
            ? "STATIONARY"
            : moving
            ? "MOVING"
            : "STATUS UNKNOWN";
    }

    if (directionLabelNode) {
        directionLabelNode.textContent = freshness.stale && moving
            ? matchedNextStop ? "LAST KNOWN MOVEMENT TOWARDS" : "LAST KNOWN LOCATION"
            : moving && matchedNextStop
            ? "MOVING TOWARDS"
            : moving
            ? "CURRENTLY MOVING THROUGH"
            : movementState === "stationary"
            ? "CURRENT STATUS"
            : "TRAVEL DIRECTION";
    }
    if (directionNode) {
        directionNode.textContent = moving && matchedNextStop
            ? (freshness.stale ? "Last known towards " : "") + nextStop
            : moving
            ? [freshness.stale ? "Last seen near " + place.replace(/^Near /i, "") : place, normalizedDirection].filter(Boolean).join(" · ") || "Nearby location being resolved"
            : movementState === "stationary"
            ? place ? "Stationary near " + place.replace(/^Near /i, "") : "Stationary"
            : normalizedDirection || "Direction unavailable";
    }

    if (lastStopNode) {
        const labelNode = lastStopNode.parentElement?.querySelector("span");
        const lastStop = String(bus.last_passed_stop || bus.last_stop || "").trim();
        const hasLastStop = Boolean(lastStop && !/not enough route history|unknownroute|^unknown$/i.test(lastStop));
        if (labelNode) labelNode.textContent = hasLastStop
            ? String(bus.last_stop_confidence || "").toLowerCase() === "low" ? "Likely previous stop" : "Last passed stop · estimate"
            : "Last passed stop";
        lastStopNode.textContent = hasLastStop
            ? lastStop
            : "No stop confirmed from recent history";
    }

    if (nextStopNode) {
        nextStopNode.textContent = matchedNextStop
            ? nextStop
            : hasRouteStop
            ? nextStop + " · low-confidence estimate"
            : "No route-matched stop yet";
    }

    if (arrowNode) {
        const heading = bus.heading != null && bus.heading !== "" ? Number(bus.heading) : NaN;
        arrowNode.style.transform = Number.isFinite(heading)
            ? "rotate(" + heading + "deg)"
            : "rotate(0deg)";
        arrowNode.classList.toggle("hidden", !Number.isFinite(heading));
    }

    if (distanceNode) {
        const distance = bus.distance_km != null && bus.distance_km !== "" ? Number(bus.distance_km) : NaN;
        distanceNode.textContent = Number.isFinite(distance)
            ? distance.toFixed(2) + " km away"
            : "Distance unavailable";
    }

    if (speedNode) {
        const speed = bus.speed != null && bus.speed !== "" ? Number(bus.speed) : NaN;
        speedNode.textContent = Number.isFinite(speed)
            ? (Number.isInteger(speed) ? String(speed) : speed.toFixed(1)) + " km/h"
            : "Speed unavailable";
    }

    if (movementNode) {
        const historyCount = bus.history_points_used != null && bus.history_points_used !== ""
            ? Number(bus.history_points_used)
            : NaN;
        const historyMinutes = bus.history_span_minutes != null && bus.history_span_minutes !== ""
            ? Number(bus.history_span_minutes)
            : NaN;
        movementNode.textContent = Number.isFinite(historyCount) && historyCount >= 2
            ? "History " + Math.round(historyCount) + " points" + (Number.isFinite(historyMinutes) && historyMinutes > 0 ? " · " + historyMinutes.toFixed(1) + " min" : "")
            : "Collecting movement history";
    }

    if (etaNode) {
        const eta = String(bus.eta_label || "").trim();
        etaNode.textContent = eta
            ? eta.replace(/^ETA:\s*/i, "")
            : "Waiting for a reliable route match";
    }

    resolveSelectedBusPlace(bus);
    if (followButton) followButton.textContent = "Follow bus";
    panel.classList.remove("hidden");
}

function closeSelectedBusPanel() {
    clearBusSelection();
}
