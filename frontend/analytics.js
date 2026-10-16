(function () {
    const API = "https://noida-bus-tracker.onrender.com";
    const SESSION_KEY = "noidaBusAnalyticsSession";
    const VISITOR_KEY = "noidaBusAnalyticsVisitor";
    const LOCATION_CONSENT_KEY = "noidaBusApproxLocationConsent";

    function makeId() {
        try {
            if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
        } catch (_) {}
        return String(Date.now()) + "-" + Math.random().toString(36).slice(2);
    }

    const SESSION_ACTIVITY_KEY = "noidaBusAnalyticsLastActivity";
    const SESSION_TIMEOUT_MS = 30 * 60 * 1000;
    let memorySessionId = "";
    let memorySessionActivity = 0;
    let memoryVisitorId = "";

    function sourceName() {
        try {
            const ua = window.navigator.userAgent || "";
            if (window.Android || window.AndroidBridge || window.ReactNativeWebView || /\bwv\b/i.test(ua)) {
                return "android";
            }
            const standalone = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
                window.navigator.standalone === true;
            return standalone ? "installed_app" : "web";
        } catch (_) {
            return "web";
        }
    }

    function clientVersionLabel(source) {
        let requested = "";
        try {
            requested = new URLSearchParams(location.search).get("app_version") || "";
        } catch (_) {}
        if (requested) return requested.slice(0, 40);
        if (source === "android") return "Android app · version not reported";
        if (source === "installed_app") return "Installed PWA";
        return "Web browser";
    }

    function referrerHost() {
        if (!document.referrer) return "";
        try {
            const referrer = new URL(document.referrer);
            return referrer.origin === location.origin ? "" : referrer.hostname;
        } catch (_) {
            return "";
        }
    }

    function sessionId() {
        const now = Date.now();
        try {
            let id = sessionStorage.getItem(SESSION_KEY);
            const lastActivity = Number(sessionStorage.getItem(SESSION_ACTIVITY_KEY) || 0);
            if (!id || !lastActivity || now - lastActivity > SESSION_TIMEOUT_MS) {
                id = makeId();
                sessionStorage.setItem(SESSION_KEY, id);
            }
            sessionStorage.setItem(SESSION_ACTIVITY_KEY, String(now));
            return id;
        } catch (_) {
            if (!memorySessionId || now - memorySessionActivity > SESSION_TIMEOUT_MS) {
                memorySessionId = makeId();
            }
            memorySessionActivity = now;
            return memorySessionId;
        }
    }

    function visitorId() {
        try {
            let id = localStorage.getItem(VISITOR_KEY);
            if (!id) {
                id = makeId();
                localStorage.setItem(VISITOR_KEY, id);
            }
            return id;
        } catch (_) {
            if (!memoryVisitorId) memoryVisitorId = makeId();
            return memoryVisitorId;
        }
    }

    function browserName() {
        const ua = navigator.userAgent || "";
        if (ua.includes("EdgA/") || ua.includes("EdgiOS/") || ua.includes("Edg/")) return "Edge";
        if (ua.includes("OPR/") || /Opera Mini/i.test(ua)) return "Opera";
        if (ua.includes("FxiOS/") || /Firefox/i.test(ua)) return "Firefox";
        if (ua.includes("CriOS/") || /Chrome/i.test(ua)) return "Chrome";
        if (/Safari/i.test(ua)) return "Safari";
        return "Other";
    }

    function osName() {
        const ua = navigator.userAgent || "";
        if (/Windows NT/i.test(ua)) return "Windows";
        if (/Android/i.test(ua)) return "Android";
        if (/iPhone|iPad|iPod/i.test(ua)) return "iOS";
        if (/Mac OS X/i.test(ua)) return "macOS";
        if (/Linux/i.test(ua)) return "Linux";
        return "Other";
    }

    function deviceType() {
        const width = Math.min(window.innerWidth || 9999, screen.width || 9999);
        if (/iPad|Tablet/i.test(navigator.userAgent || "") || (width >= 600 && width < 1100)) return "tablet";
        if (/Mobi|Android/i.test(navigator.userAgent || "") || width < 600) return "mobile";
        return "desktop";
    }

    function sharedContext() {
        const source = sourceName();
        return {
            event_name: "",
            path: location.pathname,
            session_id: sessionId(),
            visitor_id: visitorId(),
            source: source,
            app_version: clientVersionLabel(source),
            device_type: deviceType(),
            browser: browserName(),
            os: osName(),
            language: (navigator.language || "").slice(0, 20),
            referrer: referrerHost(),
            screen_width: Number(window.innerWidth || screen.width || 0),
            screen_height: Number(window.innerHeight || screen.height || 0),
            metadata: {}
        };
    }

    function track(eventName, metadata) {
        if (!eventName) return;

        const payload = sharedContext();
        payload.event_name = eventName;
        payload.metadata = metadata || {};

        fetch(API + "/api/analytics/event", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify(payload),
            keepalive: true,
            cache: "no-store"
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

        try { localStorage.setItem(LOCATION_CONSENT_KEY, "true"); } catch (_) {}

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
                        session_id: sessionId(),
                        visitor_id: visitorId(),
                        source: sourceName()
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
        const source = sourceName();
        track(source === "installed_app" ? "app_open" : "page_view", {
            title: document.title,
            referrer_type: referrerHost() ? "referral" : "direct",
            launch_mode: source === "installed_app" ? "standalone" : "browser"
        });

        window.addEventListener("appinstalled", function () {
            track("pwa_install");
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
                track("location_shared", { source: "map_share" });
                return;
            }

            if (target.id === "selectedShareBtn") {
                const id = document.getElementById("selectedBusId");
                track("bus_shared", { bus_id: id ? id.textContent.trim() : "" });
                return;
            }

            if (target.id === "feedbackBtn") {
                track("feedback_opened");
                return;
            }

            const moreAction = target.closest("[data-more]");
            if (moreAction) {
                if (moreAction.getAttribute("data-more") === "report") {
                    const card = moreAction.closest(".bus-card");
                    track("report_opened", { bus_id: card ? card.id.replace("bus-card-", "") : "" });
                }
                return;
            }

            if (target.closest(".feature-actions") || target.closest(".favorite-button")) return;

            if (target.closest(".bus-card")) {
                const card = target.closest(".bus-card");
                const busId = card.id.replace("bus-card-", "");
                track("bus_selected", { bus_id: busId });
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
        shareApproximateLocation: shareApproximateLocation,
        getVisitorId: visitorId,
        getSessionId: sessionId
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind, {once: true});
    } else {
        bind();
    }
})();
