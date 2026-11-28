import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

// The map and route overlays share a transform, so hits follow the road plane.
class TransitMapView extends StatefulWidget {
  final Widget map;
  const TransitMapView({super.key, required this.map});
  @override
  State<TransitMapView> createState() => _TransitMapViewState();
}
class _TransitMapViewState extends State<TransitMapView> {
  bool pitched = true;
  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (_, box) {
    final h = box.maxHeight;
    return ClipRect(child: Stack(fit: StackFit.expand, children: [
      OverflowBox(maxWidth: box.maxWidth * (pitched ? 1.15 : 1),
        maxHeight: h * (pitched ? 1.52 : 1),
        child: Transform(alignment: Alignment.center,
          transform: Matrix4.identity()..setEntry(3, 2, pitched ? -0.22 / h : 0)..rotateX(pitched ? .63 : 0),
          child: SizedBox(width: box.maxWidth * (pitched ? 1.15 : 1),height: h * (pitched ? 1.52 : 1),child: widget.map))),
      Positioned(left: 8, top: 8, child: FilterChip(label: const Text('3D'), selected: pitched,
        onSelected: (value) => setState(() => pitched = value))),
      const Positioned(bottom: 2,right: 4,child: ColoredBox(color: Color(0xddffffff),
        child: Text('© OpenStreetMap contributors',style: TextStyle(fontSize: 10,color: Colors.black87)))),
    ]));
  });
}

// Orthographic projection of the website's 11.8 m coach, with the front at -y.
class CoachView extends StatelessWidget {
  final double bearing;
  final String status;
  final bool selected;
  const CoachView({super.key,required this.bearing,required this.status,required this.selected});
  @override
  Widget build(BuildContext context) {
    final camera = MapCamera.of(context);
    final size = (43 + math.pow(2, (camera.zoom - 15) / 2) * 6).clamp(43, 108).toDouble();
    return Center(child: SizedBox.square(dimension: size, child: RepaintBoundary(child: CustomPaint(
      painter: _CoachPainter(((bearing+camera.rotation)/5).round()*5,
        (45+(camera.zoom-12).clamp(0,8)*2).round(),status,selected)))));
  }
}

typedef _Point = (double,double,double);
class _CoachPainter extends CustomPainter {
  final int heading, tilt;
  final String status;
  final bool selected;
  const _CoachPainter(this.heading,this.tilt,this.status,this.selected);
  @override
  void paint(Canvas canvas,Size size){
    canvas.scale(size.width/128,size.height/128);
    final h=heading*math.pi/180,t=tilt*math.pi/180;
    final c=math.cos(h),s=math.sin(h),u=math.cos(t),d=math.sin(t);
    final p=Paint();
    void polygon(List<_Point> points,int fill){
      final path=ui.Path();
      for(var i=0;i<points.length;i++){
        final (x,y,z)=points[i];
        final a=64+(x*c-y*s)*8.3,b=68+((x*s+y*c)*u-z*d)*8.3;
        if(i==0){path.moveTo(a,b);}else{path.lineTo(a,b);}
      }
      canvas.drawPath(path..close(),p..color=Color(fill));
    }
    void side(double x,double a,double b,double lo,double hi,int color)=>
      polygon([(x,a,lo),(x,b,lo),(x,b,hi),(x,a,hi)],color);
    void end(double y,double a,double b,double lo,double hi,int color)=>
      polygon([(a,y,lo),(b,y,lo),(b,y,hi),(a,y,hi)],color);
    void top(double z,double a,double b,double lo,double hi,int color)=>
      polygon([(a,lo,z),(b,lo,z),(b,hi,z),(a,hi,z)],color);
    void rim(double x,double y,double radius,int fill)=>polygon([
      for(int i=0;i<24;i++) (x,y+radius*math.cos(i*math.pi/12),.72+radius*math.sin(i*math.pi/12))],fill);
    void wheel(double x,double y){
      rim(x*.87,y,.72,0xff172229);rim(x*1.04,y,.72,0xff142027);
      rim(x*1.04,y,.45,0xff657781);rim(x*1.04,y,.33,0xffd2dedf);rim(x*1.04,y,.14,0xff45565b);
    }
    final x=s>=0?1.42:-1.42,y=c>=0?5.9:-5.9;
    final fresh=status=='Fresh GPS',parked=status=='Stationary';
    if(selected)canvas.drawOval(const Rect.fromLTWH(12,42,104,46),p..color=const Color(0x66796bef));
    top(.02,-1.48,1.6,-5.65,6.02,0x44375447);
    for(final axle in [-3.65,3.55]) {wheel(-x,axle);}
    side(x,-5.9,5.9,.69,3.18,fresh?0xff059b78:parked?0xffd89827:0xff91a09b);
    side(x,-5.85,5.85,1.24,1.38,fresh?0xffc6ff79:0xfffff2ac);
    side(x,-5.65,5.65,1.66,2.98,0xff1c3441);
    for(int j=0;j<7;j++){
      final a=-5.52+j*1.57;
      side(x,a,a+1.46,1.79,2.87,j.isOdd?0xff385c69:0xff4c707a);
      side(x,a,a+1.46,2.72,2.83,0xff77969b);
    }
    end(y,-1.42,1.42,.69,3.18,fresh?0xff006856:parked?0xff916216:0xff61736e);
    end(y,-1.28,1.28,1.48,2.95,0xff1d3541);end(y,-1.2,1.2,2.2,2.72,0xff62818b);
    for(final a in [-1,1]){end(y,a*.84,a*1.26,1,1.2,y<0?0xfffff3bc:0xfffa654d);}
    top(3.2,-1.42,1.42,-5.9,5.9,0xffdbe5db);top(3.23,-1.02,1.02,1.8,5.2,0xffaab9b8);
    for(int j=0;j<9;j++){top(3.25,-.84,.84,2+j*.34,2.12+j*.34,0xff798c8c);}
    if(fresh){
      polygon([(0,-5.1,3.21),(1.3,-1.45,3.21),(.65,-1.76,3.21),(.65,1.22,3.21),(-.65,1.22,3.21),(-.65,-1.76,3.21),(-1.3,-1.45,3.21)],0xff103f43);
      polygon([(0,-4.48,3.21),(.91,-2.05,3.21),(.4,-2.30,3.21),(.4,.88,3.21),(-.4,.88,3.21),(-.4,-2.30,3.21),(-.91,-2.05,3.21)],0xffffffff);
    }
    for(final axle in [-3.65,3.55]){wheel(x,axle);}
  }
  @override
  bool shouldRepaint(_CoachPainter old)=>heading!=old.heading||tilt!=old.tilt||status!=old.status||selected!=old.selected;
}
