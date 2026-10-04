(function () {
    function mergeServerHistory(items) {
        var data = {};

        try {
            data = JSON.parse(localStorage.getItem("noidaBusFeatureHistory") || "{}");
        } catch (_) {}

        (items || []).forEach(function (bus) {
            var history = Array.isArray(bus.prediction_history)
                ? bus.prediction_history
                : [];

            if (!bus.bus_id || history.length < 2) return;

            data[bus.bus_id] = history.map(function (point) {
                return {
                    latitude: Number(point.latitude),
                    longitude: Number(point.longitude),
                    speed: Number(point.speed) || 0,
                    time: point.time ? new Date(point.time).getTime() : Date.now()
                };
            }).filter(function (point) {
                return Number.isFinite(point.latitude) &&
                    Number.isFinite(point.longitude) &&
                    Number.isFinite(point.time);
            }).slice(-10);
        });

        try {
            localStorage.setItem("noidaBusFeatureHistory", JSON.stringify(data));
        } catch (_) {}
    }

    function bind() {
        if (typeof window.displayBuses !== "function") return;

        var original = window.displayBuses;
        if (original.__serverHistoryWrapped) return;

        var wrapped = function (items) {
            mergeServerHistory(items);
            return original.apply(this, arguments);
        };

        wrapped.__serverHistoryWrapped = true;
        window.displayBuses = wrapped;
    }

    function start() {
        bind();
        setTimeout(bind, 100);
        setTimeout(bind, 500);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, {once: true});
    } else {
        start();
    }
})();