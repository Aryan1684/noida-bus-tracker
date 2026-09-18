
(function () {
    var API = "https://noida-bus-tracker.onrender.com";
    var HISTORY_KEY = "noidaBusFeatureHistory";
    var FAVORITES_KEY = "noidaBusFavorites";
    var ALERT_KEY = "noidaNearbyAlert";
    var historyLimit = 10 * 60 * 1000;
    var buses = [];
    var followId = null;
    var trail = null;
    var landmarkLayer = null;
    var playbackTimer = null;
    var playbackMarker = null;
    var installPrompt = null;

    var landmarks = [
        ["Botanical Garden", 28.5672, 77.3346],
        ["Sector 37", 28.5650, 77.3440],
        ["Noida City Center", 28.5740, 77.3560],
        ["Sector 52", 28.5850, 77.3700],
        ["Parthala", 28.6075, 77.3755],
        ["Chaar Murti", 28.6020, 77.4180],
        ["Ek Murti", 28.6063, 77.4337],
        ["Surajpur", 28.5185, 77.4990],
        ["Pari Chowk", 28.4652, 77.5080]
    ];

    function addStyles() {
        var s = document.createElement("style");
        s.textContent =
            ".feature-toolbar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}" +
            ".feature-toolbar button,.feature-actions button{border:1px solid #e4e7ec;border-radius:8px;background:#fff;color:#344054;padding:8px 10px;font-size:10px;font-weight:700}" +
            ".feature-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}" +
            ".feature-summary div{padding:10px;border:1px solid #e4e7ec;border-radius:9px;background:#f8fafb;color:#667085;font-size:11px}" +
            ".feature-summary strong{display:block;color:#111827;margin-bottom:3px}" +
            ".feature-route{margin-top:8px;padding:8px 10px;border-radius:9px;background:#f8fafb;color:#475467;font-size:11px}" +
            ".feature-meta{margin-top:7px;color:#667085;font-size:11px!important}" +
            ".feature-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}" +
            ".feature-modal{position:fixed;inset:0;z-index:6000;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;padding:18px}" +
            ".feature-modal-card{width:min(440px,100%);background:#fff;border-radius:18px;padding:20px;box-shadow:0 25px 60px rgba(0,0,0,.22)}" +
            ".feature-modal-card h3{font-size:18px;margin-bottom:8px}.feature-modal-card p{font-size:12px;color:#667085;line-height:1.5}" +
            ".feature-modal-card select{width:100%;margin-top:8px;padding:10px;border:1px solid #e4e7ec;border-radius:8px}" +
            ".feature-modal-actions{display:flex;gap:8px;margin-top:14px}.feature-modal-actions button{flex:1;padding:10px;border:0;border-radius:8px;background:#111827;color:#fff;font-weight:700}" +
            ".feature-modal-actions .secondary{background:#f2f4f7;color:#344054}" +
            ".playback-marker{width:36px;height:36px;display:flex;align-items:center;justify-content:center;border:3px solid #fff;border-radius:50%;background:#16a34a;color:#fff;font-size:17px;box-shadow:0 3px 10px rgba(0,0,0,.25)}" +
            "@media(max-width:700px){.feature-toolbar{display:grid;grid-template-columns:1fr 1fr}.feature-summary{grid-template-columns:1fr}}";
        document.head.appendChild(s);
    }

    function readHistory() {
        try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "{}"); }
        catch (e) { return {}; }
    }

    function writeHistory(data) {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(data));
    }

    function savePositions(items) {
        var data = readHistory();
        var now = Date.now();

        items.forEach(function (bus) {
            if (!bus.bus_id) return;
            data[bus.bus_id] = data[bus.bus_id] || [];
            data[bus.bus_id].push({
                latitude: Number(bus.latitude),
                longitude: Number(bus.longitude),
                speed: Number(bus.speed) || 0,
                time: now
            });
            data[bus.bus_id] = data[bus.bus_id].filter(function (p) {
                return now - p.time <= historyLimit;
            });
        });

        writeHistory(data);
    }

    function busHistory(id) {
        return readHistory()[id] || [];
    }

    function distance(a,b,c,d) {
        var R=6371;
        var p1=a*Math.PI/180;
        var p2=c*Math.PI/180;
        var dp=(c-a)*Math.PI/180;
        var dl=(d-b)*Math.PI/180;
        var x=Math.sin(dp/2)*Math.sin(dp/2)+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)*Math.sin(dl/2);
        return R*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));
    }

    function heading(a,b,c,d) {
        var p1=a*Math.PI/180;
        var p2=c*Math.PI/180;
        var dl=(d-b)*Math.PI/180;
        var y=Math.sin(dl)*Math.cos(p2);
        var x=Math.cos(p1)*Math.sin(p2)-Math.sin(p1)*Math.cos(p2)*Math.cos(dl);
        return (Math.atan2(y,x)*180/Math.PI+360)%360;
    }

    function headingDiff(a,b) {
        var d=Math.abs(a-b);
        return Math.min(d,360-d);
    }

    function routeFor(bus) {
        if (bus.route && bus.likely_towards) {
            return {
                route: bus.route,
                confidence: bus.route_confidence || "Medium"
            };
        }

        var h=busHistory(bus.bus_id);
        if(h.length<2) return null;

        var first=h[0], last=h[h.length-1];
        if(distance(first.latitude,first.longitude,last.latitude,last.longitude)<0.08) return null;

        return null;
    }

    function currentSpeed(bus) {
        var h=busHistory(bus.bus_id);
        if(h.length>=2){
            var a=h[0], b=h[h.length-1];
            var mins=(b.time-a.time)/60000;
            var km=distance(a.latitude,a.longitude,b.latitude,b.longitude);
            if(mins>0 && km>0.03) return km/mins*60;
        }
        return Number(bus.speed)||0;
    }

    function dataQuality(bus) {
        var lat=Number(bus.latitude), lon=Number(bus.longitude);
        if(bus.vehicle_status==="no_signal") return "No signal";
        if(lat<27 || lat>29.5 || lon<76 || lon>78.5) return "Location may be inaccurate";
        return "Live";
    }

    function summary() {
        var target=typeof confirmedLocation!=="undefined" ? confirmedLocation : null;
        if(!target) return;

        var radius=document.getElementById("radiusSelect") ? document.getElementById("radiusSelect").value : 5;
        fetch(API+"/api/buses/nearby?lat="+target.lat+"&lon="+target.lon+"&radius="+radius)
            .then(function(r){return r.json();})
            .then(function(data){
                var old=document.getElementById("featureSummary");
                if(!old) return;
                var closest=data.closest_bus;
                var live=buses.filter(function(b){return b.vehicle_status==="live";}).length;
                var moving=buses.map(currentSpeed).filter(function(s){return s>2;});
                var avg=moving.length?moving.reduce(function(a,b){return a+b;},0)/moving.length:0;
                var congestion=moving.length<3?"Insufficient data":avg<15?"High":avg<25?"Medium":"Low";
                old.innerHTML="<div><strong>Closest bus</strong>"+(closest?closest.bus_id+" · "+closest.distance_km+" km":"None")+"</div>"+
                    "<div><strong>Congestion estimate</strong>"+congestion+"</div>"+
                    "<div><strong>Active nearby</strong>"+live+"</div>";
            })
            .catch(function(){});
    }

    function toolbar() {
        if(document.getElementById("advancedFeatures")) return;
        var section=document.querySelector(".bus-section");
        if(!section) return;

        var box=document.createElement("div");
        box.id="advancedFeatures";
        box.innerHTML=
            "<div class='feature-toolbar'>"+
            "<button id='featureAlert'>🔔 Nearby Alert</button>"+
            "<button id='featureFav'>❤️ Favorites</button>"+
            "<button id='featureStops'>🚏 Stops & Landmarks</button>"+
            "<button id='featureInstall' hidden>📱 Install App</button>"+
            "</div>"+
            "<div id='featureSummary' class='feature-summary'></div>";

        section.insertBefore(box,section.querySelector(".section-header"));

        document.getElementById("featureAlert").onclick=enableAlert;
        document.getElementById("featureFav").onclick=saveFavorite;
        document.getElementById("featureStops").onclick=toggleStops;
        document.getElementById("featureInstall").onclick=installPWA;

        renderFavorites();
    }

    function renderFavorites(){
        var existing=document.getElementById("favoriteLocations");
        if(existing) existing.remove();

        var favorites=JSON.parse(localStorage.getItem(FAVORITES_KEY)||"[]");
        if(!favorites.length) return;

        var box=document.createElement("div");
        box.id="favoriteLocations";
        box.className="feature-route";
        box.innerHTML="<strong>Favorites:</strong> "+favorites.map(function(item,index){
            return "<button data-fav='"+index+"' style='margin:3px;padding:5px;border:1px solid #e4e7ec;border-radius:6px;background:#fff'>"+item.name+"</button>";
        }).join("");

        box.querySelectorAll("[data-fav]").forEach(function(btn){
            btn.onclick=function(){
                var item=favorites[Number(btn.dataset.fav)];
                setLocationMarker(item.lat,item.lon);
                map.setView([item.lat,item.lon],15);
            };
        });

        var toolbarBox=document.getElementById("advancedFeatures");
        if(toolbarBox) toolbarBox.appendChild(box);
    }

    function saveFavorite(){
        var target=typeof confirmedLocation!=="undefined"&&confirmedLocation?confirmedLocation:typeof userLocation!=="undefined"?userLocation:null;
        if(!target){alert("Select a location first.");return;}
        var name=prompt("Name this location:","My place");
        if(!name)return;
        var favorites=JSON.parse(localStorage.getItem(FAVORITES_KEY)||"[]");
        favorites.push({name:name,lat:target.lat,lon:target.lon});
        localStorage.setItem(FAVORITES_KEY,JSON.stringify(favorites.slice(-10)));
        renderFavorites();
    }

    function enhance(){
        buses.forEach(function(bus){
            var card=document.getElementById("bus-card-"+bus.bus_id);
            if(!card || card.dataset.advanced==="true") return;

            var route=routeFor(bus);
            var routeText=route ? "Likely route: "+route.route+" · Confidence: "+route.confidence : "Route prediction: not enough movement data";
            var quality=dataQuality(bus);
            var history=busHistory(bus.bus_id);

            var meta=document.createElement("div");
            meta.className="feature-meta";
            meta.innerHTML="Data quality: <strong>"+quality+"</strong><br>History captured: "+history.length+" points";
            card.appendChild(meta);

            var routeBox=document.createElement("div");
            routeBox.className="feature-route";
            routeBox.textContent=routeText;
            card.appendChild(routeBox);

            var actions=document.createElement("div");
            actions.className="feature-actions";
            actions.innerHTML=
                "<button data-f='eta'>ETA</button>"+
                "<button data-f='follow'>"+(followId===bus.bus_id?"Following":"Follow")+"</button>"+
                "<button data-f='trail'>Trail</button>"+
                "<button data-f='play'>Playback</button>"+
                "<button data-f='share'>Share</button>"+
                "<button data-f='report'>Report</button>";

            actions.onclick=function(event){
                var btn=event.target.closest("button");
                if(!btn)return;
                event.stopPropagation();
                var type=btn.dataset.f;
                if(type==="eta") eta(bus);
                if(type==="follow") follow(bus);
                if(type==="trail") showTrail(bus);
                if(type==="play") playback(bus);
                if(type==="share") share(bus);
                if(type==="report") report(bus);
            };

            card.appendChild(actions);
            card.dataset.advanced="true";
        });
    }

    function eta(bus){
        var target=typeof confirmedLocation!=="undefined"?confirmedLocation:null;
        if(!target){alert("Select and confirm a location first.");return;}

        var km=distance(Number(bus.latitude),Number(bus.longitude),target.lat,target.lon);
        var speed=currentSpeed(bus);

        if(speed<3){alert("ETA unavailable while the bus is stationary or moving too slowly.");return;}
        var minutes=Math.max(1,Math.ceil(km/speed*60));
        alert("Approx ETA: "+minutes+" min\\nDistance: "+km.toFixed(2)+" km\\nBased on recent/current GPS speed.");
    }

    function follow(bus){
        followId=followId===bus.bus_id?null:bus.bus_id;
        if(followId){
            map.setView([bus.latitude,bus.longitude],16);
            updateLocationMessage("Following "+bus.bus_id+".");
        }else{
            updateLocationMessage("Bus follow mode stopped.");
        }
        enhance();
    }

    function showTrail(bus){
        if(trail){map.removeLayer(trail);trail=null;}
        var h=busHistory(bus.bus_id);
        if(h.length<2){alert("Keep the tracker open for a few refreshes to build history.");return;}
        trail=L.polyline(h.map(function(p){return [p.latitude,p.longitude];}),{weight:5}).addTo(map);
        map.fitBounds(trail.getBounds(),{padding:[30,30]});
    }

    function playback(bus){
        var h=busHistory(bus.bus_id);
        if(h.length<2){alert("Not enough recorded history yet.");return;}
        if(playbackTimer)clearInterval(playbackTimer);
        if(playbackMarker)map.removeLayer(playbackMarker);

        var points=h.map(function(p){return [p.latitude,p.longitude];});
        var line=L.polyline(points,{weight:5}).addTo(map);
        map.fitBounds(line.getBounds(),{padding:[30,30]});

        playbackMarker=L.marker(points[0],{
            icon:L.divIcon({className:"",html:"<div class='playback-marker'>▶</div>",iconSize:[36,36],iconAnchor:[18,18]})
        }).addTo(map);

        var i=0;
        playbackTimer=setInterval(function(){
            i++;
            if(i>=points.length){
                clearInterval(playbackTimer);
                playbackTimer=null;
                setTimeout(function(){map.removeLayer(line);},1000);
                return;
            }
            playbackMarker.setLatLng(points[i]);
        },500);
    }

    function share(bus){
        var url=location.origin+location.pathname+"?bus="+encodeURIComponent(bus.bus_id);
        if(navigator.share){
            navigator.share({title:"Noida Bus "+bus.bus_id,text:"Track this Noida Electric Bus",url:url}).catch(function(){});
        }else if(navigator.clipboard){
            navigator.clipboard.writeText(url).then(function(){alert("Live bus link copied.");});
        }else{
            prompt("Copy this link:",url);
        }
    }

    function focusSharedBus(){
        var params=new URLSearchParams(location.search);
        var busId=params.get("bus");
        if(!busId)return;

        var tries=0;
        var timer=setInterval(function(){
            tries++;
            var bus=buses.find(function(item){return item.bus_id===busId;});
            if(bus){
                clearInterval(timer);
                if(typeof focusBusOnMap==="function")focusBusOnMap(busId);
                if(typeof map!=="undefined")map.setView([bus.latitude,bus.longitude],16);
                var card=document.getElementById("bus-card-"+busId);
                if(card){
                    card.scrollIntoView({behavior:"smooth",block:"center"});
                    card.classList.add("shared-bus-highlight");
                }
            }
            if(tries>30)clearInterval(timer);
        },500);
    }

    function report(bus){
        var choice=prompt("Report:\\n1 Not moving\\n2 Wrong location\\n3 Already passed\\n4 Occupancy");
        var types={"1":"not_moving","2":"wrong_location","3":"already_passed","4":"occupancy"};
        var type=types[choice];
        if(!type)return;

        var value="";
        if(type==="occupancy"){
            var o=prompt("Occupancy:\\n1 Empty\\n2 Seats available\\n3 Crowded\\n4 Full");
            value=({"1":"empty","2":"seats_available","3":"crowded","4":"full"})[o]||"";
            if(!value)return;
        }

        var form=new URLSearchParams();
        form.set("form-name","bus-reports");
        form.set("bus_id",bus.bus_id);
        form.set("report_type",type);
        form.set("value",value);
        form.set("note","");

        fetch("/",{
            method:"POST",
            headers:{"Content-Type":"application/x-www-form-urlencoded"},
            body:form.toString()
        }).then(function(r){
            if(!r.ok)throw new Error("failed");
            alert("Thanks. Your report was submitted.");
        }).catch(function(){alert("Could not submit the report right now.");});
    }

    function toggleStops(){
        if(landmarkLayer){
            map.removeLayer(landmarkLayer);
            landmarkLayer=null;
            return;
        }

        landmarkLayer=L.layerGroup();
        landmarks.forEach(function(item){
            L.circleMarker([item[1],item[2]],{radius:6,weight:2})
                .bindPopup("<strong>"+item[0]+"</strong><br>Route landmark / stop context")
                .addTo(landmarkLayer);
        });
        landmarkLayer.addTo(map);
    }

    function enableAlert(){
        if(!("Notification" in window)){alert("Notifications are not supported in this browser.");return;}
        Notification.requestPermission().then(function(permission){
            if(permission==="granted"){
                localStorage.setItem(ALERT_KEY,"true");
                alert("Nearby bus alerts enabled.");
            }
        });
    }

    function checkAlert(){
        if(localStorage.getItem(ALERT_KEY)!=="true")return;
        var bus=buses.find(function(item){return Number(item.distance_km)<=0.5;});
        if(!bus)return;

        var last=Number(localStorage.getItem("lastNoidaBusAlert")||0);
        if(Date.now()-last<5*60*1000)return;
        localStorage.setItem("lastNoidaBusAlert",String(Date.now()));

        navigator.serviceWorker.getRegistration().then(function(reg){
            if(reg)reg.showNotification("Nearby electric bus",{
                body:bus.bus_id+" is "+bus.distance_km+" km away.",
                icon:"/icon.svg"
            });
        });
    }

    function initPWA(){
        var manifest=document.createElement("link");
        manifest.rel="manifest";
        manifest.href="manifest.json";
        document.head.appendChild(manifest);

        if("serviceWorker" in navigator){
            navigator.serviceWorker.register("sw.js").catch(function(e){console.error(e);});
        }

        window.addEventListener("beforeinstallprompt",function(event){
            event.preventDefault();
            installPrompt=event;
            var button=document.getElementById("featureInstall");
            if(button)button.hidden=false;
        });
    }

    function installPWA(){
        if(!installPrompt)return;
        installPrompt.prompt();
        installPrompt.userChoice.then(function(){installPrompt=null;});
    }

    function wrapDisplay(){
        if(typeof window.displayBuses!=="function" || window.displayBuses.__featureWrapped)return;
        var original=window.displayBuses;
        var wrapped=function(items){
            buses=items||[];
            savePositions(buses);
            original.apply(this,arguments);
            setTimeout(function(){
                toolbar();
                enhance();
                summary();
                checkAlert();
                focusSharedBus();
                if(followId){
                    var bus=buses.find(function(item){return item.bus_id===followId;});
                    if(bus)map.setView([bus.latitude,bus.longitude],16);
                }
            },80);
        };
        wrapped.__featureWrapped=true;
        window.displayBuses=wrapped;
    }

    function init(){
        addStyles();
        initPWA();
        toolbar();
        wrapDisplay();
    }

    var observer=new MutationObserver(function(){
        toolbar();
        wrapDisplay();
    });

    observer.observe(document.documentElement,{childList:true,subtree:true});
    setTimeout(init,300);
})();
