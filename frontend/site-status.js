const TRACKER_API = /^deploy-preview-\d+--noidabus\.netlify\.app$/.test(location.hostname)
    ? "/fleet-data"
    : "https://noida-bus-tracker.onrender.com";

// All public tracking views honour the same switch as the operator dashboard.
const trackerReady = (function () {
    let checking = false;
    async function check() {
        if (checking) return false;
        checking = true;
        try {
            const response = await fetch(TRACKER_API + "/api/maintenance", {
                cache: "no-store",
                signal: AbortSignal.timeout(8000),
            });
            if (response.ok && (await response.json()).enabled) {
                location.replace("./maintenance.html");
                return false;
            }
        } catch (_) {
            // The public map can still show routes during a feed outage.
        } finally {
            checking = false;
        }
        document.documentElement.style.visibility = "";
        return true;
    }
    document.documentElement.style.visibility = "hidden";
    window.setInterval(check, 15000);
    return check();
})();
