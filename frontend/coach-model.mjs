// Orthographic projection of one electric coach, in metres. Both map engines use the same artwork.
const cache = new Map();
export function coachArtwork(heading, tilt) {
    const key = heading + "/" + tilt;
    if (cache.has(key)) return cache.get(key);
    const rad = Math.PI / 180, c = Math.cos(heading * rad), s = Math.sin(heading * rad);
    const up = Math.cos(tilt * rad), depth = Math.sin(tilt * rad);
    let svg = "";
    function polygon(points, fill) {
        const xy = points.map(([x,y,z]) => {
            const u = x*c-y*s, v = x*s+y*c;
            return (64+u*8.3).toFixed(2)+","+(68+(v*up-z*depth)*8.3).toFixed(2);
        });
        svg += '<polygon points="'+xy.join(" ")+'" fill="'+fill+'"/>';
    }
    function side(x,y1,y2,z1,z2,color) {
        polygon([[x,y1,z1],[x,y2,z1],[x,y2,z2],[x,y1,z2]],color);
    }
    function end(y,x1,x2,z1,z2,color) {
        polygon([[x1,y,z1],[x2,y,z1],[x2,y,z2],[x1,y,z2]],color);
    }
    function top(z,x1,x2,y1,y2,color) {
        polygon([[x1,y1,z],[x2,y1,z],[x2,y2,z],[x1,y2,z]],color);
    }
    function rim(x,y,r,color) {
        polygon(Array.from({length:32},(_,i)=>[x,y+r*Math.cos(i*Math.PI/16),.72+r*Math.sin(i*Math.PI/16)]),color);
    }
    function wheel(x,y) {
        const outer=x*1.04, inner=x*.71;
        for(let i=0;i<24;i++) {
            const a=i*Math.PI/12,b=(i+1)*Math.PI/12;
            polygon([[inner,y+.72*Math.cos(a),.72+.72*Math.sin(a)],[outer,y+.72*Math.cos(a),.72+.72*Math.sin(a)],
                [outer,y+.72*Math.cos(b),.72+.72*Math.sin(b)],[inner,y+.72*Math.cos(b),.72+.72*Math.sin(b)]],"#172229");
        }
        rim(outer,y,.72,"#142027");rim(outer,y,.45,"#657781");rim(outer,y,.33,"#d2dedf");rim(outer,y,.14,"#45565b");
    }
    const x = (s>=0?1:-1)*1.42, y = (c>=0?1:-1)*5.9;
    top(.02,-1.48,1.6,-5.65,6.02,"#37544744");
    for(const axle of [-3.65,3.55]) wheel(-x,axle);
    side(x,-5.9,5.9,.69,3.18,"var(--body)");
    side(x,-5.85,5.85,1.24,1.38,"var(--accent)");
    side(x,-5.65,5.65,1.66,2.98,"#1c3441");
    for(let j=0;j<7;j++){
        const a=-5.52+j*1.57;
        side(x,a,a+1.46,1.79,2.87,j%2?"#385c69":"#4c707a");
        side(x,a,a+1.46,2.72,2.83,"#77969b");
    }
    end(y,-1.42,1.42,.69,3.18,"var(--skirt)");
    end(y,-1.28,1.28,1.48,2.95,"#1d3541");
    end(y,-1.2,1.2,2.2,2.72,"#62818b");
    for(const sign of [-1,1])end(y,sign*.84,sign*1.26,1,1.2,y<0?"#fff3bc":"#fa654d");
    top(3.2,-1.42,1.42,-5.9,5.9,"#dbe5db");
    top(3.23,-1.02,1.02,1.8,5.2,"#aab9b8");
    for(let j=0;j<9;j++)top(3.25,-.84,.84,2+j*.34,2.12+j*.34,"#798c8c");
    // Paint the arrow in the roof plane with its tip towards the windscreen (negative y).
    svg += '<g opacity="var(--roof-arrow-opacity,0)">';
    polygon([[0,-5.1,3.21],[1.30,-1.45,3.21],[.65,-1.76,3.21],[.65,1.22,3.21],
        [-.65,1.22,3.21],[-.65,-1.76,3.21],[-1.30,-1.45,3.21]],"#103f43");
    polygon([[0,-4.48,3.21],[.91,-2.05,3.21],[.40,-2.30,3.21],[.40,.88,3.21],
        [-.40,.88,3.21],[-.40,-2.30,3.21],[-.91,-2.05,3.21]],"#ffffff");
    svg += '</g>';
    // Draw the outboard sidewall last, clear of the skirt, with the tread below the chassis.
    for(const axle of [-3.65,3.55])wheel(x,axle);
    cache.set(key,svg);
    return svg;
}

export function drawCoach(el, heading, tilt) {
    const angle = ((Math.round(heading/5)*5)%360+360)%360;
    const pitch = Math.round(Math.min(75,Math.max(20,tilt))/5)*5;
    const frame = angle+"/"+pitch;
    if(el.dataset.frame === frame)return;
    el.dataset.frame=frame;
    // Share geometry across the fleet. Each moving marker updates only its reference.
    const ns = "http://www.w3.org/2000/svg";
    const id = "coach-frame-" + angle + "-" + pitch;
    if (!document.getElementById(id)) {
        const symbol = document.createElementNS(ns,"symbol");
        symbol.id = id;
        symbol.setAttribute("viewBox","0 0 128 128");
        symbol.innerHTML = coachArtwork(angle,pitch);
        document.querySelector("svg.symbols defs").append(symbol);
    }
    let use = el.firstElementChild;
    if (!use) {
        use = document.createElementNS(ns,"use");
        el.append(use);
    }
    use.setAttribute("href","#"+id);
}
