import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

class FleetScreen extends StatefulWidget {
  final String api;
  final Future<List<Map<String, dynamic>>> Function() catalogue;
  const FleetScreen({super.key, required this.api, required this.catalogue});
  @override
  State<FleetScreen> createState() => _FleetScreenState();
}

class _Bus {
  final String id, depot;
  final LatLng point;
  final double? bearing;
  final DateTime? freshUntil;
  final bool parked;
  const _Bus(this.id, this.depot, this.point, this.bearing, this.freshUntil, this.parked);

  static _Bus? read(Map row, DateTime now) {
    final depot = '${row['depot_name'] ?? ''}'.trim().toUpperCase().replaceAll(RegExp(r'\s+'), ' ');
    final fuel = '${row['fuel_type'] ?? ''}'.trim().toUpperCase();
    final id = '${row['bus_id'] ?? ''}'.trim().toUpperCase();
    if (!{'NOIDA ELECTRIC','GREATER NOIDA ELECTRIC'}.contains(depot) ||
        !{'','ELECTRIC','ELECTRICITY','BATTERY ELECTRIC','EV','BEV'}.contains(fuel) || id.isEmpty) return null;
    double? number(String key) => double.tryParse('${row[key]}');
    final lat = number('latitude'), lon = number('longitude');
    if (lat == null || lon == null || !lat.isFinite || !lon.isFinite ||
        lat.abs()>90 || lon.abs()>180 || (lat==0 && lon==0)) return null;
    var stamp = '${row['source_timestamp'] ?? row['timestamp'] ?? ''}'.trim().replaceFirst(' ', 'T');
    if (!RegExp(r'(Z|[+-]\d\d:?\d\d)$',caseSensitive:false).hasMatch(stamp)) stamp += '+05:30';
    var time = DateTime.tryParse(stamp);
    if (time != null && time.isAfter(now.add(const Duration(minutes:5))) && stamp.endsWith('Z')) {
      time = DateTime.tryParse('${stamp.substring(0,stamp.length-1)}+05:30');
    }
    var until = time?.add(const Duration(minutes:2));
    final age = number('gps_age_seconds');
    if (age != null && age.isFinite && until != null) {
      final limit = now.add(Duration(seconds:120-age.round()-(number('snapshot_age_seconds')??0).round()));
      if (limit.isBefore(until)) until = limit;
    }
    if (time == null || time.isAfter(now.add(const Duration(minutes:5))) ||
        ['data_stale','snapshot_stale','is_stale'].any((k)=>row[k]==true) || row['vehicle_status']=='no_signal') until=null;
    final bearings = [number('gps_heading'), number('heading')].whereType<double>().where((n)=>n>=0 && n<=360);
    return _Bus(id,depot,LatLng(lat,lon),bearings.firstOrNull,until,
      row['vehicle_status']=='stationary' || (number('speed')??99)<2);
  }

  String status(bool offline) => offline || !(freshUntil?.isAfter(DateTime.now())??false)
      ? 'Last known' : parked ? 'Stationary' : 'Fresh GPS';
}

class _FleetScreenState extends State<FleetScreen> with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  final map = MapController();
  final client = http.Client();
  late final AnimationController motion = AnimationController(vsync:this,duration:const Duration(seconds:3));
  Timer? timer;
  Map<String,_Bus> buses={};
  Map<String,LatLng> starts={};
  Map<String,double> angles={};
  List<Map<String,dynamic>> routes=[];
  String? selected, routeId, issue;
  bool busy=false, fitted=false, showLines=true;
  double zoom=11;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      _resume();
      await showDialog<void>(context:context,builder:(c)=>AlertDialog(
        title:const Text('About the fleet map'),
        content:const Text('Routes are approximate and may differ from the roads buses take. Vehicle positions come from GPS. A last-known position may be out of date.'),
        actions:[TextButton(onPressed:()=>Navigator.pop(c),child:const Text('Explore map'))]));
    });
  }
  void _resume() {
    timer?.cancel();
    unawaited(_refresh());
    timer=Timer.periodic(const Duration(seconds:15),(_)=>_refresh());
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if(state==AppLifecycleState.resumed) { _resume(); } else {timer?.cancel();}
  }
  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    timer?.cancel();client.close();motion.dispose();map.dispose();super.dispose();
  }
  LatLng _position(_Bus b) {
    final a=starts[b.id]??b.point,t=motion.value;
    return LatLng(a.latitude+(b.point.latitude-a.latitude)*t,a.longitude+(b.point.longitude-a.longitude)*t);
  }
  Future<void> _refresh() async {
    if(busy)return;
    setState(()=>busy=true);
    try {
      if(routes.isEmpty) {
        final catalogue=await widget.catalogue();
        if(!mounted)return;
        setState(()=>routes=catalogue);
      }
      final response=await client.get(Uri.parse('${widget.api}/api/buses')).timeout(const Duration(seconds:12));
      final data=jsonDecode(response.body);
      if(!mounted)return;
      if(data is Map && data['maintenance']==true){
        setState((){buses={};selected=null;issue='Fleet tracking is under maintenance.';});return;
      }
      if(response.statusCode!=200 || data['buses'] is! List)throw const FormatException();
      final now=DateTime.now(),next=<String,_Bus>{},from=<String,LatLng>{},directions=<String,double>{};
      for(final row in data['buses'] as List){
        if(row is! Map)continue;
        final b=_Bus.read(row,now);
        if(b==null)continue;
        next[b.id]=b;
        final previous=buses[b.id], distance=const Distance();
        final moved=previous==null?0.0:distance(previous.point,b.point);
        if(previous!=null && moved<1000 && b.status(false)=='Fresh GPS')from[b.id]=_position(previous);
        directions[b.id]=b.bearing??(previous!=null && moved>5 ? distance.bearing(previous.point,b.point):angles[b.id]??0);
      }
      setState((){buses=next;starts=from;angles=directions;issue=null;if(!next.containsKey(selected))selected=null;});
      if(MediaQuery.disableAnimationsOf(context)){motion.value=1;}else{motion.forward(from:0);}
      if(!fitted && next.isNotEmpty){fitted=true;_fit(next.values.map((b)=>b.point).toList());}
    }catch(_){if(mounted)setState(()=>issue='GPS feed unavailable');}
    finally{if(mounted)setState(()=>busy=false);}
  }

  void _fit(List<LatLng> points){
    if(points.isEmpty)return;
    if(points.length==1){map.move(points.first,15);return;}
    map.fitCamera(CameraFit.coordinates(coordinates:points,padding:const EdgeInsets.all(48),maxZoom:16));
  }
  Future<void> _explore() async {
    final query=ValueNotifier('');
    await showModalBottomSheet<void>(context:context,isScrollControlled:true,showDragHandle:true,builder:(sheet)=>SafeArea(child:SizedBox(
      height:MediaQuery.sizeOf(sheet).height*.7,child:Column(children:[
        Padding(padding:const EdgeInsets.symmetric(horizontal:16),child:TextField(onChanged:(v)=>query.value=v.trim().toLowerCase(),decoration:const InputDecoration(prefixIcon:Icon(Icons.search),hintText:'Search buses or routes'))),
        Expanded(child:ValueListenableBuilder<String>(valueListenable:query,builder:(_,q,__){
          final items=<Widget>[
            for(final b in buses.values.where((b)=>('${b.id} ${b.depot}').toLowerCase().contains(q)))
              ListTile(leading:const Icon(Icons.directions_bus),title:Text(b.id),subtitle:Text(b.status(issue!=null)),onTap:(){Navigator.pop(sheet);setState(()=>selected=b.id);map.move(b.point,17);}),
            for(final r in routes.where((r)=>('${r['id']} ${r['name']} ${r['stops']}').toLowerCase().contains(q)))
              ExpansionTile(title:Text('${r['id']} · ${r['name']}'),children:[
                ListTile(title:Text((r['stops'] as List).join(' → ')),subtitle:Text([r['note'],...(r['landmarks']??[])].whereType<String>().join(' · '))),
                if((r['paths'] as List).isNotEmpty)TextButton(onPressed:(){Navigator.pop(sheet);setState((){routeId=r['id'];selected=null;showLines=true;});_fit((r['paths'] as List).cast<List<LatLng>>().expand((p)=>p).toList());},child:const Text('Show route on map')),
              ]),
          ];return ListView(children:items.isEmpty?[const ListTile(title:Text('No matching buses or routes'))]:items);
        })),
      ]))));
    query.dispose();
  }

  @override
  Widget build(BuildContext context){
    final bus=buses[selected];
    return Scaffold(appBar:AppBar(title:const Text('Electric Fleet Map'),actions:[
      IconButton(tooltip:'Refresh buses',onPressed:busy?null:_refresh,icon:const Icon(Icons.refresh)),
      IconButton(tooltip:'Show all buses',onPressed:(){setState((){selected=null;routeId=null;});_fit(buses.values.map((b)=>b.point).toList());},icon:const Icon(Icons.center_focus_strong)),
    ]),body:Column(children:[Expanded(child:Stack(children:[
      FlutterMap(mapController:map,options:MapOptions(initialCenter:const LatLng(28.52,77.44),initialZoom:11,
        onPositionChanged:(camera,_){if((zoom-camera.zoom).abs()>.05)setState(()=>zoom=camera.zoom);}),children:[
        TileLayer(urlTemplate:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',userAgentPackageName:'com.noidabus.noida_bus_tracker'),
        if(showLines)PolylineLayer(polylines:[
          for(final r in routes)if(routeId==null || r['id']==routeId)
            for(final path in (r['paths'] as List).cast<List<LatLng>>())
              Polyline(points:path,strokeWidth:routeId==null?2:4,color:routeId==null?const Color(0x705145AD):const Color(0xff5145ad)),
        ]),
        AnimatedBuilder(animation:motion,builder:(_,__)=>MarkerLayer(markers:[
          for(final b in buses.values)Marker(point:_position(b),width:58,height:58,child:Semantics(button:true,label:'${b.id}, ${b.status(issue!=null)}',
            child:GestureDetector(behavior:HitTestBehavior.opaque,onTap:()=>setState(()=>selected=b.id),child:Center(child:Transform.rotate(angle:(angles[b.id]??0)*math.pi/180,child:CustomPaint(
              size:Size(20+(zoom-11).clamp(0,8)*1.4,31+(zoom-11).clamp(0,8)*2.3),
              painter:_Coach(b.status(issue!=null),b.id==selected),
            )))))),
        ])),
        const SimpleAttributionWidget(source:Text('OpenStreetMap contributors')),
      ]),
      Positioned(top:10,right:12,child:ActionChip(avatar:Icon(showLines?Icons.layers:Icons.layers_clear),label:Text(routeId??'Routes'),onPressed:()=>setState(()=>showLines=!showLines))),
    ])),SafeArea(top:false,child:ListTile(
      title:Text(bus?.id??issue??'${buses.length} electric buses'),
      subtitle:Text(bus!=null?'${bus.depot} · ${bus.status(issue!=null)}':busy?'Checking GPS…':issue!=null?'Pull up the fleet list for details':'Noida & Greater Noida electric depots'),
      trailing:FilledButton(onPressed:_explore,child:const Text('Explore')),
    ))]));
  }
}

class _Coach extends CustomPainter {
  final String status;final bool selected;
  const _Coach(this.status,this.selected);
  @override
  void paint(Canvas canvas,Size size){
    canvas.scale(size.width/24,size.height/42);
    final p=Paint()..color=const Color(0xff20253a);
    void box(double x,double y,double w,double h,double radius,Color c){
      p.color=c;canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(x,y,w,h),Radius.circular(radius)),p);
    }
    if(selected)box(0,0,24,42,6,const Color(0xff7363ff));
    for(final y in [8.0,29.0]){box(1,y,4,7,2,Colors.black87);box(19,y,4,7,2,Colors.black87);}
    box(3,1,18,40,5,const Color(0xff30364b));
    box(4,2,15,35,4,status=='Fresh GPS'?const Color(0xff188773):status=='Stationary'?const Color(0xff9b680b):const Color(0xff657582));
    box(6,4,11,5,2,const Color(0xffc7e5ef));
    p.color=Colors.white;
    canvas.drawPath(ui.Path()..moveTo(12,12)..lineTo(17,20)..lineTo(13.5,19)..lineTo(13.5,28)..lineTo(10.5,28)..lineTo(10.5,19)..lineTo(7,20)..close(),p);
  }
  @override
  bool shouldRepaint(_Coach other)=>status!=other.status||selected!=other.selected;
}
