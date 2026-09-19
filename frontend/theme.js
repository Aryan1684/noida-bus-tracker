(function(){
    var key="noidaBusTheme";
    var saved=localStorage.getItem(key);
    var dark=saved==="dark";

    function apply(){
        document.body.classList.toggle("dark",dark);
        document.body.classList.add("page-ready");
        var icon=document.getElementById("themeIcon");
        var text=document.getElementById("themeText");
        if(icon)icon.textContent=dark?"☀":"☾";
        if(text)text.textContent=dark?"Light":"Dark";
    }

    function init(){
        apply();
        var button=document.getElementById("themeToggle");
        if(button){
            button.onclick=function(){
                dark=!dark;
                localStorage.setItem(key,dark?"dark":"light");
                apply();
            };
        }

        var tracker=document.getElementById("scrollTrackerBtn");
        if(tracker){
            tracker.onclick=function(){
                var section=document.querySelector(".tracker-section");
                if(section)section.scrollIntoView({behavior:"smooth",block:"start"});
            };
        }
    }

    if(document.readyState==="loading"){
        document.addEventListener("DOMContentLoaded",init);
    }else{
        init();
    }
})();
