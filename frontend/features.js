
(function () {
    var API = "https://noida-bus-tracker.onrender.com";
    var HISTORY_KEY = "noidaBusFeatureHistory";
    var FAVORITES_KEY = "noidaBusFavorites";
    var ALERT_KEY = "noidaNearbyAlert";
    var historyLimit = 10 * 60 * 1000;
    var buses = [];
    var followId = null;
    var trail = null;
    var playbackTimer = null;
    var playbackMarker = null;
    var installPrompt = null;

    function addStyles() {
        var s=document.createElement("style");
        s.textContent=
            "#advancedFeatures{margin:8px 0 16px;padding:0;border:0;background:transparent}"+
            ".feature-toolbar{display:grid;grid-template-columns:1fr 1fr;gap:8px}"+
            ".feature-toolbar button{min-height:42px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--text);padding:8px 10px;font-size:10px;font-weight:800}"+
            ".feature-toolbar button:hover{background:var(--text);color:var(--bg)}"+
            ".feature-summary{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}"+
            ".feature-summary div{padding:10px 11px;border-radius:12px;background:var(--surface);color:var(--muted);font-size:9px;border:1px solid var(--line)}"+
            ".feature-summary strong{display:block;color:var(--text);font-size:10px;margin-bottom:3px}"+
            ".feature-route{margin-top:8px;padding:8px 10px;border-radius:9px;background:var(--surface2);color:var(--muted);font-size:10px;line-height:1.45}"+
            ".feature-meta{margin-top:8px;color:var(--muted);font-size:10px!important;line-height:1.5}"+
            ".feature-meta strong{color:var(--text)}"+
            ".feature-actions{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}"+
            ".feature-actions button:first-child{background:var(--accent);color:var(--dark);border-color:var(--accent)}"+
            ".playback-marker{width:34px;height:34px;display:grid;place-items:center;border:3px solid #fff;border-radius:50%;background:#111;color:#fff;font-size:14px;box-shadow:0 3px 10px rgba(0,0,0,.25)}"+
            ".feature-modal{position:fixed;inset:0;z-index:6000;background:rgba(15,18,15,.55);display:flex;align-items:center;justify-content:center;padding:18px}"+
            ".feature-modal-card{width:min(440px,100%);background:var(--surface);color:var(--text);border-radius:18px;padding:20px;box-shadow:0 25px 60px rgba(0,0,0,.22)}"+
            ".feature-modal-card h3{font-size:18px;margin-bottom:8px}.feature-modal-card p{font-size:12px;color:var(--muted);line-height:1.5}"+
            ".feature-modal-card select{width:100%;margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text)}"+
            "@media(max-width:700px){#advancedFeatures{margin:10px 0 0;padding:10px;border-radius:14px}.feature-toolbar{grid-template-columns:1fr 1fr;gap:7px}.feature-toolbar button,.feature-actions button{min-height:44px;font-size:9px;padding:8px 6px}.feature-summary{grid-template-columns:1fr 1fr;gap:7px}.feature-summary div{min-height:58px;padding:9px 8px}.feature-actions{grid-template-columns:1fr 1fr;gap:7px}.feature-actions button{font-size:9px}.feature-route{font-size:9px;padding:9px}.report-modal{padding:10px}.report-modal-card{max-height:calc(100dvh - 20px);border-radius:16px;padding:16px}.report-field select,.report-field textarea{font-size:12px;min-height:44px}.report-form-actions{position:sticky;bottom:0;padding-top:10px;background:var(--surface)}}";
        s.textContent += ".report-modal{position:fixed;inset:0;z-index:7000;background:rgba(11,13,16,.55);display:grid;place-items:center;padding:18px}.report-modal-card{width:min(520px,100%);max-height:min(700px,calc(100vh - 36px));overflow:auto;background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 28px 70px rgba(0,0,0,.24)}.report-modal-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.report-modal-head h3{font-size:18px}.report-close{width:30px;height:30px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--muted);font-size:18px}.report-field{display:grid;gap:5px;margin-top:13px}.report-field label,.report-consent{font-size:9px;font-weight:800;color:var(--text)}.report-field select,.report-field textarea{width:100%;border:1px solid var(--line);border-radius:10px;background:var(--surface2);color:var(--text);padding:10px;font-size:10px;outline:0}.report-field textarea{min-height:90px;resize:vertical}.report-help{font-size:8px;color:var(--muted);line-height:1.5}.report-consent{display:flex;align-items:flex-start;gap:8px;margin-top:13px;line-height:1.5}.report-consent input{margin-top:1px;accent-color:var(--accent);width:14px;height:14px}.report-form-actions{display:flex;gap:7px;margin-top:15px}.report-form-actions button{flex:1;min-height:38px;border:1px solid var(--line);border-radius:10px;padding:8px;font-size:10px;font-weight:900;background:var(--surface);color:var(--text)}.report-form-actions button[type=\"submit\"]{background:var(--primary);border-color:var(--primary);color:var(--primaryText)}.report-status{margin-top:10px;font-size:9px;color:var(--muted)}.footer-links{display:flex;flex-wrap:wrap;justify-content:center;gap:5px 11px;margin-top:8px}.footer-links a{color:inherit;text-decoration:none}.footer-links a:hover{text-decoration:underline}";document.head.appendChild(s);
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
                old.innerHTML="<div><strong>Closest bus</strong>"+(closest?closest.bus_id+" · "+closest.distance_km+" km":"None")+"</div>"+
                    "<div><strong>Active nearby</strong>"+live+"</div>";
            })
            .catch(function(){});
    }

    function toolbar() {
        if(document.getElementById("advancedFeatures")) return;
        var section=document.querySelector(".results-section");
        if(!section) return;

        var box=document.createElement("div");
        box.id="advancedFeatures";
        box.innerHTML=
            "<div class='feature-toolbar'>"+
            "<button id='featureAlert'>🔔 Nearby Alert</button>"+
            "<button id='featureFav'>❤️ Favorites</button>"+
            "</div>"+
            "<div id='featureSummary' class='feature-summary'></div>";

        section.insertBefore(box,section.querySelector(".section-header"));

        document.getElementById("featureAlert").onclick=enableAlert;
        document.getElementById("featureFav").onclick=saveFavorite;

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
            if(!card) return;

            if(card.dataset.advanced==="true"){
                var followButton=card.querySelector(".feature-actions button[data-f='follow']");
                if(followButton) followButton.textContent=followId===bus.bus_id?"Following":"Follow";
                return;
            }

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

            actions.addEventListener("pointerdown",function(event){
                var btn=event.target.closest("button");
                if(btn)event.stopPropagation();
            });

            actions.addEventListener("click",function(event){
                var btn=event.target.closest("button");
                if(!btn)return;
                event.preventDefault();
                event.stopPropagation();

                actions.querySelectorAll("button.action-pressed").forEach(function(item){
                    item.classList.remove("action-pressed");
                });
                btn.classList.add("action-pressed");
                window.setTimeout(function(){
                    btn.classList.remove("action-pressed");
                },220);

                var type=btn.dataset.f;
                if(type==="eta") eta(bus);
                if(type==="follow") follow(bus);
                if(type==="trail") showTrail(bus);
                if(type==="play") playback(bus);
                if(type==="share") share(bus);
                if(type==="report") report(bus);

                window.setTimeout(function(){btn.blur();},0);
            });

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

        document.querySelectorAll(".feature-actions button[data-f='follow']").forEach(function(button){
            var card=button.closest(".bus-card");
            if(!card)return;
            button.textContent=card.id==="bus-card-"+bus.bus_id && followId===bus.bus_id?"Following":"Follow";
        });

        if(followId){
            map.setView([bus.latitude,bus.longitude],16,{animate:true,duration:.35});
            updateLocationMessage("Following "+bus.bus_id+". The map will stay centered on this bus as new data arrives.");
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
        if(document.querySelector(".report-modal")) return;

        var modal=document.createElement("div");
        modal.className="report-modal";
        modal.setAttribute("role","dialog");
        modal.setAttribute("aria-modal","true");
        modal.setAttribute("aria-labelledby","reportTitle");

        modal.innerHTML=
            "<div class='report-modal-card'>"+
                "<div class='report-modal-head'>"+
                    "<div><p class='eyebrow'>BUS REPORT</p><h3 id='reportTitle'>Report "+bus.bus_id+"</h3></div>"+
                    "<button type='button' class='report-close' aria-label='Close report'>×</button>"+
                "</div>"+
                "<form class='report-form'>"+
                    "<div class='report-field'><label for='reportType'>What is wrong?</label><select id='reportType' required><option value=''>Choose an issue</option><option value='not_moving'>Bus is not moving</option><option value='wrong_location'>Location looks wrong</option><option value='already_passed'>Bus already passed</option><option value='occupancy'>Occupancy</option></select></div>"+
                    "<div class='report-field hidden' id='reportOccupancyField'><label for='reportOccupancy'>Occupancy</label><select id='reportOccupancy'><option value=''>Choose occupancy</option><option value='empty'>Empty</option><option value='seats_available'>Seats available</option><option value='crowded'>Crowded</option><option value='full'>Full</option></select></div>"+
                    "<div class='report-field'><label for='reportNote'>Additional note <span class='report-help'>Do not include your name, phone number, email, address, or other personal information.</span></label><textarea id='reportNote' maxlength='500' placeholder='Optional details...'></textarea></div>"+
                    "<label class='report-consent'><input id='reportConsent' type='checkbox' required><span>I understand that this report will be submitted through our form provider for service improvement. I have not included personal information. <a href='privacy.html' target='_blank' rel='noopener'>Privacy Notice</a></span></label>"+
                    "<div class='report-form-actions'><button type='button' class='report-cancel'>Cancel</button><button type='submit'>Submit report</button></div>"+
                    "<div class='report-status' aria-live='polite'></div>"+
                "</form>"+
            "</div>";

        document.body.appendChild(modal);

        var close=modal.querySelector(".report-close");
        var cancel=modal.querySelector(".report-cancel");
        var form=modal.querySelector(".report-form");
        var type=modal.querySelector("#reportType");
        var occupancyField=modal.querySelector("#reportOccupancyField");
        var occupancy=modal.querySelector("#reportOccupancy");
        var note=modal.querySelector("#reportNote");
        var consent=modal.querySelector("#reportConsent");
        var status=modal.querySelector(".report-status");

        function remove(){modal.remove();}

        close.addEventListener("click",remove);
        cancel.addEventListener("click",remove);
        modal.addEventListener("click",function(event){if(event.target===modal)remove();});
        document.addEventListener("keydown",function onKey(event){
            if(!document.body.contains(modal))return;
            if(event.key==="Escape"){document.removeEventListener("keydown",onKey);remove();}
        });

        type.addEventListener("change",function(){
            var isOccupancy=type.value==="occupancy";
            occupancyField.classList.toggle("hidden",!isOccupancy);
            occupancy.required=isOccupancy;
        });

        form.addEventListener("submit",function(event){
            event.preventDefault();
            if(!form.reportValidity())return;

            var formData=new URLSearchParams();
            formData.set("form-name","bus-reports");
            formData.set("bus_id",bus.bus_id || "");
            formData.set("report_type",type.value);
            formData.set("value",type.value==="occupancy"?occupancy.value:"");
            formData.set("note",note.value.trim());
            formData.set("consent","accepted");

            status.textContent="Submitting report...";

            fetch("/",{
                method:"POST",
                headers:{"Content-Type":"application/x-www-form-urlencoded"},
                body:formData.toString()
            }).then(function(response){
                if(!response.ok)throw new Error("failed");
                status.textContent="Report submitted. Thank you.";
                form.reset();
                occupancyField.classList.add("hidden");
                occupancy.required=false;
                setTimeout(remove,900);
            }).catch(function(){
                status.textContent="Could not submit the report right now. Please try again later.";
            });
        });

        type.focus();
    }
    function openFeedback(){
        if(document.querySelector(".feedback-modal")) return;

        var modal=document.createElement("div");
        modal.className="report-modal feedback-modal";
        modal.setAttribute("role","dialog");
        modal.setAttribute("aria-modal","true");
        modal.setAttribute("aria-labelledby","feedbackTitle");

        modal.innerHTML=
            "<div class='report-modal-card'>"+
                "<div class='report-modal-head'>"+
                    "<div><p class='eyebrow'>YOUR FEEDBACK</p><h3 id='feedbackTitle'>Help improve Noida Bus Tracker</h3></div>"+
                    "<button type='button' class='report-close' aria-label='Close feedback'>×</button>"+
                "</div>"+
                "<form class='feedback-form'>"+
                    "<div class='report-field'><label for='feedbackRating'>How would you rate the tracker?</label><select id='feedbackRating' required><option value=''>Choose a rating</option><option value='5'>5 · Excellent</option><option value='4'>4 · Good</option><option value='3'>3 · Okay</option><option value='2'>2 · Poor</option><option value='1'>1 · Very poor</option></select></div>"+
                    "<div class='report-field'><label for='feedbackType'>What is your feedback about?</label><select id='feedbackType' required><option value=''>Choose a category</option><option value='general'>General</option><option value='bus-data'>Bus data / accuracy</option><option value='location'>Location / map</option><option value='performance'>Speed / performance</option><option value='design'>Design / usability</option><option value='bug'>Bug or problem</option><option value='other'>Other</option></select></div>"+
                    "<div class='report-field'><label for='feedbackMessage'>Tell us what you think</label><textarea id='feedbackMessage' maxlength='1000' required placeholder='What should we improve? What worked well?'></textarea></div>"+
                    "<p class='report-help'>Please do not include your name, phone number, email, address, or other personal information.</p>"+
                    "<div class='report-form-actions'><button type='button' class='report-cancel'>Cancel</button><button type='submit'>Send feedback</button></div>"+
                    "<div class='report-status' aria-live='polite'></div>"+
                "</form>"+
            "</div>";

        document.body.appendChild(modal);

        var close=modal.querySelector(".report-close");
        var cancel=modal.querySelector(".report-cancel");
        var form=modal.querySelector(".feedback-form");
        var status=modal.querySelector(".report-status");
        var rating=modal.querySelector("#feedbackRating");
        var type=modal.querySelector("#feedbackType");
        var message=modal.querySelector("#feedbackMessage");

        function remove(){modal.remove();}

        close.addEventListener("click",remove);
        cancel.addEventListener("click",remove);
        modal.addEventListener("click",function(event){
            if(event.target===modal)remove();
        });

        function onKey(event){
            if(!document.body.contains(modal))return;
            if(event.key==="Escape"){
                document.removeEventListener("keydown",onKey);
                remove();
            }
        }
        document.addEventListener("keydown",onKey);

        form.addEventListener("submit",function(event){
            event.preventDefault();
            if(!form.reportValidity())return;

            var formData=new URLSearchParams();
            formData.set("form-name","site-feedback");
            formData.set("rating",rating.value);
            formData.set("feedback_type",type.value);
            formData.set("message",message.value.trim());

            status.textContent="Sending feedback...";

            fetch("/",{
                method:"POST",
                headers:{"Content-Type":"application/x-www-form-urlencoded"},
                body:formData.toString()
            }).then(function(response){
                if(!response.ok)throw new Error("failed");
                status.textContent="Thanks. Your feedback was submitted.";
                form.reset();
                setTimeout(remove,1200);
            }).catch(function(){
                status.textContent="Could not send feedback right now. Please try again.";
            });
        });

        rating.focus();
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

        var feedbackButton=document.getElementById("feedbackBtn");
        if(feedbackButton && feedbackButton.dataset.bound!=="true"){
            feedbackButton.dataset.bound="true";
            feedbackButton.addEventListener("click",openFeedback);
        }
    }

    var observer=new MutationObserver(function(){
        toolbar();
        wrapDisplay();
    });

    observer.observe(document.documentElement,{childList:true,subtree:true});
    setTimeout(init,300);
})();
