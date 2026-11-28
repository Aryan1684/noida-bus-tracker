const BUS_ROUTES = {
    UP14ST3546: "GR01",
    UP14TT1668: "GR01",
    UP14TT1667: "GR01",
    UP14TT1671: "GR01",
    UP14TT1679: "GR01",
    UP14TT1680: "GR01",
};

function getBusRoute(busId) {
    return (
        BUS_ROUTES[
            String(busId || "")
                .trim()
                .toUpperCase()
        ] || null
    );
}

function reportedRoute(bus) {
    const path = String(bus.route_path_id || "");
    if (path.startsWith("N-R02-ADVANT")) return "Expressway";
    if (path.startsWith("N-R01")) return "R1";
    if (path.startsWith("GR01-AIRPORT")) return null;
    return bus.route_id || getBusRoute(bus.bus_id);
}
