// Positions use [longitude, latitude] throughout. Distances are local metres.
let networkPromise;
export function loadNetwork() {
    if (!networkPromise) {
        networkPromise = fetch(new URL("./assets/noida-network.json", import.meta.url))
            .then((response) => {
                if (!response.ok) throw new Error("Service area unavailable");
                return response.json();
            })
            .catch((error) => {
                networkPromise = null;
                throw error;
            });
    }
    return networkPromise;
}

export function inArea([x, y], network) {
    return network.boundaries.some((ring) => {
        let inside = false;
        for (let i = 1; i < ring.length; i++) {
            const [a, b] = ring[i - 1],
                [c, d] = ring[i];
            if (b > y !== d > y && x < ((c - a) * (y - b)) / (d - b) + a) inside = !inside;
        }
        return inside;
    });
}

export function eligibleBus(bus, network) {
    if (!bus?.bus_id || !bus.latitude || !bus.longitude) return false;
    const depot = String(bus.depot_name || "")
        .trim()
        .toUpperCase()
        .replace(/\s+/g, " ");
    const fuel = String(bus.fuel_type || "")
        .trim()
        .toUpperCase();
    return (
        ["NOIDA ELECTRIC", "GREATER NOIDA ELECTRIC"].includes(depot) &&
        ["", "ELECTRIC", "ELECTRICITY", "BEV", "EV", "BATTERY ELECTRIC"].includes(fuel) &&
        inArea([Number(bus.longitude), Number(bus.latitude)], network)
    );
}

export function observation(bus, now = Date.now()) {
    let stamp = String(bus.source_timestamp || bus.timestamp || "")
        .trim()
        .replace(" ", "T");
    if (stamp && !/(Z|[+-]\d\d:?\d\d)$/i.test(stamp)) stamp += "+05:30";
    let time = Date.parse(stamp);
    // The source sometimes labels an IST clock time with a Z suffix (same rule as ingestion).
    if (/Z$/i.test(stamp) && time > now + 300000) time = Date.parse(stamp.slice(0, -1) + "+05:30");
    if (!Number.isFinite(time) || time > now + 300000) time = null;
    const age = bus.gps_age_seconds;
    const ageAtRead = Number(age) + Number(bus.snapshot_age_seconds || 0);
    const freshUntil =
        time === null
            ? 0
            : Math.min(
                  time + 120000,
                  age != null && age !== "" && Number.isFinite(ageAtRead)
                      ? now + (120 - ageAtRead) * 1000
                      : Infinity,
              );
    const status = String(bus.vehicle_status || "").toLowerCase();
    const speed = bus.speed == null || bus.speed === "" ? null : Number(bus.speed);
    const heading = [bus.gps_heading, bus.heading]
        .filter(value => typeof value === "number" || (typeof value === "string" && value.trim()))
        .map(Number)
        .find(value => value >= 0 && value <= 360);
    return {
        id: String(bus.bus_id).trim().toUpperCase(),
        point: [Number(bus.longitude), Number(bus.latitude)],
        time,
        freshUntil,
        speed: Number.isFinite(speed) ? speed : null,
        stale: !!(bus.data_stale || bus.snapshot_stale || bus.is_stale || status === "no_signal"),
        parked: status === "stationary" || (speed != null && speed < 2),
        heading: heading == null ? null : heading % 360,
        depot: String(bus.depot_name).trim(),
        route: bus.route_id || null,
    };
}

export function stateOf(fix, now = Date.now()) {
    if (fix.stale || now >= fix.freshUntil) return "Last known";
    if (fix.parked) return "Stationary";
    return fix.speed >= 2 ? "Moving" : "Fresh GPS";
}

const east = 97780,
    north = 111190;
export function distance(a, b) {
    return Math.hypot((b[0] - a[0]) * east, (b[1] - a[1]) * north);
}
export function bearing(a, b) {
    return (Math.atan2((b[0] - a[0]) * east, (b[1] - a[1]) * north) * 180) / Math.PI;
}
function mix(a, b, t) {
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}
export function shortestTurn(a, b) {
    return ((((b - a + 180) % 360) + 360) % 360) - 180;
}

function nearest(path, point) {
    let best = { distance: Infinity };
    for (let i = 1; i < path.length; i++) {
        const a = path[i - 1],
            b = path[i];
        const dx = (b[0] - a[0]) * east,
            dy = (b[1] - a[1]) * north;
        const projection =
            ((point[0] - a[0]) * east * dx + (point[1] - a[1]) * north * dy) / (dx * dx + dy * dy || 1);
        const t = Math.max(0, Math.min(1, projection));
        const projected = mix(a, b, t),
            gap = distance(point, projected);
        if (gap < best.distance) best = { distance: gap, index: i - 1 + t, point: projected, bearing: bearing(a,b) };
    }
    return best;
}

// Match only nearby roads with a compatible axis. At ambiguous junctions keep the observed fix.
export function matchRoad(point, paths, heading) {
    let best = null, runnerUp = null;
    for (const path of paths) {
        if (path.length < 2) continue;
        const hit = nearest(path, point);
        if (hit.distance > 22) continue;
        const turn = heading == null ? 0 : Math.abs(shortestTurn(heading,hit.bearing));
        const error = Math.min(turn,180-turn);
        if (error > 45) continue;
        const score = hit.distance + error / 6;
        const candidate = {...hit, path, score, heading: heading == null ? null : hit.bearing + (turn>90 ? 180 : 0)};
        if (!best || score < best.score) {
            if (best && distance(hit.point,best.point)>4) runnerUp=best;
            best=candidate;
        } else if (distance(hit.point,best.point)>4 && (!runnerUp || score<runnerUp.score)) runnerUp=candidate;
    }
    return best && (!runnerUp || runnerUp.score-best.score>3) ? best : null;
}

// Use a mapped road only when both real fixes agree with the same short section.
export function movementPath(start, end, route) {
    const direct = distance(start, end);
    for (const path of route?.paths || []) {
        const a = nearest(path, start),
            b = nearest(path, end);
        if (!direct || Math.max(a.distance, b.distance) > 3) continue;
        const forward = a.index <= b.index;
        const lo = forward ? a : b,
            hi = forward ? b : a;
        const mid = path.slice(Math.floor(lo.index) + 1, Math.ceil(hi.index));
        const via = [start, a.point, ...(forward ? mid : mid.reverse()), b.point, end];
        const length = via.slice(1).reduce((n, p, i) => n + distance(via[i], p), 0);
        if (length <= direct * 1.65 + 12) return via;
    }
    return null;
}

export function makeLeg(points) {
    const lengths = [0];
    for (let i = 1; i < points.length; i++) lengths.push(lengths[i - 1] + distance(points[i - 1], points[i]));
    return { points, lengths, length: lengths[lengths.length - 1] };
}
export function poseAt(leg, fraction) {
    const target = Math.min(1, Math.max(0, fraction)) * leg.length;
    const { points, lengths } = leg;
    let i = 1;
    while (i < lengths.length - 1 && (lengths[i] < target || lengths[i] === lengths[i - 1])) i++;
    return {
        point: mix(points[i - 1], points[i], (target - lengths[i - 1]) / (lengths[i] - lengths[i - 1] || 1)),
        heading: bearing(points[i - 1], points[i]),
    };
}
export function canAnimate(previous, next, now = Date.now()) {
    if (
        !previous.time ||
        !next.time ||
        stateOf(previous, previous.time) === "Last known" ||
        stateOf(next, now) === "Last known" ||
        next.parked ||
        previous.stale
    )
        return false;
    const seconds = (next.time - previous.time) / 1000;
    const metres = distance(previous.point, next.point);
    return seconds > 0 && seconds <= 120 && metres > 5 && metres / seconds <= 25;
}
