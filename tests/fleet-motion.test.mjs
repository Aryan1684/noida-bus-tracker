import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
    eligibleBus,
    observation,
    canAnimate,
    shortestTurn,
    stateOf,
    movementPath,
    matchRoad,
    makeLeg,
    poseAt,
    distance,
} from "../frontend/fleet-motion.mjs";
const network = JSON.parse(readFileSync(new URL("../frontend/assets/noida-network.json", import.meta.url)));
const now = Date.parse("2026-11-26T09:00:00Z");
const raw = {
    bus_id: "BUS-A",
    latitude: 28.5641,
    longitude: 77.3358,
    depot_name: " Noida Electric ",
    speed: 20,
    timestamp: "2026-11-26 14:30:00",
    gps_age_seconds: 0,
};

test("both electric depots are allowed inside either city and other vehicles fail closed", () => {
    assert.ok(eligibleBus(raw, network));
    assert.ok(
        eligibleBus(
            { ...raw, latitude: 28.4652, longitude: 77.508, depot_name: " greater  noida electric " },
            network,
        ),
    );
    for (const patch of [
        { depot_name: "NOIDA" },
        { depot_name: "AGRA ELECTRIC" },
        { depot_name: null },
        { fuel_type: "Diesel" },
        { latitude: 28.6469, longitude: 77.3168 },
        { latitude: null },
    ])
        assert.equal(eligibleBus({ ...raw, ...patch }, network), false);
});
test("stopped, stale, unknown time and repeated fixes cannot animate", () => {
    const latest = observation(raw, now);
    const prev = { ...latest, point: [77.3348, 28.5641], time: now - 30000 };
    assert.equal(stateOf(latest, now), "Moving");
    assert.ok(canAnimate(prev, latest, now));
    for (const fix of [
        { ...latest, stale: true },
        { ...latest, time: null },
        { ...latest, parked: true },
        { ...latest, time: prev.time },
        { ...latest, freshUntil: now - 1 },
    ])
        assert.equal(canAnimate(prev, fix, now), false);
    assert.equal(stateOf(observation({ ...raw, snapshot_age_seconds: 180 }, now), now), "Last known");
    assert.equal(stateOf(latest, now + 121000), "Last known");
    assert.equal(observation({ ...raw, timestamp: "2026-11-26T14:30:00Z" }, now).time, now);
    assert.equal(canAnimate(prev, { ...latest, point: [77.53, 28.55] }, now), false);
});
test("street interpolation preserves bends, distance and endpoints in either direction", () => {
    const a = [77.3, 28.5],
        corner = [77.301, 28.5],
        b = [77.301, 28.501],
        route = { paths: [[a, corner, b]] };
    for (const [from, to] of [
        [a, b],
        [b, a],
    ]) {
        const path = movementPath(from, to, route);
        assert.ok(path.includes(corner));
        const leg = makeLeg(path);
        assert.ok(distance(poseAt(leg, 0).point, from) < 0.001);
        assert.ok(distance(poseAt(leg, 1).point, to) < 0.001);
        assert.ok(distance(poseAt(leg, 0.5).point, corner) < 12);
    }
    assert.equal(shortestTurn(359, 2), 3);
    assert.equal(shortestTurn(1079, 2), 3);
    assert.equal(movementPath(a, [77.32, 28.55], null), null);
});

test("road matching accepts opposite travel, rejects cross streets, ambiguity and distant fixes", () => {
    const street=[[77.30,28.5],[77.31,28.5]],p=[77.305,28.50008];
    const hit=matchRoad(p,[street],270);
    assert.ok(distance(hit.point,[p[0],28.5])<0.1);
    assert.equal(Math.abs(shortestTurn(hit.heading,270)),0);
    assert.equal(matchRoad(p,[street],0),null);
    assert.equal(matchRoad([p[0],28.51],[street],90),null);
    assert.equal(matchRoad(p,[street,street.map(([x,y])=>[x,y+.00016])],90),null);
    assert.equal(movementPath(p,[77.3051,p[1]],null),null);
    assert.equal(movementPath(p,hit.point,{ paths: [street] }),null);
});

test("first observation prefers device north and accepts a saved travel bearing", () => {
    assert.equal(observation({ ...raw, gps_heading: 0, heading: 190 }, now).heading, 0);
    assert.equal(observation({ ...raw, gps_heading: 361, heading: "240" }, now).heading, 240);
    assert.equal(observation({ ...raw, heading: "   " }, now).heading, null);
});
