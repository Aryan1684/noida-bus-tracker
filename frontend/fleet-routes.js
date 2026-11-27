const BUS_ROUTES = {
    UP80KT3702: "R1",
    UP80KT4582: "R1",
    UP70PT6077: "R1",
    UP70PT6268: "R1",
    UP80LT4113: "R1",
    UP80LT4117: "R1",
    UP80LT4126: "R1",
    UP80KT3630: "R1",
    UP80KT3703: "R1",
    UP70PT6330: "R1",
    UP80LT4114: "R1",
    UP80LT4120: "R1",
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
