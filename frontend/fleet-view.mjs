import { drawCoach } from "./coach-model.mjs";
// MapTiler's public browser key is shared with the existing nearby map.
const mapKey = "zDrcI9pwHS3FLOHuWQm3";
export const routeColors = {
    R1: "#116953",
    R2: "#85388b",
    R3: "#a34c1d",
    R4: "#2466a4",
    R5: "#906415",
    "Ek Murti": "#a03773",
    "Via D-Mart": "#236c69",
    GR01: "#395fa4",
};
const region = [
    [77.31, 28.35],
    [77.595, 28.64],
];
const limits = [
    [77.21, 28.24],
    [77.72, 28.73],
];
const toLatLng = ([x, y]) => [y, x];

// MapLibre counts 512px world tiles. Leaflet counts 256px tiles, one zoom level apart.
export function streetScale(zoom, tilePixels, latitude) {
    const metresPerPixel = 40075017 * Math.cos(latitude * Math.PI / 180) / (tilePixels * 2 ** zoom);
    const lengthPixels = 12 / metresPerPixel;
    return Math.min(5, 0.78 + lengthPixels / 48);
}

function updateStreetScale(map, tilePixels, zoom = map.getZoom()) {
    const scale = streetScale(zoom, tilePixels, map.getCenter().lat);
    const style = map.getContainer().style;
    style.setProperty("--coach-scale", scale);
    const level = zoom + Math.log2(tilePixels / 256);
    const tilt = 26 + Math.min(22, Math.max(0, level - 13) * 3.5);
    style.setProperty("--zoom-tilt", tilt + "deg");
    map.getContainer().classList.toggle("city-scale", level < 13.5);
}

function vehicleMarker(el, map, gl, move, remove) {
    const coach = el.querySelector(".coach");
    let heading = -55;
    const events = gl ? ["rotate","pitch","zoom"] : ["zoomend","coachpitch"];
    function redraw() {
        const z = map.getZoom() + (gl ? 1 : 0);
        const tilt = 45 + Math.min(18,Math.max(0,z-13)*3);
        const camera = gl ? map.getPitch() : map.getContainer().classList.contains("model-view") ? 70 : 0;
        const relative = heading - (gl ? map.getBearing() : 0);
        drawCoach(coach,relative,Math.max(camera,tilt));
    }
    events.forEach(event => map.on(event,redraw));
    redraw();
    return {
        move(point,angle) { heading=angle; move(point); redraw(); },
        remove() { events.forEach(event => map.off(event,redraw)); remove(); }
    };
}

function roadFeatures(network) {
    return network.routes.flatMap((route) =>
        route.paths.map((path) => ({
            type: "Feature",
            properties: { id: route.id, color: routeColors[route.id] },
            geometry: { type: "LineString", coordinates: path },
        })),
    );
}
function stopButton(name, select) {
    const el = document.createElement("button");
    el.className = "stop-pin";
    el.type = "button";
    el.title = name;
    el.setAttribute("aria-label", name + ", mapped stop");
    el.addEventListener("click", (event) => {
        event.stopPropagation();
        select("stop", name);
    });
    return el;
}
function glView(map, network, select, onDrag) {
    const markers = [];
    const container = map.getContainer();
    const syncCamera = () => {
        updateStreetScale(map, 512);
        container.style.setProperty("--camera-bearing", map.getBearing() + "deg");
        container.style.setProperty("--camera-tilt", map.getPitch() + "deg");
    };
    for (const event of ["zoom","rotate","pitch"]) map.on(event,syncCamera);
    syncCamera();
    const roads = roadFeatures(network);
    const visible = { routes: true, stops: true };
    let selectedRoute = null;
    function styleRoads() {
        if (!map.getLayer("fleet-roads")) return;
        const filter = selectedRoute ? ["==", "id", selectedRoute] : null;
        for (const layer of ["fleet-casing", "fleet-roads"]) {
            map.setFilter(layer, filter);
            map.setLayoutProperty(layer, "visibility", visible.routes ? "visible" : "none");
        }
    }
    map.on("load", () => {
        map.addSource("fleet-roads", {
            type: "geojson",
            data: { type: "FeatureCollection", features: roads },
        });
        const before = map.getStyle().layers.find((layer) => layer.type === "symbol")?.id;
        const layout = { "line-cap": "round", "line-join": "round" };
        map.addLayer(
            {
                id: "fleet-casing",
                source: "fleet-roads",
                type: "line",
                layout,
                paint: { "line-color": "#fff", "line-width": 6, "line-opacity": 0.83 },
            },
            before,
        );
        map.addLayer(
            {
                id: "fleet-roads",
                source: "fleet-roads",
                type: "line",
                layout,
                paint: { "line-color": ["get", "color"], "line-width": 3.1, "line-opacity": 0.87 },
            },
            before,
        );
        styleRoads();
        map.on("click", "fleet-roads", (e) => select("route", e.features[0].properties.id));
    });
    map.on("dragstart", (event) => {
        if (event.originalEvent) onDrag();
    });
    for (const [name, point] of Object.entries(network.stops)) {
        const el = stopButton(name, select);
        new maplibregl.Marker({ element: el }).setLngLat(point).addTo(map);
        markers.push(el);
    }
    map.fitBounds(region, { padding: 36, duration: 0 });
    const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
    return {
        marker(el, point, vehicle = false) {
            const marker = new maplibregl.Marker({
                element: el,
                rotationAlignment: "viewport",
                pitchAlignment: "viewport",
            })
                .setLngLat(point)
                .addTo(map);
            if (vehicle) return vehicleMarker(el,map,true,p=>marker.setLngLat(p),()=>marker.remove());
            return { move: (p) => marker.setLngLat(p), remove: () => marker.remove() };
        },
        onStreetViewChange(refresh) {
            let changed = true;
            map.on("moveend", () => { changed = true; });
            map.on("idle", () => {
                if (changed) {
                    changed = false;
                    refresh();
                }
            });
        },
        nearbyRoads(point) {
            if (map.getZoom()<14 || !map.isStyleLoaded() || !map.getBounds().contains(point)) return [];
            const layers = map.getStyle().layers.filter(l=>l.type==="line" && l["source-layer"]==="transportation").map(l=>l.id);
            if (!layers.length) return [];
            const center=map.project(point);
            const radius=24*512*2**map.getZoom()/(40075017*Math.cos(point[1]*Math.PI/180));
            const box=[[center.x-radius,center.y-radius],[center.x+radius,center.y+radius]];
            return map.queryRenderedFeatures(box,{layers}).filter(f=>
                ["motorway","trunk","primary","secondary","tertiary","minor","residential","service","unclassified"].includes(f.properties.class)
            ).flatMap(f=>f.geometry.type==="MultiLineString" ? f.geometry.coordinates :
                f.geometry.type==="LineString" ? [f.geometry.coordinates] : []);
        },
        streetZoom: 18.75,
        focus(point, zoom) {
            const target = zoom ?? map.getZoom();
            map.flyTo({ center: point, zoom: target, duration: reduced() ? 0 : 850,
                pitch: target >= 18 ? Math.max(map.getPitch(), 42) : map.getPitch() });
            document.getElementById("pitch").setAttribute("aria-pressed", String(target >= 18 || map.getPitch() > 0));
        },
        track(point) {
            map.jumpTo({ center: point });
        },
        fit(points) {
            const bounds = new maplibregl.LngLatBounds();
            (points || region).forEach((p) => bounds.extend(p));
            map.fitBounds(bounds, { padding: 45, maxZoom: 15, duration: reduced() ? 0 : 420 });
        },
        zoom(delta) {
            map.easeTo({ zoom: map.getZoom() + delta, duration: reduced() ? 0 : 170 });
        },
        pitch(enabled) {
            map.easeTo({
                pitch: enabled ? 53 : 0,
                bearing: enabled ? -18 : 0,
                duration: reduced() ? 0 : 550,
            });
        },
        layers(toggles, route) {
            Object.assign(visible, toggles);
            selectedRoute = route;
            styleRoads();
            markers.forEach((el) => {
                el.hidden = !visible.stops;
            });
        },
    };
}

async function flatView(network, select, onDrag) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css";
    document.head.append(link);
    await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js";
        script.onload = resolve;
        script.onerror = reject;
        document.head.append(script);
    });
    const map = L.map("map", { zoomControl: false, maxBounds: limits.map(toLatLng), minZoom: 10, zoomSnap: 0.25, wheelPxPerZoomLevel: 100 }).fitBounds(
        region.map(toLatLng),
    );
    L.tileLayer("https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=" + mapKey, {
        tileSize: 512,
        zoomOffset: -1,
        maxNativeZoom: 20,
        maxZoom: 22,
        attribution:
            '© <a href="https://www.maptiler.com/copyright/">MapTiler</a> · © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    map.on("zoom zoomend", () => updateStreetScale(map, 256));
    map.on("zoomanim", event => updateStreetScale(map, 256, event.zoom));
    updateStreetScale(map, 256);
    map.on("dragstart", onDrag);
    const stops = L.layerGroup().addTo(map),
        roads = L.layerGroup().addTo(map);
    const lines = roadFeatures(network).map((f) => {
        const line = L.polyline(f.geometry.coordinates.map(toLatLng), {
            weight: 3.5,
            color: f.properties.color,
        });
        line.on("click", () => select("route", f.properties.id)).addTo(roads);
        return [f.properties.id, line];
    });
    function marker(el, point, group = map, vehicle = false) {
        const size = vehicle ? [32, 38] : [14, 14];
        const pin = L.marker(toLatLng(point), {
            icon: L.divIcon({ html: el, className: "", iconSize: size }),
            keyboard: false,
        }).addTo(group);
        if (vehicle) return vehicleMarker(el,map,false,p=>pin.setLatLng(toLatLng(p)),()=>pin.remove());
        return { move: (p) => pin.setLatLng(toLatLng(p)), remove: () => pin.remove() };
    }
    for (const [name, point] of Object.entries(network.stops)) marker(stopButton(name, select), point, stops);
    document.getElementById("pitch").title = "Tilt electric bus models";
    return {
        marker: (el, p, v) => marker(el, p, map, v),
        streetZoom: 19.75,
        focus: (p, z) => {
            if (matchMedia("(prefers-reduced-motion: reduce)").matches) map.setView(toLatLng(p), z ?? map.getZoom(), {animate:false});
            else map.flyTo(toLatLng(p), z ?? map.getZoom(), {duration:0.75});
        },
        track: (p) => map.panTo(toLatLng(p), { animate: false }),
        fit: (points) =>
            map.fitBounds((points || region).map(toLatLng), {
                padding: [28, 28],
                maxZoom: 15,
                animate: false,
            }),
        zoom: (delta) => map.setZoom(map.getZoom() + delta),
        pitch: enabled => { map.getContainer().classList.toggle("model-view", enabled); map.fire("coachpitch"); },
        layers(toggles, route) {
            lines.forEach(([id, line]) => {
                if (toggles.routes && (!route || route === id)) roads.addLayer(line);
                else roads.removeLayer(line);
            });
            if (toggles.stops) stops.addTo(map);
            else stops.remove();
        },
    };
}

export async function createView(network, select, onDrag) {
    if (globalThis.maplibregl) {
        let map;
        try {
            map = new maplibregl.Map({
                container: "map",
                style: "https://api.maptiler.com/maps/streets-v2/style.json?key=" + mapKey,
                center: [77.431, 28.525],
                zoom: 11,
                maxBounds: limits,
                minZoom: 9,
                maxZoom: 21,
                attributionControl: { compact: true },
            });
            return glView(map, network, select, onDrag);
        } catch (_) {
            map?.remove();
        }
    }
    return flatView(network, select, onDrag);
}
