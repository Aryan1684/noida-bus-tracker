const API="https://noida-bus-tracker.onrender.com";
const KEY="noidaBusAdminToken";
let token=sessionStorage.getItem(KEY)||"";
let map=null;
let layer=null;

function auth(){return {Accept:"application/json","X-Admin-Token":token};}
async function request(path){
  const r=await fetch(API+path,{headers:auth()});
  if(r.status===401) throw new Error("Invalid admin token.");
  if(!r.ok) throw new Error("Request failed: HTTP "+r.status);
  return r.json();
}
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));}
function rows(id,items,key){
  const box=document.getElementById(id); box.innerHTML="";
  if(!items.length){box.innerHTML="<p>No data yet.</p>";return;}
  items.forEach(x=>box.innerHTML+="<div class='row'><span>"+esc(x[key])+"</span><b>"+esc(x.count||0)+"</b></div>");
}
function chart(items){
  const box=document.getElementById("chart"); box.innerHTML="";
  const max=Math.max(1,...items.map(x=>Number(x.events)||0));
  items.forEach(x=>{
    const d=document.createElement("div"); d.className="bar"; d.style.height=Math.max(3,(Number(x.events)||0)/max*150)+"px"; d.title=x.date+" · "+x.events; box.appendChild(d);
  });
}
function demandMap(cells){
  if(!map){
    map=L.map("map").setView([28.5355,77.3910],11);
    L.tileLayer("https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=zDrcI9pwHS3FLOHuWQm3",{tileSize:512,zoomOffset:-1,attribution:"&copy; MapTiler &copy; OpenStreetMap contributors"}).addTo(map);
    layer=L.layerGroup().addTo(map);
  }
  layer.clearLayers();
  const points=[];
  cells.forEach(x=>{
    const lat=Number(x.latitude),lon=Number(x.longitude);
    if(!Number.isFinite(lat)||!Number.isFinite(lon))return;
    points.push([lat,lon]);
    L.circle([lat,lon],{radius:350,weight:1,fillOpacity:.3}).bindPopup("Approximate demand area · "+x.shares+" shares").addTo(layer);
  });
  if(points.length)map.fitBounds(points,{padding:[20,20],maxZoom:13});
}
function fleet(data){
  ["Total","Live","Stationary","NoSignal","Anomalies","Predictions","Corrected","Confidence"].forEach(()=>{});
  document.getElementById("fleetTotal").textContent=data.total;
  document.getElementById("fleetLive").textContent=data.live;
  document.getElementById("fleetStationary").textContent=data.stationary;
  document.getElementById("fleetNoSignal").textContent=data.no_signal;
  document.getElementById("fleetAnomalies").textContent=data.gps_anomalies;
  document.getElementById("fleetPredictions").textContent=data.predictions_available;
  document.getElementById("fleetCorrected").textContent=data.predictions_applied;
  document.getElementById("fleetConfidence").textContent=data.average_prediction_confidence==null?"—":Math.round(data.average_prediction_confidence*100)+"%";
  const box=document.getElementById("fleetTable");box.innerHTML="";
  data.buses.forEach(x=>{
    box.innerHTML+="<div class='row'><strong>"+esc(x.bus_id)+"</strong><small>"+esc(x.vehicle_status)+" · AI "+(x.prediction_confidence==null?"—":Math.round(Number(x.prediction_confidence)*100)+"%")+"</small></div>";
  });
}
async function load(){
  document.getElementById("error").hidden=true;
  try{
    const days=document.getElementById("days").value;
    const [a,f]=await Promise.all([request("/api/admin/analytics?days="+days),request("/api/admin/fleet")]);
    document.getElementById("events").textContent=a.total_events;
    document.getElementById("sessions").textContent=a.unique_sessions;
    document.getElementById("views").textContent=a.page_views;
    document.getElementById("selections").textContent=a.bus_selections;
    document.getElementById("locations").textContent=a.location_shares;
    document.getElementById("reports").textContent=a.reports_submitted;
    document.getElementById("storage").textContent="Storage: "+a.storage;
    chart(a.daily||[]);
    rows("eventTable",a.event_breakdown||[],"event");
    rows("busTable",a.top_buses||[],"bus_id");
    demandMap(a.location_cells||[]);
    fleet(f);
  }catch(e){
    const x=document.getElementById("error");x.textContent=e.message;x.hidden=false;
  }
}
function login(){
  const v=document.getElementById("token").value.trim();
  if(!v){document.getElementById("loginStatus").textContent="Enter the admin token.";return;}
  sessionStorage.setItem(KEY,v);token=v;
  request("/api/admin/analytics?days=7").then(()=>{
    document.getElementById("login").hidden=true;
    document.getElementById("dash").hidden=false;
    load();
  }).catch(e=>document.getElementById("loginStatus").textContent=e.message);
}
document.getElementById("loginBtn").onclick=login;
document.getElementById("token").onkeydown=e=>{if(e.key==="Enter")login();};
document.getElementById("refresh").onclick=load;
document.getElementById("days").onchange=load;
document.getElementById("logout").onclick=()=>{sessionStorage.removeItem(KEY);location.reload();};
if(token){document.getElementById("login").hidden=true;document.getElementById("dash").hidden=false;load();}