(function () {
    const API = "https://noida-bus-tracker.onrender.com";
    const SESSION_KEY = "noidaBusAnalyticsSession";
    const LOCATION_CONSENT_KEY = "noidaBusApproxLocationConsent";

    function sessionId() {
        let id = sessionStorage.getItem(SESSION_KEY);

        if (!id) {
            id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(36).slice(2);
            sessionStorage.setItem(SESSION_KEY, id);
        }

        return id;
    }

    function track(eventName, metadata) {
        if (!eventName) return;

        fetch(API + "/api/analytics/event", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({
                event_name: eventName,
                path: location.pathname,
                session_id: sessionId(),
                metadata: metadata || {}
            }),
            keepalive: true
        }).catch(() => {});
    }

    function shareApproximateLocation() {
        if (!navigator.geolocation) {
            alert("Location sharing is not supported by this browser.");
            return;
        }

        const accepted = confirm(
            "Share an approximate location for this visit? Your location will be rounded to about 1 km, used only to understand where people need better bus coverage, and shown in admin analytics only as an aggregated area with at least 3 shares."
        );

        if (!accepted) return;

        localStorage.setItem(LOCATION_CONSENT_KEY, "true");

        navigator.geolocation.getCurrentPosition(
            function (position) {
                fetch(API + "/api/analytics/location", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    body: JSON.stringify({
                        latitude: Number(position.coords.latitude),
                        longitude: Number(position.coords.longitude),
                        path: location.pathname,
                        session_id: sessionId()
                    }),
                    keepalive: true
                }).then(function (response) {
                    if (!response.ok) throw new Error("location analytics failed");
                    alert("Thanks. Only an approximate area was shared.");
                }).catch(function () {
                    alert("Could not share the approximate area right now.");
                });
            },
            function () {
                alert("Could not get your location.");
            },
            {
                enableHighAccuracy: false,
                timeout: 8000,
                maximumAge: 60000
            }
        );
    }

    function bind() {
        track("page_view", {
            referrer: document.referrer ? document.referrer.slice(0, 200) : ""
        });

        document.addEventListener("click", function (event) {
            const target = event.target.closest("button, a");

            if (!target) return;

            if (target.id === "shareApproxLocationBtn") {
                shareApproximateLocation();
                return;
            }

            if (target.id === "refreshBtn") {
                track("refresh");
                return;
            }

            if (target.id === "locationBtn" || target.id === "finderLocationBtn" || target.id === "mapLocateBtn") {
                track("location_used");
                return;
            }

            if (target.id === "shareLocationBtn") {
                track("location_shared", {source: "map_share"});
                return;
            }

            if (target.id === "selectedShareBtn") {
                track("bus_shared");
                return;
            }

            if (target.id === "feedbackBtn") {
                track("feedback_opened");
                return;
            }

            if (target.closest(".bus-card")) {
                const card = target.closest(".bus-card");
                const busId = card.id.replace("bus-card-", "");
                track("bus_selected", {bus_id: busId});
                return;
            }

            if (target.matches(".search-result")) {
                track("place_search", {
                    place: (target.textContent || "").trim().slice(0, 120)
                });
            }
        });
    }

    window.noidaBusAnalytics = {
        track: track,
        shareApproximateLocation: shareApproximateLocation
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind, {once: true});
    } else {
        bind();
    }
})();