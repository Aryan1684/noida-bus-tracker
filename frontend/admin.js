const API = "https://noida-bus-tracker.onrender.com";
const KEY = "noidaBusAdminToken";
let token = sessionStorage.getItem(KEY) || "";
let map = null;
let layer = null;

function auth() {
    return {
        Accept: "application/json",
        "X-Admin-Token": token
    };
}

async function request(path) {
    const response = await fetch(API + path, { headers: auth() });
    if (response.status === 401) throw new Error("Invalid admin token.");
    if (!response.ok) throw new Error("Request failed: HTTP " + response.status);
    return response.json();
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
    const rows = (items || []).filter(x => x.name === "web" || x.name === "android");
    if (!rows.length) {
        emptyState(box, "No platform data yet.");
        return;
    }
    rows.forEach(x => {
        const label = x.name === "android" ? "Android app" : "Web";
        box.innerHTML +=
            "<div class='platform-row'><div><strong>" + label + "</strong><small>" +
            (x.views || 0) + " views/open · " + (x.events || 0) + " events · " + (x.selections || 0) + " bus selections</small></div>" +
            "<div><b>" + (x.visitors || 0) + "</b><span> visitors</span><small>" +
            Math.round((Number(x.visitor_share) || 0) * 100) + "%</small></div></div>";
    });
}

function dailyChart(items) {
    const box = document.getElementById("dailyChart");
    box.innerHTML = "";
    const data = items || [];
    const max = Math.max(1, ...data.map(x => Math.max(Number(x.visitors) || 0, Number(x.sessions) || 0, Number(x.events) || 0)));
    data.forEach(x => {
        const col = document.createElement("div");
        col.className = "day-col";
        const height = Math.max(4, Math.round((Number(x.events) || 0) / max * 150));
        col.innerHTML =
            "<div class='day-bar' style='height:" + height + "px' title='" + esc(x.date) + " · " + (x.events || 0) + " events'></div>" +
            "<span>" + esc((x.date || "").slice(5)) + "</span>";
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
    (cells || []).forEach(x => {
        const lat = Number(x.latitude);
        const lon = Number(x.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
        points.push([lat, lon]);
        L.circle([lat, lon], {
            radius: 450,
            weight: 1,
            fillOpacity: 0.25
        }).bindPopup("Approximate demand area · " + x.shares + " shares").addTo(layer);
    });
    if (points.length) map.fitBounds(points, { padding: [20, 20], maxZoom: 13 });
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
    document.getElementById("error").hidden = true;
    const started = Date.now();
    try {
        const days = document.getElementById("days").value;
        const results = await Promise.all([
            request("/api/admin/analytics?days=" + days),
            request("/api/admin/fleet")
        ]);
        const analytics = results[0];
        const fleetData = results[1];

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

        document.getElementById("storage").textContent = "Storage: " + analytics.storage;
        document.getElementById("lastLoaded").textContent = "Loaded in " + (Date.now() - started) + " ms";

        platformTable(analytics.platforms);
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
        fleet(fleetData);
    } catch (error) {
        const box = document.getElementById("error");
        box.textContent = error.message;
        box.hidden = false;
    }
}

function login() {
    const value = document.getElementById("token").value.trim();
    if (!value) {
        document.getElementById("loginStatus").textContent = "Enter the admin token.";
        return;
    }
    sessionStorage.setItem(KEY, value);
    token = value;
    request("/api/admin/analytics?days=7").then(() => {
        document.getElementById("login").hidden = true;
        document.getElementById("dash").hidden = false;
        load();
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
}
