const API = "https://noida-bus-tracker.onrender.com";
const KEY = "noidaBusAdminToken";
let token = sessionStorage.getItem(KEY) || "";
let map = null;
let layer = null;
let mobileInstallMapInstance = null;
let mobileInstallHeatLayer = null;

function auth() {
    return {
        Accept: "application/json",
        "X-Admin-Token": token
    };
}

async function request(path) {
    let response;
    try {
        response = await fetch(API + path, {
            headers: auth(),
            cache: "no-store"
        });
    } catch (_) {
        throw new Error("Cannot reach the analytics API. Check the connection and backend status.");
    }
    if (response.status === 401) throw new Error("Invalid admin token.");
    if (!response.ok) throw new Error("Request failed: HTTP " + response.status);
    try {
        return await response.json();
    } catch (_) {
        throw new Error("The analytics API returned an unreadable response.");
    }
}

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    }[c]));
}

function emptyState(box, text = "No data yet.") {
    box.innerHTML = "<p class='muted'>" + esc(text) + "</p>";
}

function tableRows(id, items, labelKey, options = {}) {
    const box = document.getElementById(id);
    box.innerHTML = "";
    if (!items || !items.length) {
        emptyState(box);
        return;
    }
    const max = Math.max(1, ...items.map(item => Number(item.count) || 0));
    items.forEach(item => {
        const label = item[labelKey] ?? item.name ?? "unknown";
        const count = Number(item.count) || 0;
        const visitors = options.visitors ? " · " + (Number(item.visitors) || 0) + " visitors" : "";
        box.innerHTML +=
            "<div class='row'><div class='row-main'><span>" + esc(label) + "</span>" +
            (visitors ? "<small>" + esc(visitors) + "</small>" : "") +
            "</div><div class='row-value'><i style='width:" + Math.round(count / max * 100) + "%'></i><b>" + count + "</b></div></div>";
    });
}

function platformTable(items) {
    const box = document.getElementById("platformTable");
    box.innerHTML = "";
    const labels = {
        web: "Web browser",
        installed_app: "Installed app (PWA)",
        android: "Android app",
        ios: "iOS app",
        unknown: "Unclassified source"
    };
    const rows = (items || []).filter(x =>
        ["web", "installed_app", "android", "ios", "unknown"].includes(x.name) &&
        (Number(x.events) > 0 || Number(x.visitors) > 0)
    );
    if (!rows.length) {
        emptyState(box, "No platform data yet. New visits will appear here.");
        return;
    }
    rows.forEach(x => {
        box.innerHTML +=
            "<div class='platform-row'><div><strong>" + esc(labels[x.name] || x.name) + "</strong><small>" +
            (x.views || 0) + " views / opens · " + (x.events || 0) + " events · " +
            (x.sessions || 0) + " sessions · " + (x.selections || 0) + " bus selections</small></div>" +
            "<div><b>" + (x.visitors || 0) + "</b><span> visitors</span><small>" +
            Math.round((Number(x.visitor_share) || 0) * 100) + "% of platform visitor counts</small></div></div>";
    });
}

function dailyChart(items) {
    const box = document.getElementById("dailyChart");
    box.innerHTML = "";
    const data = items || [];
    if (!data.length) {
        emptyState(box, "No traffic recorded in this reporting window.");
        return;
    }
    const max = Math.max(1, ...data.map(x => Math.max(
        Number(x.visitors) || 0,
        Number(x.sessions) || 0,
        Number(x.events) || 0
    )));
    const hourly = data.length > 0 && /^\d{2}:\d{2}$/.test(String(data[0].label || ""));
    box.classList.toggle("hourly-series", hourly);
    data.forEach((x, index) => {
        const col = document.createElement("div");
        col.className = "day-col";
        const bars = document.createElement("div");
        bars.className = "day-bars";
        [
            ["visitors", "bar-visitors", "visitors"],
            ["sessions", "bar-sessions", "sessions"],
            ["events", "bar-events", "events"]
        ].forEach(([key, className, label]) => {
            const value = Number(x[key]) || 0;
            const bar = document.createElement("i");
            bar.className = "day-bar " + className;
            bar.style.height = Math.max(2, Math.round(value / max * 145)) + "px";
            bar.title = (x.date || "") + " · " + (x.label || "") + " · " + value + " " + label;
            bars.appendChild(bar);
        });
        const date = document.createElement("span");
        date.textContent = x.label || (x.date || "").slice(5);
        date.title = x.date || "";
        if (hourly && data.length > 24 && index % 4 !== 0 && index !== data.length - 1) date.hidden = true;
        col.appendChild(bars);
        col.appendChild(date);
        box.appendChild(col);
    });
}
function hourlyChart(items) {
    const box = document.getElementById("hourlyChart");
    box.innerHTML = "";
    const data = items || [];
    const max = Math.max(1, ...data.map(x => Number(x.events) || 0));
    let peak = { hour: null, events: -1 };
    data.forEach(x => {
        if ((Number(x.events) || 0) > peak.events) peak = x;
        const col = document.createElement("div");
        col.className = "hour-col";
        col.innerHTML =
            "<div class='hour-bar' style='height:" + Math.max(3, Math.round((Number(x.events) || 0) / max * 125)) + "px' title='" +
            esc(x.label) + " · " + (x.events || 0) + " events · " + (x.visitors || 0) + " visitors'></div>" +
            "<span>" + esc(String(x.hour).padStart(2, "0")) + "</span>";
        box.appendChild(col);
    });
    document.getElementById("peakHour").textContent = peak.hour == null ? "No activity yet" : "Peak " + String(peak.hour).padStart(2, "0") + ":00";
}

function demandMap(cells) {
    const summary = document.getElementById("heatmapSummary");
    if (!map) {
        map = L.map("map").setView([28.5355, 77.3910], 11);
        L.tileLayer("https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=zDrcI9pwHS3FLOHuWQm3", {
            tileSize: 512,
            zoomOffset: -1,
            attribution: "&copy; MapTiler &copy; OpenStreetMap contributors"
        }).addTo(map);
        layer = L.layerGroup().addTo(map);
    }
    layer.clearLayers();
    const points = [];
    const valid = (cells || []).filter(x => {
        const lat = Number(x.latitude);
        const lon = Number(x.longitude);
        const shares = Number(x.shares);
        return Number.isFinite(lat) && Number.isFinite(lon) && Number.isFinite(shares) && shares >= 3;
    });
    const maxShares = Math.max(1, ...valid.map(x => Number(x.shares)));
    valid.forEach(x => {
        const lat = Number(x.latitude);
        const lon = Number(x.longitude);
        const shares = Number(x.shares);
        const intensity = Math.max(0.25, shares / maxShares);
        points.push([lat, lon]);
        if (typeof L.heatLayer !== "function") {
            L.circle([lat, lon], {
                radius: 350 + Math.min(800, shares * 25),
                weight: 1,
                fillOpacity: 0.2 + intensity * 0.3
            }).bindPopup("Approximate area · " + shares + " consented location shares").addTo(layer);
        } else {
            L.circleMarker([lat, lon], {
                radius: Math.min(18, 5 + Math.sqrt(shares) * 2),
                weight: 1,
                fillOpacity: 0.18,
                opacity: 0.35
            }).bindPopup("Approximate area · " + shares + " consented location shares").addTo(layer);
        }
    });
    if (typeof L.heatLayer === "function" && valid.length) {
        L.heatLayer(valid.map(x => [
            Number(x.latitude),
            Number(x.longitude),
            Math.max(0.2, Number(x.shares) / maxShares)
        ]), {
            radius: 34,
            blur: 26,
            maxZoom: 13,
            max: 1,
            minOpacity: 0.28
        }).addTo(map);
    }
    if (points.length) {
        map.fitBounds(points, { padding: [20, 20], maxZoom: 13 });
        if (summary) summary.textContent = valid.length + " high-level areas shown. Stronger hotspots indicate more consented location shares in the selected reporting window.";
    } else if (summary) {
        summary.textContent = "No area has reached 3 consented location shares in this reporting window yet. The map will populate as more visitors opt in.";
    }
    window.setTimeout(() => map && map.invalidateSize(), 100);
}


function renderMobileInstallMap(cells) {
    const box = document.getElementById("mobileInstallMap");
    const summary = document.getElementById("mobileInstallMapSummary");
    if (!box) return;
    if (!mobileInstallMapInstance) {
        mobileInstallMapInstance = L.map(box).setView([28.5355, 77.3910], 10);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 18,
            attribution: "&copy; OpenStreetMap contributors"
        }).addTo(mobileInstallMapInstance);
        mobileInstallHeatLayer = L.layerGroup().addTo(mobileInstallMapInstance);
    }
    mobileInstallHeatLayer.clearLayers();
    const valid = (cells || []).filter(item =>
        Number.isFinite(Number(item.latitude)) &&
        Number.isFinite(Number(item.longitude)) &&
        Number(item.count) >= 3
    );
    const max = Math.max(1, ...valid.map(item => Number(item.count)));
    const bounds = [];
    valid.forEach(item => {
        const lat = Number(item.latitude);
        const lon = Number(item.longitude);
        const count = Number(item.count);
        bounds.push([lat, lon]);
        L.circleMarker([lat, lon], {
            radius: Math.min(20, 6 + Math.sqrt(count) * 2),
            color: "#5c8b28",
            weight: 1,
            fillColor: "#b8f26b",
            fillOpacity: 0.35 + 0.45 * count / max
        }).bindPopup("Approximate first-open area · " + count + " installation(s)").addTo(mobileInstallHeatLayer);
    });
    if (typeof L.heatLayer === "function" && valid.length) {
        L.heatLayer(valid.map(item => [
            Number(item.latitude),
            Number(item.longitude),
            Math.max(0.2, Number(item.count) / max)
        ]), {radius: 34, blur: 26, maxZoom: 13, max: 1, minOpacity: 0.25}).addTo(mobileInstallHeatLayer);
    }
    if (bounds.length) {
        mobileInstallMapInstance.fitBounds(bounds, {padding: [18, 18], maxZoom: 12});
        summary.textContent = valid.length + " approximate areas shown; only cells with at least 3 tracked installation IDs are displayed.";
    } else {
        summary.textContent = "No area has reached 3 tracked installation IDs with a successful IP lookup yet.";
    }
    window.setTimeout(() => mobileInstallMapInstance && mobileInstallMapInstance.invalidateSize(), 100);
}

function renderMobileAnalytics(data) {
    document.getElementById("mobileAnalyticsStatus").textContent =
        data.storage === "sqlite-ephemeral" ? "TEMPORARY STORAGE" : (data.period_label || "Mobile analytics");
    document.getElementById("mobileInstalls").textContent = data.tracked_first_opens_all_time ?? "0";
    document.getElementById("mobileActive").textContent = data.active_installations ?? "0";
    document.getElementById("mobileSessions").textContent = data.active_sessions ?? "0";
    document.getElementById("mobileOpens").textContent = data.app_opens ?? "0";
    document.getElementById("mobileNewInstalls").textContent = data.tracked_first_opens_in_window ?? "0";
    document.getElementById("mobileFeatureEvents").textContent = data.feature_events ?? "0";
    document.getElementById("mobileTrackingNote").textContent = data.tracking_note ||
        "First opens are a proxy for installation instances, not exact Play Store install counts or unique physical phones. Areas are approximate IP-derived first-open areas.";
    dailyChartInto("mobileDailyChart", data.daily);
    tableRows("mobileBrandTable", data.brands, "name");
    tableRows("mobileManufacturerTable", data.manufacturers, "name");
    tableRows("mobileModelTable", data.models, "name");
    tableRows("mobileAndroidTable", data.android_versions, "name");
    tableRows("mobileAppVersionTable", data.app_versions, "name");
    tableRows("mobileEventTable", data.event_breakdown, "name");
    tableRows("mobileInstallAreaTable", (data.install_areas || []).map(item => ({
        name: item.name + " · " + Number(item.latitude).toFixed(2) + ", " + Number(item.longitude).toFixed(2),
        count: item.count
    })), "name");
    renderMobileInstallMap(data.install_areas);
}

function dailyChartInto(id, items) {
    const box = document.getElementById(id);
    if (!box) return;
    box.innerHTML = "";
    const data = items || [];
    if (!data.length) {
        emptyState(box, "No Android activity recorded in this reporting window.");
        return;
    }
    const max = Math.max(1, ...data.map(item => Math.max(
        Number(item.visitors) || 0,
        Number(item.sessions) || 0,
        Number(item.events) || 0
    )));
    const hourly = data.length > 0 && /^\d{2}:\d{2}$/.test(String(data[0].label || ""));
    box.classList.toggle("hourly-series", hourly);
    data.forEach((item, index) => {
        const column = document.createElement("div");
        column.className = "day-col";
        const bars = document.createElement("div");
        bars.className = "day-bars";
        [["visitors", "bar-visitors", "active installations"], ["sessions", "bar-sessions", "sessions"], ["events", "bar-events", "events"]].forEach(([key, className, label]) => {
            const value = Number(item[key]) || 0;
            const bar = document.createElement("i");
            bar.className = "day-bar " + className;
            bar.style.height = Math.max(2, Math.round(value / max * 145)) + "px";
            bar.title = (item.date || item.label || "") + " · " + value + " " + label;
            bars.appendChild(bar);
        });
        const date = document.createElement("span");
        date.textContent = item.label || (item.date || "").slice(5);
        date.title = item.date || "";
        if (hourly && data.length > 24 && index % 4 !== 0 && index !== data.length - 1) date.hidden = true;
        column.appendChild(bars);
        column.appendChild(date);
        box.appendChild(column);
    });
}

function renderForecastModel(data) {
    const status = document.getElementById("forecastModelStatus");
    const trainingStatus = document.getElementById("forecastTrainingStatus");
    const button = document.getElementById("trainForecastButton");
    const lastAttempt = data.last_attempt_status || data.status;
    status.textContent = data.active ? "ACTIVE" : String(data.status || "Unavailable").replaceAll("_", " ").toUpperCase();
    document.getElementById("forecastModelType").textContent = data.model_type || "Random Forest";
    document.getElementById("forecastTrainingSamples").textContent = data.training_samples ?? data.samples ?? "—";
    document.getElementById("forecastValidationSamples").textContent = data.validation_samples ?? "—";
    document.getElementById("forecastModelMae").textContent = data.model_mae_km == null ? "—" : Number(data.model_mae_km).toFixed(3) + " km";
    document.getElementById("forecastBaselineMae").textContent = data.baseline_mae_km == null ? "—" : Number(data.baseline_mae_km).toFixed(3) + " km";
    document.getElementById("forecastImprovement").textContent = data.improvement_percent == null ? "—" : Number(data.improvement_percent).toFixed(1) + "%";
    if (data.error) trainingStatus.textContent = "Model status unavailable: " + data.error;
    else if (lastAttempt === "not_promoted_baseline_better") trainingStatus.textContent = "Latest candidate did not beat the baseline by at least 3%, so it was not promoted.";
    else if (lastAttempt === "promoted") trainingStatus.textContent = "A model passed time-based validation and was promoted.";
    else if (data.status === "collecting_data") trainingStatus.textContent = "Collecting timestamped GPS history. Minimum sample target: " + (data.minimum_samples ?? "—") + ".";
    else if (data.active) trainingStatus.textContent = "The active model is evaluated against later GPS timestamps before any replacement.";
    else trainingStatus.textContent = String(data.status || "Model unavailable").replaceAll("_", " ");
    button.disabled = data.status === "training_in_progress";
}

async function loadForecastModel() {
    try {
        renderForecastModel(await request("/api/admin/forecast-model"));
    } catch (error) {
        document.getElementById("forecastModelStatus").textContent = "UNAVAILABLE";
        document.getElementById("forecastTrainingStatus").textContent = error.message;
    }
}

async function trainForecastModelNow() {
    const button = document.getElementById("trainForecastButton");
    const note = document.getElementById("forecastTrainingStatus");
    button.disabled = true;
    button.textContent = "Training…";
    note.textContent = "Building training samples and validating against the motion baseline…";
    try {
        const response = await fetch(API + "/api/admin/forecast-model/train", {
            method: "POST",
            headers: auth(),
            cache: "no-store"
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Training failed (HTTP " + response.status + ").");
        renderForecastModel(data);
        await loadForecastModel();
    } catch (error) {
        note.textContent = error.message;
        button.disabled = false;
    } finally {
        button.textContent = "Train / retrain model";
    }
}

function fleet(data) {
    document.getElementById("fleetTotal").textContent = data.total ?? "—";
    document.getElementById("fleetLive").textContent = data.live ?? "—";
    document.getElementById("fleetMoving").textContent = data.moving ?? "—";
    document.getElementById("fleetStationary").textContent = data.stationary ?? "—";
    document.getElementById("fleetNoSignal").textContent = data.no_signal ?? "—";
    document.getElementById("fleetAnomalies").textContent = data.gps_anomalies ?? "—";
    document.getElementById("fleetPredictions").textContent = data.predictions_available ?? "—";
    document.getElementById("fleetCorrected").textContent = data.predictions_applied ?? "—";
    document.getElementById("fleetConfidence").textContent =
        data.average_prediction_confidence == null ? "—" : Math.round(Number(data.average_prediction_confidence) * 100) + "%";
    document.getElementById("collectorStatus").textContent =
        data.live_gps_collector_running ? "RUNNING" : "STOPPED";

    const box = document.getElementById("fleetTable");
    box.innerHTML = "";
    const buses = data.buses || [];
    if (!buses.length) {
        emptyState(box);
        return;
    }

    buses.forEach(bus => {
        const speed = Number(bus.speed);
        const status = bus.vehicle_status || "unknown";
        const anomaly = bus.gps_anomaly ? "GPS anomaly" : "GPS normal";
        const prediction = bus.prediction_applied ? "AI corrected" : (bus.prediction_available ? "Forecast ready" : "No forecast");
        box.innerHTML +=
            "<div class='fleet-row'>" +
            "<strong>" + esc(bus.bus_id) + "</strong>" +
            "<span>" + esc(status) + "</span>" +
            "<span>" + (Number.isFinite(speed) ? speed.toFixed(0) + " km/h" : "—") + "</span>" +
            "<span class='" + (bus.gps_anomaly ? "bad" : "good") + "'>" + esc(anomaly) + "</span>" +
            "<span>" + esc(prediction) + "</span>" +
            "<span>" + (bus.prediction_confidence == null ? "—" : Math.round(Number(bus.prediction_confidence) * 100) + "%") + "</span>" +
            "</div>";
    });

    document.getElementById("fleetUpdated").textContent = "Live fleet response · " + buses.length + " buses";
}

function recentTable(items) {
    const box = document.getElementById("recentTable");
    box.innerHTML = "";
    if (!items || !items.length) {
        emptyState(box);
        return;
    }
    items.forEach(x => {
        const time = x.time ? new Date(x.time).toLocaleString() : "—";
        const subject = x.bus_id || x.place || x.path || "—";
        box.innerHTML +=
            "<div class='recent-row'><span>" + esc(time) + "</span><strong>" + esc(x.event) + "</strong><span>" +
            esc(x.source) + "</span><span>" + esc(x.device) + "</span><span>" + esc(subject) + "</span></div>";
    });
}

async function load() {
    const errorBox = document.getElementById("error");
    const warningBox = document.getElementById("warning");
    const fleetError = document.getElementById("fleetError");
    const refreshButton = document.getElementById("refresh");
    errorBox.hidden = true;
    warningBox.hidden = true;
    fleetError.hidden = true;
    const started = Date.now();
    refreshButton.disabled = true;
    refreshButton.textContent = "Loading…";

    (async () => {
        try {
            const days = document.getElementById("days").value;
            const results = await Promise.allSettled([
                request("/api/admin/analytics?period=" + encodeURIComponent(days)),
                request("/api/admin/fleet"),
                request("/api/admin/mobile-analytics?period=" + encodeURIComponent(days)),
                request("/api/admin/forecast-model")
            ]);

            if (results[0].status === "rejected") throw results[0].reason;
            const analytics = results[0].value;

            document.getElementById("uniqueVisitors").textContent = analytics.unique_visitors ?? "0";
            document.getElementById("sessions").textContent = analytics.unique_sessions ?? "0";
            document.getElementById("returning").textContent = analytics.returning_visitors ?? "0";
            document.getElementById("views").textContent = analytics.page_views ?? "0";
            document.getElementById("events").textContent = analytics.total_events ?? "0";
            document.getElementById("avgSession").textContent = (analytics.average_session_minutes ?? 0) + " min";
            document.getElementById("engaged").textContent = analytics.engaged_sessions ?? "0";
            document.getElementById("bounce").textContent =
                (analytics.bounce_sessions ?? 0) + " · " + Math.round((Number(analytics.bounce_rate) || 0) * 100) + "%";

            document.getElementById("refreshes").textContent = analytics.refreshes ?? "0";
            document.getElementById("selections").textContent = analytics.bus_selections ?? "0";
            document.getElementById("busShares").textContent = analytics.bus_shares ?? "0";
            document.getElementById("locationUses").textContent = analytics.location_uses ?? "0";
            document.getElementById("locations").textContent = analytics.location_shares ?? "0";
            document.getElementById("installs").textContent = analytics.pwa_installs ?? "0";
            document.getElementById("feedback").textContent = analytics.feedback_submitted ?? "0";
            document.getElementById("reports").textContent = analytics.reports_submitted ?? "0";

            const storageLabels = {
                "supabase-postgresql": "Supabase PostgreSQL",
                "postgresql": "PostgreSQL",
                "sqlite-ephemeral": "SQLite (temporary)"
            };
            document.getElementById("storage").textContent =
                "Storage: " + (storageLabels[analytics.storage] || analytics.storage || "unknown");

            const latestEvent = analytics.latest_event_at
                ? new Date(analytics.latest_event_at).toLocaleString([], {dateStyle:"medium",timeStyle:"short"})
                : "No events in this window";
            document.getElementById("lastLoaded").textContent =
                (analytics.period_label || days) + " · Latest event: " + latestEvent +
                " · Loaded in " + (Date.now() - started) + " ms";

            if (analytics.storage === "sqlite-ephemeral") {
                warningBox.textContent = "Analytics is using temporary SQLite storage. Events can disappear after a service restart or redeploy. Configure DATABASE_URL for persistent Supabase/PostgreSQL history.";
                warningBox.hidden = false;
            } else if (analytics.storage === "postgresql") {
                warningBox.textContent = "The backend is connected to PostgreSQL, but its hostname was not recognized as Supabase. If you expected Supabase, check Render's DATABASE_URL host. The connection string is not displayed here.";
                warningBox.hidden = false;
            }

            const title = document.getElementById("trafficTitle");
            if (title) {
                title.textContent = analytics.series_granularity === "hour"
                    ? "Hourly visitors, sessions and events"
                    : analytics.series_granularity === "week"
                    ? "Weekly visitors, sessions and events"
                    : "Daily visitors, sessions and events";
            }
            dailyChart(analytics.daily);
            hourlyChart(analytics.hourly);
            tableRows("eventTable", analytics.event_breakdown, "event");
            tableRows("deviceTable", analytics.devices, "name", { visitors: true });
            tableRows("browserTable", analytics.browsers, "name", { visitors: true });
            tableRows("osTable", analytics.oses, "name", { visitors: true });
            tableRows("versionTable", analytics.app_versions, "name", { visitors: true });
            tableRows("busTable", analytics.top_buses, "bus_id");
            tableRows("sharedBusTable", analytics.top_shared_buses, "bus_id");
            tableRows("searchTable", analytics.top_searches, "name");
            tableRows("referrerTable", analytics.referrers, "name");
            recentTable(analytics.recent_events);
            demandMap(analytics.location_cells);

            if (results[3].status === "fulfilled") {
                renderForecastModel(results[3].value);
            } else {
                document.getElementById("forecastModelStatus").textContent = "UNAVAILABLE";
                document.getElementById("forecastTrainingStatus").textContent = results[3].reason?.message || "Could not load forecast model status.";
            }

            if (results[2].status === "fulfilled") {
                renderMobileAnalytics(results[2].value);
            } else {
                document.getElementById("mobileAnalyticsStatus").textContent = "Unavailable";
                document.getElementById("mobileTrackingNote").textContent = "Mobile analytics could not be loaded. Check that the backend with the mobile analytics endpoint has deployed successfully.";
                ["mobileInstalls", "mobileActive", "mobileSessions", "mobileOpens", "mobileNewInstalls", "mobileFeatureEvents"].forEach(id => {
                    document.getElementById(id).textContent = "—";
                });
            }

            if (results[1].status === "fulfilled") {
                fleet(results[1].value);
            } else {
                fleetError.textContent = "Fleet data did not load (" + (results[1].reason?.message || "request failed") + "). Usage analytics above are still up to date; retry to reload fleet data.";
                fleetError.hidden = false;
                ["fleetTotal", "fleetLive", "fleetMoving", "fleetStationary", "fleetNoSignal", "fleetAnomalies",
                 "fleetPredictions", "fleetCorrected", "fleetConfidence", "collectorStatus"].forEach(id => {
                    document.getElementById(id).textContent = "—";
                });
                emptyState(document.getElementById("fleetTable"), "Fleet data is temporarily unavailable.");
                document.getElementById("fleetUpdated").textContent = "Unavailable";
            }
        } catch (error) {
            errorBox.textContent = error.message || "Analytics failed to load.";
            errorBox.hidden = false;
            if (error.message === "Invalid admin token.") {
                sessionStorage.removeItem(KEY);
                token = "";
                document.getElementById("dash").hidden = true;
                document.getElementById("login").hidden = false;
                document.getElementById("loginStatus").textContent = "Your admin token was rejected. Log in again.";
            }
        } finally {
            refreshButton.disabled = false;
            refreshButton.textContent = "Refresh data";
        }
    })();
}



function maintenanceDurationMinutes() {
    const hours = Math.max(0, Math.min(168, Number(document.getElementById("maintenanceHours").value) || 0));
    const minutes = Math.max(0, Math.min(59, Number(document.getElementById("maintenanceMinutes").value) || 0));
    return Math.floor(hours * 60 + minutes);
}

async function loadMaintenance() {
    const state = document.getElementById("maintenanceState");
    const message = document.getElementById("maintenanceMessage");
    const status = document.getElementById("maintenanceStatus");
    try {
        const data = await request("/api/admin/maintenance");
        state.textContent = data.enabled ? "ENABLED" : "DISABLED";
        state.classList.toggle("maintenance-on", data.enabled);
        message.value = data.message || "We are making a few improvements. Please check back shortly.";
        document.getElementById("maintenanceToggle").disabled = false;
        document.getElementById("maintenanceDisable").disabled = !data.enabled;
        if (data.expires_at) {
            const remaining = Math.max(0, Math.ceil((data.expires_at - Date.now()) / 60000));
            document.getElementById("maintenanceHours").value = Math.floor(remaining / 60);
            document.getElementById("maintenanceMinutes").value = remaining % 60;
            status.textContent = data.enabled ? "Auto-disable scheduled. Remaining: " + remaining + " minute(s)." : "The tracker is visible to visitors.";
        } else {
            status.textContent = data.enabled ? "Maintenance is enabled without an expiry." : "The tracker is visible to visitors.";
        }
    } catch (error) {
        state.textContent = "Unavailable";
        status.textContent = error.message + " If this persists, check whether the backend has deployed the maintenance API.";
    }
}

async function setMaintenance(enabled) {
    const status = document.getElementById("maintenanceStatus");
    const toggle = document.getElementById("maintenanceToggle");
    const disable = document.getElementById("maintenanceDisable");
    const duration = maintenanceDurationMinutes();
    if (enabled && duration < 1) {
        status.textContent = "Enter a duration of at least 1 minute.";
        return;
    }
    toggle.disabled = true;
    disable.disabled = true;
    status.textContent = enabled ? "Saving maintenance schedule…" : "Disabling maintenance…";
    try {
        const response = await fetch(API + "/api/admin/maintenance", {
            method: "POST",
            headers: { ...auth(), "Content-Type": "application/json" },
            cache: "no-store",
            body: JSON.stringify({
                enabled,
                message: document.getElementById("maintenanceMessage").value.trim(),
                duration_minutes: duration
            })
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.detail || "Could not update maintenance mode (HTTP " + response.status + ").");
        await loadMaintenance();
        status.textContent = enabled ? "Maintenance enabled. Auto-disable is scheduled." : "Maintenance disabled. The tracker is available again.";
    } catch (error) {
        status.textContent = error.message + " Check backend deployment and API logs.";
        toggle.disabled = false;
        disable.disabled = false;
    }
}

document.getElementById("maintenanceToggle").addEventListener("click", () => setMaintenance(true));
document.getElementById("maintenanceDisable").addEventListener("click", () => setMaintenance(false));
document.getElementById("trainForecastButton").addEventListener("click", trainForecastModelNow);

function login() {
    const value = document.getElementById("token").value.trim();
    if (!value) {
        document.getElementById("loginStatus").textContent = "Enter the admin token.";
        return;
    }
    sessionStorage.setItem(KEY, value);
    token = value;
    request("/api/admin/analytics?period=7d").then(() => {
        document.getElementById("login").hidden = true;
        document.getElementById("dash").hidden = false;
        load();
        loadMaintenance();
    }).catch(error => {
        sessionStorage.removeItem(KEY);
        token = "";
        document.getElementById("loginStatus").textContent = error.message;
    });
}

document.getElementById("loginBtn").onclick = login;
document.getElementById("token").onkeydown = event => {
    if (event.key === "Enter") login();
};
document.getElementById("refresh").onclick = load;
document.getElementById("days").onchange = load;
document.getElementById("logout").onclick = () => {
    sessionStorage.removeItem(KEY);
    location.reload();
};

if (token) {
    document.getElementById("login").hidden = true;
    document.getElementById("dash").hidden = false;
    load();
    loadMaintenance();
}
