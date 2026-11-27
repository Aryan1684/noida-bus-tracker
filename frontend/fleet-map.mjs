import {
    loadNetwork,
    eligibleBus,
    inArea,
    observation,
    stateOf,
    movementPath,
    makeLeg,
    poseAt,
    shortestTurn,
    canAnimate,
} from "./fleet-motion.mjs";
import { createView, routeColors } from "./fleet-view.mjs";

const $ = (id) => document.getElementById(id);
const fleet = new Map();
const toggles = { routes: true, stops: true, buses: true };
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const query = new URLSearchParams(location.search);
let network,
    view,
    selection,
    following = false,
    tab = "Buses",
    lastRead = 0;
let feedState = "connecting",
    pending = false,
    frame = 0,
    locationPin,
    noticeTimer;
let sharedBus = query.get("bus")?.trim().toUpperCase();

function node(tag, cls, value) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (value != null) n.textContent = value;
    return n;
}
function icon(id) {
    const ns = "http://www.w3.org/2000/svg",
        svg = document.createElementNS(ns, "svg"),
        use = document.createElementNS(ns, "use");
    use.setAttribute("href", "#i-" + id);
    svg.setAttribute("aria-hidden", "true");
    svg.append(use);
    return svg;
}
function notice(text) {
    clearTimeout(noticeTimer);
    $("mapNotice").textContent = text;
    $("mapNotice").hidden = false;
    noticeTimer = setTimeout(() => {
        $("mapNotice").hidden = true;
    }, 6500);
}
function expand(open) {
    document.querySelector(".explorer").classList.toggle("open", open);
    $("sheetToggle").setAttribute("aria-expanded", String(open));
    $("sheetToggle").textContent = open ? "Collapse ▾" : "Explore ▴";
}
function routeFor(fix) {
    return getBusRoute(fix.id) || fix.route;
}
function visualState(entry) {
    return feedState === "offline" ? "Last known" : stateOf(entry.fix);
}
function place(entry, point, heading) {
    entry.point = point;
    if (Number.isFinite(heading)) entry.angle += shortestTurn(entry.angle, heading);
    entry.marker?.move(point);
    if (entry.coach) entry.coach.style.transform = "rotateZ(" + entry.angle + "deg)";
    if (following && selection?.kind === "bus" && selection.id === entry.fix.id) view?.track(point);
}
function settle(entry) {
    entry.leg = null;
    place(entry, entry.fix.point, entry.fix.heading ?? entry.angle);
}
function styleVehicle(entry) {
    if (!entry.el) return;
    const status = visualState(entry);
    entry.el.classList.toggle("stationary", status === "Stationary");
    entry.el.classList.toggle("stale", status === "Last known");
    entry.el.classList.toggle("selected", selection?.kind === "bus" && selection.id === entry.fix.id);
    entry.el.setAttribute("aria-label", entry.fix.id + " · " + status);
    entry.el.title = entry.el.getAttribute("aria-label");
    entry.el.hidden = !toggles.buses;
}
function attach(entry) {
    if (!view || entry.marker) return;
    const el = node("button", "vehicle");
    el.type = "button";
    const coach = node("span", "coach");
    coach.setAttribute("aria-hidden", "true");
    ["flank", "flank right", "nose", "tail", "roof"].forEach((cls) => coach.append(node("i", cls)));
    el.append(coach);
    el.addEventListener("click", (e) => {
        e.stopPropagation();
        select("bus", entry.fix.id);
    });
    entry.el = el;
    entry.coach = coach;
    entry.marker = view.marker(el, entry.point, true);
    styleVehicle(entry);
    place(entry, entry.point, entry.angle);
}
function animate(now) {
    frame = 0;
    let more = false;
    for (const entry of fleet.values()) {
        if (!entry.leg) continue;
        const t = (now - entry.start) / entry.duration;
        if (t >= 1 || reduced.matches || document.hidden || visualState(entry) === "Last known") {
            settle(entry);
            continue;
        }
        const pose = poseAt(entry.leg, t);
        // Give the coach a short steering transition around bends and across north.
        const turn = shortestTurn(entry.angle, pose.heading);
        const dt = Math.max(0, now - entry.lastFrame);
        place(entry, pose.point, entry.angle + turn * (1 - Math.exp(-dt / 170)));
        entry.lastFrame = now;
        more = true;
    }
    if (more) frame = requestAnimationFrame(animate);
}
function accept(fix) {
    let e = fleet.get(fix.id);
    if (!e) {
        e = { fix, point: fix.point, angle: fix.heading ?? 0 };
        fleet.set(fix.id, e);
        attach(e);
        return;
    }
    const previous = e.fix;
    if (previous.time && (!fix.time || fix.time < previous.time)) return;
    const duplicate = previous.time !== null && fix.time === previous.time;
    if (duplicate) {
        // Repeated poll data may mark a fix stale, but cannot move the bus.
        e.fix = { ...fix, point: previous.point, heading: previous.heading };
        if (stateOf(e.fix) === "Last known" || fix.parked) settle(e);
        styleVehicle(e);
        return;
    }
    e.fix = fix;
    const route = network.routes.find((r) => r.id === routeFor(fix));
    const path =
        view && !reduced.matches && !document.hidden && canAnimate(previous, fix)
            ? movementPath(e.point, fix.point, route)
            : null;
    if (path) {
        e.leg = makeLeg(path);
        e.start = e.lastFrame = performance.now();
        e.duration = Math.min(25000, Math.max(1200, fix.time - previous.time));
    } else settle(e);
    styleVehicle(e);
}
function ageText(time) {
    if (!time) return "GPS time unavailable";
    const s = Math.max(0, Math.floor((Date.now() - time) / 1000));
    if (s < 60) return s + " sec ago";
    if (s < 3600) return Math.floor(s / 60) + " min ago";
    if (s < 86400) return Math.floor(s / 3600) + " hr ago";
    return Math.floor(s / 86400) + " days ago";
}
function sourceStatus() {
    const status = { connecting: "Connecting to GPS…", offline: "GPS unavailable", online: "Fleet checked" };
    const checked = lastRead
        ? new Date(lastRead).toLocaleTimeString("en-IN", {
              hour: "2-digit",
              minute: "2-digit",
              timeZone: "Asia/Kolkata",
          }) + " IST"
        : "";
    $("feed").textContent = status[feedState] + (checked ? " · " + checked : "");
    document.querySelector(".source-dot").dataset.state = feedState;
}
function heading(title, count) {
    const h = node("h2", "list-heading", title);
    if (count != null) h.append(node("span", "", count));
    return h;
}
function row(kind, id, title, sub, tag) {
    const b = node("button", "row");
    b.type = "button";
    b.dataset.item = kind + "-" + id;
    const badge = node("span", kind === "bus" ? "bus-badge" : "badge");
    if (kind === "route") {
        badge.textContent = id;
        badge.style.setProperty("--route", routeColors[id]);
    } else {
        badge.append(icon(kind === "stop" ? "stop" : "bus"));
        if (tag === "Last known") badge.classList.add("old");
    }
    const txt = node("span", "text");
    txt.append(node("strong", "", title), node("small", "", sub));
    b.append(badge, txt, icon("arrow"));
    b.onclick = () => select(kind, id);
    return b;
}
function routeRow(r) {
    return row("route", r.id, r.name, r.stops.length + " mapped stops");
}
function empty(title, desc) {
    const box = node("div", "empty");
    box.append(node("strong", "", title), node("p", "hint", desc));
    return box;
}
function renderResults() {
    const results = $("results"),
        q = $("query").value.trim().toLowerCase();
    const match = (...parts) =>
        parts.some((value) =>
            String(value ?? "")
                .toLowerCase()
                .includes(q),
        );
    const all = [...fleet.values()].sort(
        (a, b) =>
            Number(visualState(a) === "Last known") - Number(visualState(b) === "Last known") ||
            a.fix.id.localeCompare(b.fix.id),
    );
    const buses = all.filter((e) => match(e.fix.id, routeFor(e.fix), visualState(e)));
    const routes = (network?.routes || []).filter((r) => match(r.name, r.id, ...r.stops));
    const stops = Object.keys(network?.stops || {})
        .filter((n) => match(n))
        .sort();
    const nodes = [];
    if (q || tab === "Buses") {
        nodes.push(heading("Electric buses", buses.length));
        for (const e of buses) {
            const status = visualState(e),
                route = routeFor(e.fix);
            nodes.push(
                row(
                    "bus",
                    e.fix.id,
                    e.fix.id,
                    [route, status, ageText(e.fix.time)].filter(Boolean).join(" · "),
                    status,
                ),
            );
        }
        if (!q && !buses.length) {
            if (feedState === "offline")
                nodes.push(
                    empty(
                        "GPS feed unavailable",
                        "You can still explore the mapped routes and stops. Bus positions will return when the feed recovers.",
                    ),
                );
            else if (feedState === "connecting")
                nodes.push(empty("Checking the fleet…", "Looking for electric buses across both cities."));
            else
                nodes.push(
                    empty(
                        "No electric buses reported",
                        "The latest feed has no vehicles in the service area. The map refreshes automatically.",
                    ),
                );
        }
    }
    if (q || tab === "Routes" || (tab === "Buses" && buses.length < 6)) {
        nodes.push(heading("Network routes", routes.length), ...routes.map(routeRow));
    }
    if (q || tab === "Stops") {
        nodes.push(heading("Mapped stops", stops.length));
        nodes.push(
            ...stops.map((name) =>
                row(
                    "stop",
                    name,
                    name,
                    network.routes
                        .filter((r) => r.stops.includes(name))
                        .map((r) => r.id)
                        .join(" · "),
                ),
            ),
        );
    }
    if (q && !buses.length && !routes.length && !stops.length)
        nodes.splice(0, nodes.length, empty("No matches", "Try a bus number, route code or stop name."));
    results.replaceChildren(...nodes);
}
function layers() {
    view?.layers(toggles, selection?.kind === "route" ? selection.id : null);
    for (const e of fleet.values()) styleVehicle(e);
}
function clearSelection() {
    selection = null;
    following = false;
    $("detail").hidden = true;
    $("results").hidden = false;
    layers();
    renderResults();
}
function renderDetail() {
    if (!selection) return;
    const { kind, id } = selection,
        detail = $("detail");
    const back = node("button", "back", "← Back to results");
    back.dataset.item = "detail-back";
    back.onclick = clearSelection;
    const nodes = [back];
    if (kind === "bus") {
        const e = fleet.get(id);
        if (!e) {
            clearSelection();
            notice("That bus has left the current fleet snapshot.");
            return;
        }
        const route = routeFor(e.fix),
            status = visualState(e);
        nodes.push(
            node("p", "kicker", "Electric bus"),
            node("h2", "detail-title", id),
            node(
                "p",
                "detail-body gps",
                [
                    status,
                    ageText(e.fix.time),
                    status !== "Last known" && e.fix.speed != null ? Math.round(e.fix.speed) + " km/h" : "",
                ]
                    .filter(Boolean)
                    .join(" · "),
            ),
            node("p", "detail-body", "Depot · " + e.fix.depot),
        );
        if (view && status !== "Last known") {
            const follow = node("button", "follow", following ? "Stop following" : "Follow bus");
            follow.setAttribute("aria-pressed", String(following));
            follow.dataset.item = "follow";
            follow.onclick = () => {
                following = !following;
                if (following) view.focus(e.point, 16);
                renderDetail();
            };
            nodes.push(follow);
        } else following = false;
        if (route) {
            const r = network.routes.find((r) => r.id === route);
            if (r) nodes.push(heading("Assigned route"), routeRow(r));
        }
    } else if (kind === "route") {
        const r = network.routes.find((r) => r.id === id);
        nodes.push(
            node("p", "kicker", "Route " + id),
            node("h2", "detail-title", r.name),
            node(
                "p",
                "detail-body",
                "Road links are approximate. Only mapped stops in the service area are shown.",
            ),
        );
        const list = node("ol", "stop-list");
        r.stops.forEach((name) => {
            const li = node("li"),
                b = node("button", "", name);
            b.onclick = () => select("stop", name);
            li.append(b);
            list.append(li);
        });
        nodes.push(list);
    } else {
        nodes.push(
            node("p", "kicker", "Mapped stop"),
            node("h2", "detail-title", id),
            heading("Routes at this stop"),
            ...network.routes.filter((r) => r.stops.includes(id)).map(routeRow),
        );
    }
    const focus = document.activeElement?.dataset.item;
    detail.replaceChildren(...nodes);
    detail.hidden = false;
    $("results").hidden = true;
    if (focus)
        Array.from(detail.querySelectorAll("[data-item]"))
            .find((b) => b.dataset.item === focus)
            ?.focus({ preventScroll: true });
}
function select(kind, id) {
    selection = { kind, id };
    following = false;
    expand(true);
    layers();
    renderDetail();
    if (kind === "bus") {
        const e = fleet.get(id);
        if (!e) return;
        view?.focus(e.point, 16);
        window.noidaBusAnalytics?.track("bus_selected", { bus_id: id });
    } else if (kind === "route") {
        const r = network.routes.find((r) => r.id === id);
        view?.fit(r.paths.flat().length ? r.paths.flat() : r.stops.map((n) => network.stops[n]));
    } else view?.focus(network.stops[id], 16);
    $("detail").querySelector(".back")?.focus({ preventScroll: true });
}
async function refresh() {
    if (pending || document.hidden) return;
    pending = true;
    $("refreshBtn").disabled = true;
    try {
        network = await loadNetwork();
        const res = await fetch(TRACKER_API + "/api/buses", {
            cache: "no-store",
            signal: AbortSignal.timeout(18000),
        });
        const body = await res.json();
        if (body?.maintenance === true) {
            location.replace("./maintenance.html");
            return;
        }
        if (!res.ok || !Array.isArray(body?.buses)) throw new Error("Fleet unavailable");
        feedState = "online";
        lastRead = Date.now();
        const seen = new Set();
        for (const raw of body.buses) {
            if (!eligibleBus(raw, network)) continue;
            const fix = observation(raw);
            seen.add(fix.id);
            accept(fix);
        }
        for (const [id, e] of fleet)
            if (!seen.has(id)) {
                e.marker?.remove();
                fleet.delete(id);
            }
        if (!frame) frame = requestAnimationFrame(animate);
        if (sharedBus && fleet.has(sharedBus)) {
            select("bus", sharedBus);
            sharedBus = null;
        }
    } catch (_) {
        feedState = "offline";
        for (const e of fleet.values()) {
            settle(e);
            styleVehicle(e);
        }
    } finally {
        pending = false;
        $("refreshBtn").disabled = false;
        sourceStatus();
        if (selection) renderDetail();
        else renderResults();
    }
}
function locate() {
    if (!navigator.geolocation) {
        notice("Location is unavailable on this device.");
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const point = [pos.coords.longitude, pos.coords.latitude];
            if (!inArea(point, network)) {
                notice("Your location is outside the Noida and Greater Noida service area.");
                return;
            }
            following = false;
            locationPin?.remove();
            locationPin = view.marker(node("span", "user-pin"), point);
            view.focus(point, 15);
            notice("Showing your location.");
        },
        () => notice("Location unavailable. Search for a stop instead."),
        { timeout: 10000 },
    );
}
async function init() {
    if (!(await trackerReady)) return;
    $("routeWarning").showModal();
    $("sheetToggle").onclick = () => expand(!document.querySelector(".explorer").classList.contains("open"));
    document.querySelectorAll("[data-tab]").forEach(
        (button) =>
            (button.onclick = () => {
                tab = button.dataset.tab;
                $("query").value = "";
                document
                    .querySelectorAll("[data-tab]")
                    .forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
                clearSelection();
            }),
    );
    $("query").oninput = () => {
        clearSelection();
    };
    $("refreshBtn").onclick = refresh;
    $("layersButton").onclick = () => {
        const hidden = !$("layers").hidden;
        $("layers").hidden = hidden;
        $("layersButton").setAttribute("aria-expanded", String(!hidden));
    };
    $("layers").onchange = (e) => {
        toggles[e.target.value] = e.target.checked;
        layers();
    };
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        if (!$("layers").hidden) {
            $("layersButton").click();
            $("layersButton").focus();
        } else if (selection) clearSelection();
        else expand(false);
    });
    $("fit").onclick = () => {
        clearSelection();
        view?.fit();
    };
    $("zoomIn").onclick = () => view?.zoom(1);
    $("zoomOut").onclick = () => view?.zoom(-1);
    $("pitch").onclick = () => {
        const on = $("pitch").getAttribute("aria-pressed") !== "true";
        $("pitch").setAttribute("aria-pressed", String(on));
        view?.pitch(on);
    };
    $("mapLocateBtn").onclick = () => {
        if (view) locate();
    };
    renderResults();
    try {
        network = await loadNetwork();
        renderResults();
        createView(network, select, () => {
            if (following) {
                following = false;
                renderDetail();
            }
        })
            .then((v) => {
                view = v;
                for (const e of fleet.values()) attach(e);
                layers();
                if (selection?.kind === "bus" && fleet.has(selection.id))
                    view.focus(fleet.get(selection.id).point, 16);
                if (query.has("lat") && query.has("lon")) {
                    const p = [Number(query.get("lon")), Number(query.get("lat"))];
                    if (inArea(p, network)) view.focus(p, 15);
                }
            })
            .catch(() => {
                notice("Map could not load. Use the fleet, route and stop lists.");
            });
    } catch (_) {
        notice("Service area could not load. Reload to restore the map.");
    }
    refresh();
    setInterval(refresh, 30000);
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            cancelAnimationFrame(frame);
            frame = 0;
            for (const e of fleet.values()) if (e.leg) settle(e);
        } else refresh();
    });
    reduced.addEventListener("change", () => {
        if (reduced.matches) for (const e of fleet.values()) if (e.leg) settle(e);
    });
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js?v=25").catch(() => {});
}
init();
