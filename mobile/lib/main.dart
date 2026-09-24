import 'dart:async';
import 'dart:convert';
import 'dart:ui' as ui;import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() { WidgetsFlutterBinding.ensureInitialized(); runApp(const App()); }

class App extends StatefulWidget { const App({super.key}); @override State<App> createState()=>_AppState(); }
class _AppState extends State<App> { bool dark=false; @override Widget build(BuildContext c)=>MaterialApp(debugShowCheckedModeBanner:false,title:'Noida Bus Tracker',themeMode:dark?ThemeMode.dark:ThemeMode.light,theme:ThemeData(useMaterial3:true,scaffoldBackgroundColor:const Color(0xFFF4F6F8),colorScheme:ColorScheme.fromSeed(seedColor:const Color(0xFFB8F26B))),darkTheme:ThemeData(useMaterial3:true,brightness:Brightness.dark,colorScheme:ColorScheme.fromSeed(seedColor:const Color(0xFFB8F26B),brightness:Brightness.dark)),home:StartupSplash(child:Home(dark:dark,toggle:()=>setState(()=>dark=!dark)))); }

class StartupSplash extends StatefulWidget {
  final Widget child;

  const StartupSplash({
    super.key,
    required this.child,
  });

  @override
  State<StartupSplash> createState() => _StartupSplashState();
}

class _StartupSplashState extends State<StartupSplash>
    with TickerProviderStateMixin {
  late final AnimationController intro;
  late final AnimationController travel;

  @override
  void initState() {
    super.initState();

    intro = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    )..forward();

    travel = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    Future.delayed(const Duration(milliseconds: 2950), () {
      if (!mounted) return;

      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          pageBuilder: (_, __, ___) => widget.child,
          transitionDuration: const Duration(milliseconds: 650),
          transitionsBuilder: (_, animation, __, child) {
            final curved = CurvedAnimation(
              parent: animation,
              curve: Curves.easeOutCubic,
            );

            return FadeTransition(
              opacity: curved,
              child: ScaleTransition(
                scale: Tween<double>(
                  begin: .965,
                  end: 1,
                ).animate(curved),
                child: child,
              ),
            );
          },
        ),
      );
    });
  }

  @override
  void dispose() {
    intro.dispose();
    travel.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070A10),
      body: SafeArea(
        child: AnimatedBuilder(
          animation: Listenable.merge([intro, travel]),
          builder: (context, _) {
            final logoT = Curves.easeOutBack.transform(
              (intro.value * 1.55).clamp(0.0, 1.0),
            );
            final logoFade = Curves.easeOut.transform(
              (intro.value * 1.25).clamp(0.0, 1.0),
            );
            final titleT = Curves.easeOutCubic.transform(
              ((intro.value - .32) / .42).clamp(0.0, 1.0),
            );
            final subT = Curves.easeOutCubic.transform(
              ((intro.value - .50) / .28).clamp(0.0, 1.0),
            );
            final progressT = Curves.easeInOutCubic.transform(
              ((intro.value - .02) / .88).clamp(0.0, 1.0),
            );

            return Stack(
              children: [
                Positioned.fill(
                  child: CustomPaint(
                    painter: SplashRoutePainter(
                      progress: progressT,
                      travel: travel.value,
                    ),
                  ),
                ),
                Center(
                  child: Opacity(
                    opacity: logoFade,
                    child: Transform.scale(
                      scale: .72 + (.28 * logoT),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 118,
                            height: 118,
                            decoration: BoxDecoration(
                              color: const Color(0xFF101722),
                              borderRadius: BorderRadius.circular(34),
                              border: Border.all(
                                color: const Color(0xFFB8F26B)
                                    .withOpacity(.72),
                                width: 1.4,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFFB8F26B)
                                      .withOpacity(.10 + (.10 * logoFade)),
                                  blurRadius: 34,
                                  spreadRadius: 5 + (9 * logoFade),
                                ),
                              ],
                            ),
                            child: const Icon(
                              Icons.directions_bus_rounded,
                              color: Color(0xFFB8F26B),
                              size: 61,
                            ),
                          ),
                          const SizedBox(height: 26),
                          Opacity(
                            opacity: titleT,
                            child: Transform.translate(
                              offset: Offset(0, 20 * (1 - titleT)),
                              child: const Text(
                                'NOIDA BUS TRACKER',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 25,
                                  fontWeight: FontWeight.w900,
                                  letterSpacing: 1.5,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Opacity(
                            opacity: subT,
                            child: const Text(
                              'LIVE ELECTRIC BUS TRACKING',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: Color(0xFFB8F26B),
                                fontSize: 10,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 2.15,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Positioned(
                  left: 24,
                  right: 24,
                  bottom: 28,
                  child: Opacity(
                    opacity: Curves.easeOut.transform(
                      ((intro.value - .62) / .26).clamp(0.0, 1.0),
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.satellite_alt_rounded,
                          size: 12,
                          color: Color(0xFF667085),
                        ),
                        SizedBox(width: 7),
                        Text(
                          'MARGDARSHI · UPSRTC',
                          style: TextStyle(
                            color: Color(0xFF667085),
                            fontSize: 9,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 1.2,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class SplashRoutePainter extends CustomPainter {
  final double progress;
  final double travel;

  const SplashRoutePainter({
    required this.progress,
    required this.travel,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final baseY = size.height * .69;
    final start = Offset(size.width * .07, baseY);
    final control = Offset(size.width * .50, size.height * .54);
    final end = Offset(size.width * .93, baseY);

    final routePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round
      ..color = const Color(0xFF344054)
          .withOpacity(.58 * progress);

    final path = ui.Path()
      ..moveTo(start.dx, start.dy)
      ..quadraticBezierTo(
        control.dx,
        control.dy,
        end.dx,
        end.dy,
      );

    canvas.drawPath(path, routePaint);

    final dotPaint = Paint()
      ..color = const Color(0xFFB8F26B).withOpacity(.7 * progress);

    for (final t in const <double>[.08, .22, .36, .50, .64, .78, .92]) {
      final point = _point(start, control, end, t);
      canvas.drawCircle(point, 2.8, dotPaint);
    }

    final busT = .12 + (.76 * travel);
    final busPoint = _point(start, control, end, busT);

    final glow = Paint()
      ..color = const Color(0xFFB8F26B).withOpacity(.12 * progress)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 15);

    canvas.drawCircle(busPoint, 22, glow);

    final busPaint = Paint()..color = const Color(0xFFB8F26B);
    final bus = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: busPoint,
        width: 39,
        height: 23,
      ),
      const Radius.circular(7),
    );

    canvas.drawRRect(bus, busPaint);

    final windowPaint = Paint()..color = const Color(0xFF111827);

    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(
          center: Offset(busPoint.dx, busPoint.dy - 3),
          width: 27,
          height: 9,
        ),
        const Radius.circular(2),
      ),
      windowPaint,
    );

    canvas.drawCircle(
      Offset(busPoint.dx - 11, busPoint.dy + 12),
      3.2,
      windowPaint,
    );
    canvas.drawCircle(
      Offset(busPoint.dx + 11, busPoint.dy + 12),
      3.2,
      windowPaint,
    );

    final sweepProgress = (.08 + (progress * .92)) % 1;
    final sweepPoint = _point(start, control, end, sweepProgress);

    final sweep = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..color = const Color(0xFFB8F26B).withOpacity(.22 * progress);

    canvas.drawCircle(sweepPoint, 12, sweep);
  }

  Offset _point(
    Offset start,
    Offset control,
    Offset end,
    double t,
  ) {
    final u = 1 - t;

    return Offset(
      u * u * start.dx +
          2 * u * t * control.dx +
          t * t * end.dx,
      u * u * start.dy +
          2 * u * t * control.dy +
          t * t * end.dy,
    );
  }

  @override
  bool shouldRepaint(SplashRoutePainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.travel != travel;
  }
}

class Home extends StatefulWidget { final bool dark; final VoidCallback toggle; const Home({super.key,required this.dark,required this.toggle}); @override State<Home> createState()=>_HomeState(); }

class _HomeState extends State<Home> {
 static const api='https://noida-bus-tracker.onrender.com';
 final map=MapController(); final search=TextEditingController(); Timer? refreshTimer,searchTimer;
 LatLng location=const LatLng(28.4598,77.5184); List<dynamic> buses=[]; List<dynamic> suggestions=[]; Set<String> favs={}; Map<String,List<LatLng>> history={}; Map<String,List<DateTime>> historyTimes={}; List<LatLng> trail=[]; Map<String,DateTime> alertHistory={};
 double radius=5; bool loading=false,locating=false,movePin=false,stops=false,following=false,permissionBlocked=false,dontShowNotice=false,nearbyAlerts=false; String? error,selected,followed; String locationLabel='Use your current location'; DateTime? refreshed;
 final stopData=const [['Botanical Garden',28.5640,77.3340],['Sector 37',28.5700,77.3450],['Noida City Center',28.5740,77.3560],['Sector 52',28.5890,77.3730],['Pari Chowk',28.4595,77.5082],['Chaar Murti',28.5650,77.4370],['Ek Murti',28.6040,77.4370],['Surajpur',28.5140,77.4830],['Kasna Village',28.4050,77.5060]];
 final searchPlaces=const [['Botanical Garden',28.5640,77.3340],['Sector 37',28.5700,77.3450],['Noida City Center',28.5740,77.3560],['Sector 52',28.5890,77.3730],['Sector 62',28.6280,77.3770],['Pari Chowk',28.4595,77.5082],['Chaar Murti',28.5650,77.4370],['Ek Murti',28.6040,77.4370],['Gaur Chowk',28.6150,77.4350],['Gaur City',28.6155,77.4240],['Surajpur',28.5140,77.4830],['Kasna Village',28.4050,77.5060],['Sector 90',28.5340,77.4380],['Noida International Airport',28.5562,77.5849]];

 @override void initState(){super.initState();_initApp();}
 @override void dispose(){refreshTimer?.cancel();searchTimer?.cancel();search.dispose();super.dispose();}
 Future<void> _initApp() async {
  final prefs = await SharedPreferences.getInstance();
  if (!mounted) return;

  setState(() {
    favs = (prefs.getStringList('favs') ?? []).toSet();
    dontShowNotice = prefs.getBool('dont_show_notice') ?? false;
    nearbyAlerts = prefs.getBool('nearby_alerts') ?? false;
  });

  if (!dontShowNotice) {
    await Future.delayed(const Duration(milliseconds: 700));
    if (mounted && !dontShowNotice) {
      _notice();
    }
  }
}

 Future<void> _notice() async {
  if (!mounted) return;

  var dontAgain = dontShowNotice;

  await showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) {
      return StatefulBuilder(
        builder: (context, setDialogState) {
          return AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(24),
            ),
            title: const Text('One important note'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Bus locations come from live GPS data. The “moving towards” information is an estimate from recent movement and can be wrong near junctions, turns or route changes.',
                  style: TextStyle(height: 1.45),
                ),
                const SizedBox(height: 14),
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Not a government website.\n'
                    'This is an independent project made by a curious BTech student.\n\n'
                    'Data source: MARGDARSHI · UPSRTC',
                    style: TextStyle(
                      height: 1.45,
                      fontSize: 12,
                      color: Color(0xFF6B7280),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                CheckboxListTile(
                  value: dontAgain,
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: const Text(
                    'Don’t show this again',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  onChanged: (value) {
                    setDialogState(() {
                      dontAgain = value ?? false;
                    });
                  },
                ),
              ],
            ),
            actions: [
              FilledButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Got it'),
              ),
            ],
          );
        },
      );
    },
  );

  final prefs = await SharedPreferences.getInstance();
  await prefs.setBool('dont_show_notice', dontAgain);

  if (mounted) {
    setState(() {
      dontShowNotice = dontAgain;
    });
  }
}

 Future<void> _location() async {
  if (locating) return;
  setState(() { locating = true; error = null; permissionBlocked = false; });
  try {
    if (!await Geolocator.isLocationServiceEnabled()) {
      if (mounted) {
        setState(() { locationLabel = 'Location services are off'; error = 'Turn on Location/GPS and tap again.'; });
        await Geolocator.openLocationSettings();
      }
      return;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied) {
      if (mounted) {
        setState(() { locationLabel = 'Location permission denied'; error = 'Allow Location permission to find buses near you.'; });
        _info('Location permission is required for current location.');
      }
      return;
    }
    if (permission == LocationPermission.deniedForever) {
      if (mounted) {
        setState(() { permissionBlocked = true; locationLabel = 'Location permission is blocked'; error = 'Allow Location permission in app settings.'; });
        _info('Location permission is blocked. Open app settings and allow Location.');
      }
      return;
    }
    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 15),
      ),
    );
    await _set(LatLng(position.latitude, position.longitude), 'Current location', true);
  } on TimeoutException {
    if (mounted) {
      setState(() { locationLabel = 'GPS fix timed out'; error = 'Try again outdoors or check GPS.'; });
      _info('GPS took too long to respond. Please try again.');
    }
  } catch (_) {
    if (mounted) {
      setState(() { locationLabel = 'Location unavailable'; error = 'Could not get your current location. Try again.'; });
      _info('Could not get your current location. Check GPS and Location permission.');
    }
  } finally {
    if (mounted) setState(() => locating = false);
  }
}

 Future<void> _set(LatLng p,String label,bool load) async {setState(() { location=p; locationLabel=label; selected=null; error=null; });map.move(p,14.5);if(load){await _load();_auto();}}
 void _auto(){refreshTimer?.cancel();refreshTimer=Timer.periodic(const Duration(seconds:45),(_){if(!loading)_load(auto:true);});}
 Future<void> _load({bool auto=false}) async {
  if (loading) return;
  setState(() => loading = true);

  final u = Uri.parse(
    api +
        '/api/buses/nearby?lat=' +
        location.latitude.toString() +
        '&lon=' +
        location.longitude.toString() +
        '&radius=' +
        radius.toString(),
  );

  try {
    final r = await http.get(u).timeout(const Duration(seconds: 20));
    if (r.statusCode != 200) throw Exception();

    final d = jsonDecode(r.body);
    final next = List<dynamic>.from(d['buses'] ?? []);

    next.sort((a, b) {
      final da = double.tryParse(a['distance_km']?.toString() ?? '');
      final db = double.tryParse(b['distance_km']?.toString() ?? '');
      return (da ?? double.infinity).compareTo(db ?? double.infinity);
    });

    for (final bus in next) {
      final id = bus['bus_id']?.toString();
      final lat = double.tryParse(bus['latitude']?.toString() ?? '');
      final lon = double.tryParse(bus['longitude']?.toString() ?? '');
      if (id == null || lat == null || lon == null) continue;

      history.putIfAbsent(id, () => []).add(LatLng(lat, lon));
      historyTimes.putIfAbsent(id, () => []).add(DateTime.now());
      if (history[id]!.length > 30) history[id]!.removeAt(0);
      if (historyTimes[id]!.length > 30) historyTimes[id]!.removeAt(0);
    }

    if (!mounted) return;

    setState(() {
      buses = next;
      refreshed = DateTime.now();
      error = null;
    });

    _checkNearbyAlert(next);

    if (following && followed != null) {
      final bus = _find(followed!);
      if (bus != null) _center(bus, false);
    }
  } catch (_) {
    if (mounted) {
      setState(() {
        error = 'Unable to refresh bus data. Showing previous results.';
      });
    }
  } finally {
    if (mounted) setState(() => loading = false);
  }
}

 void _checkNearbyAlert(List<dynamic> next) {
  if (!nearbyAlerts || next.isEmpty || !mounted) return;

  final now = DateTime.now();
  dynamic nearest;
  double? nearestDistance;

  for (final bus in next) {
    final distance = double.tryParse(bus['distance_km']?.toString() ?? '');
    if (distance == null || distance > 1) continue;

    if (nearestDistance == null || distance < nearestDistance!) {
      nearest = bus;
      nearestDistance = distance;
    }
  }

  if (nearest == null || nearestDistance == null) return;

  final id = nearest['bus_id'].toString();
  final lastAlert = alertHistory[id];

  if (lastAlert != null &&
      now.difference(lastAlert) < const Duration(minutes: 10)) {
    return;
  }

  alertHistory[id] = now;
  HapticFeedback.heavyImpact();

  final distanceText = nearestDistance < .1
      ? (nearestDistance * 1000).round().toString() + ' m'
      : nearestDistance.toStringAsFixed(2) + ' km';

  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 5),
        content: Row(
          children: [
            const Icon(
              Icons.notifications_active_rounded,
              color: Colors.white,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Nearby bus: ' +
                    nearest['bus_id'].toString() +
                    ' · ' +
                    distanceText +
                    ' away',
              ),
            ),
          ],
        ),
      ),
    );
}

 double _movedLastMinutes(String id,{int minutes=5}){
  final points=history[id]??[];
  final times=historyTimes[id]??[];
  if(points.length<2||times.length!=points.length)return 0;
  final cutoff=DateTime.now().subtract(Duration(minutes:minutes));
  var start=0;
  while(start<times.length-1&&times[start].isBefore(cutoff))start++;
  if(start>=points.length-1)return 0;
  final distance=const Distance();
  var total=0.0;
  for(var i=start+1;i<points.length;i++){
    total+=distance.as(LengthUnit.Kilometer,points[i-1],points[i]);
  }
  return total;
 }

 String? _routeForBus(String id){
  const routes={
    'UP80KT3702':'R1',
    'UP80KT4582':'R1',
    'UP70PT6077':'R1',
    'UP70PT6268':'R1',
    'UP80LT4113':'R1',
    'UP80LT4117':'R1',
    'UP80LT4126':'R1',
    'UP80KT3630':'R1',
    'UP80KT3703':'R1',
    'UP70PT6330':'R1',
    'UP80LT4114':'R1',
    'UP80LT4120':'R1',
  };
  return routes[id.toUpperCase()];
 }

 dynamic _find(String id){for(final b in buses){if(b['bus_id'].toString()==id)return b;}return null;}
 void _center(dynamic b,bool select){final a=double.tryParse(b['latitude'].toString()),o=double.tryParse(b['longitude'].toString());if(a==null||o==null)return;if(select)setState(()=>selected=b['bus_id'].toString());map.move(LatLng(a,o),16);}
 void _search(String v) {
  searchTimer?.cancel();

  final query = v.trim().toLowerCase();

  if (query.length < 2) {
    setState(() => suggestions = []);
    return;
  }

  final local = searchPlaces
      .where((place) => place[0].toString().toLowerCase().contains(query))
      .map((place) => {
            'name': place[0].toString(),
            'latitude': place[1],
            'longitude': place[2],
          })
      .toList();

  setState(() => suggestions = local);

  searchTimer = Timer(const Duration(milliseconds: 400), () async {
    try {
      final uri = Uri.parse(
        api +
            '/api/search-location?q=' +
            Uri.encodeQueryComponent(v.trim()),
      );

      final response = await http.get(uri).timeout(
        const Duration(seconds: 7),
      );

      if (response.statusCode != 200) return;

      final data = jsonDecode(response.body);
      final remote = List<dynamic>.from(data['results'] ?? []);

      if (!mounted ||
          search.text.trim().toLowerCase() != query) {
        return;
      }

      final names = local
          .map((item) => item['name'].toString().toLowerCase())
          .toSet();

      final merged = <dynamic>[...local];

      for (final item in remote) {
        final name = item['name']?.toString().trim() ?? '';
        if (name.isEmpty || names.contains(name.toLowerCase())) continue;
        merged.add(item);
      }

      setState(() => suggestions = merged.take(6).toList());
    } catch (_) {
      if (mounted) setState(() => suggestions = local);
    }
  });
}

 Future<void> _pick(dynamic x)async{final a=double.tryParse(x['latitude'].toString()),o=double.tryParse(x['longitude'].toString());if(a==null||o==null)return;search.text=x['name'].toString();FocusScope.of(context).unfocus();setState(()=>suggestions=[]);await _set(LatLng(a,o),x['name'].toString(),true);}
 void _tap(TapPosition _,LatLng p){if(!movePin)return;_set(p,'Selected map location',true);setState(()=>movePin=false);}
 Future<void> _fav(String id)async{final n=Set<String>.from(favs);n.contains(id)?n.remove(id):n.add(id);final p=await SharedPreferences.getInstance();await p.setStringList('favs',n.toList());if(mounted)setState(()=>favs=n);}
 void _follow(dynamic b){final id=b['bus_id'].toString();setState(() { followed=followed==id?null:id; following=followed!=null; });_center(b,true);}
 void _trail(dynamic b){final p=history[b['bus_id'].toString()]??[];if(p.length<2){_info('Trail needs a few refreshes first.');return;}setState(()=>trail=List<LatLng>.from(p));map.fitCamera(CameraFit.coordinates(coordinates:trail,padding:const EdgeInsets.all(45)));}
 void _play(dynamic b){final p=history[b['bus_id'].toString()]??[];if(p.length<2){_info('Playback needs a few recorded positions first.');return;}var i=0;Timer.periodic(const Duration(milliseconds:450),(t){if(!mounted||i>=p.length){t.cancel();return;}map.move(p[i++],16);});}
 void _eta(dynamic b){final s=double.tryParse(b['speed'].toString())??0,d=double.tryParse(b['distance_km'].toString())??0;if(s<3){_info('Approx ETA unavailable while this bus is stationary or very slow.');return;}_info('Approx ETA: '+(d/s*60).ceil().toString()+' min\nDistance: '+d.toStringAsFixed(2)+' km\nBased on current/recent GPS speed.');}
 void _share(dynamic b){Clipboard.setData(ClipboardData(text:'Noida Bus Tracker · Bus '+b['bus_id'].toString()));_info('Bus ID copied to clipboard.');}
 void _report(dynamic b){showModalBottomSheet(context:context,showDragHandle:true,builder:(c)=>SafeArea(child:Column(mainAxisSize:MainAxisSize.min,children:[Padding(padding:const EdgeInsets.all(16),child:Text('Report '+b['bus_id'].toString(),style:const TextStyle(fontSize:20,fontWeight:FontWeight.w800))),...['Not moving','Wrong location','Already passed','Crowded'].map((x)=>ListTile(title:Text(x),leading:const Icon(Icons.flag_outlined),onTap:(){Navigator.pop(c);_info('Thanks. Your report has been noted locally.');}))])));}
 void _info(String s){if(!mounted)return;showDialog(context:context,builder:(c)=>AlertDialog(title:const Text('Noida Bus Tracker'),content:Text(s),actions:[TextButton(onPressed:()=>Navigator.pop(c),child:const Text('OK'))]));}
 void _openFavourites() {
  final favouriteBuses = buses.where(
    (b) => favs.contains(b['bus_id'].toString()),
  ).toList();

  showModalBottomSheet(
    context: context,
    showDragHandle: true,
    builder: (c) => SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Favourite buses',
            style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          if (favouriteBuses.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Text('No favourite buses nearby.'),
            ),
          ...favouriteBuses.map(
            (b) => ListTile(
              leading: const Icon(Icons.directions_bus_outlined),
              title: Text(b['bus_id'].toString()),
              subtitle: Text((b['distance_km'] ?? '?').toString() + ' km away'),
              onTap: () {
                Navigator.pop(c);
                _center(b, true);
              },
            ),
          ),
        ],
      ),
    ),
  );
}

 void _settings() {
  var currentDark = widget.dark;
  var alertsEnabled = nearbyAlerts;

  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (sheetContext) {
      return StatefulBuilder(
        builder: (context, setSheetState) {
          return SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Padding(
                  padding: EdgeInsets.fromLTRB(20, 12, 20, 8),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'App settings',
                      style: TextStyle(
                        fontSize: 21,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
                ListTile(
                  leading: Icon(
                    currentDark
                        ? Icons.dark_mode
                        : Icons.light_mode_outlined,
                  ),
                  title: const Text('Dark mode'),
                  subtitle: Text(currentDark ? 'On' : 'Off'),
                  trailing: Switch(
                    value: currentDark,
                    onChanged: (value) {
                      setSheetState(() => currentDark = value);
                      widget.toggle();
                    },
                  ),
                ),
                SwitchListTile(
                  value: alertsEnabled,
                  secondary: const Icon(Icons.notifications_active_outlined),
                  title: const Text('Nearby bus alerts'),
                  subtitle: Text(
                    alertsEnabled
                        ? 'Alert when a bus comes within 1 km'
                        : 'Turn on to get nearby bus alerts',
                  ),
                  onChanged: (value) async {
                    setSheetState(() => alertsEnabled = value);
                    final prefs = await SharedPreferences.getInstance();
                    await prefs.setBool('nearby_alerts', value);
                    if (mounted) {
                      setState(() => nearbyAlerts = value);
                      if (value && buses.isNotEmpty) _checkNearbyAlert(buses);
                    }
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: const Text('About'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _info(
                      'Independent project by a curious BTech student.\n'
                      'Live GPS data: MARGDARSHI · UPSRTC.',
                    );
                  },
                ),
                const SizedBox(height: 10),
              ],
            ),
          );
        },
      );
    },
  );
}

 @override
 Widget build(BuildContext context) {
  return Scaffold(
    appBar: AppBar(
      titleSpacing: 16,
      title: const Text(
        'Noida Bus Tracker',
        maxLines: 1,
        softWrap: false,
        overflow: TextOverflow.visible,
        style: TextStyle(
          fontWeight: FontWeight.w800,
          fontSize: 18,
        ),
      ),
      actions: [
        PopupMenuButton<String>(
          tooltip: 'Menu',
          onSelected: (value) {
            if (value == 'favourites') _openFavourites();
            if (value == 'settings') _settings();
          },
          itemBuilder: (context) => const [
            PopupMenuItem(
              value: 'favourites',
              child: Text('Favourite buses'),
            ),
            PopupMenuItem(
              value: 'settings',
              child: Text('Settings'),
            ),
          ],
        ),
      ],
    ),
    body: RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
        children: [
          _locationCard(),
          const SizedBox(height: 12),
          _searchCard(),
          const SizedBox(height: 12),
          _mapCard(),
          const SizedBox(height: 14),
          _header(),
          if (error != null) _error(),
          if (loading && buses.isEmpty)
            const Padding(
              padding: EdgeInsets.all(30),
              child: Center(child: CircularProgressIndicator()),
            ),
          if (!loading && buses.isEmpty && error == null) _empty(),
          ...buses.map(_card),
          const SizedBox(height: 18),
          const Text(
            'Independent project. Not a government website.\n'
            'Live GPS data sourced from MARGDARSHI · UPSRTC.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFF6B7280),
              fontSize: 11,
              height: 1.5,
            ),
          ),
        ],
      ),
    ),
  );
}

 Widget _locationCard() {
  return Card(
    elevation: 0,
    margin: EdgeInsets.zero,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
    child: Padding(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF8EF),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.my_location_rounded, color: Color(0xFF15803D)),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Find buses near you',
                  style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(15),
            ),
            child: Row(
              children: [
                const Icon(Icons.place_outlined, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    locationLabel,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: FilledButton.icon(
              onPressed: locating ? null : _location,
              icon: locating
                  ? const SizedBox(
                      width: 19,
                      height: 19,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.my_location_rounded),
              label: Text(locating ? 'Finding your location…' : 'Use current location'),
            ),
          ),
          if (permissionBlocked)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: Geolocator.openAppSettings,
                  icon: const Icon(Icons.settings_outlined),
                  label: const Text('Open app settings'),
                ),
              ),
            ),
          const SizedBox(height: 10),
          Row(
            children: [
              const Icon(Icons.radar_rounded, size: 18),
              const SizedBox(width: 7),
              const Text('Search radius', style: TextStyle(fontWeight: FontWeight.w600)),
              const Spacer(),
              DropdownButtonHideUnderline(
                child: DropdownButton<double>(
                  value: radius,
                  items: const [
                    DropdownMenuItem(value: 1, child: Text('1 km')),
                    DropdownMenuItem(value: 3, child: Text('3 km')),
                    DropdownMenuItem(value: 5, child: Text('5 km')),
                    DropdownMenuItem(value: 10, child: Text('10 km')),
                    DropdownMenuItem(value: 15, child: Text('15 km')),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => radius = value);
                    _load();
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

 Widget _searchCard(){return Card(elevation:0,shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(20)),child:Column(children:[Padding(padding:const EdgeInsets.fromLTRB(15,5,8,5),child:Row(children:[const Icon(Icons.search_rounded),const SizedBox(width:8),Expanded(child:TextField(controller:search,onChanged:_search,decoration:const InputDecoration(hintText:'Search Sector 62, Pari Chowk, Botanical Garden…',border:InputBorder.none))),if(search.text.isNotEmpty)IconButton(onPressed:(){search.clear();setState(()=>suggestions=[]);},icon:const Icon(Icons.close))])),...suggestions.map((x)=>ListTile(leading:const Icon(Icons.place_outlined),title:Text(x['name'].toString()),onTap:()=>_pick(x))) ]));}
 Widget _mapCard() {
  final markers = <Marker>[];

  for (final bus in buses) {
    final lat = double.tryParse(bus['latitude'].toString());
    final lon = double.tryParse(bus['longitude'].toString());

    if (lat == null || lon == null) continue;

    final id = bus['bus_id'].toString();
    final isSelected = id == selected;

    markers.add(
      Marker(
        point: LatLng(lat, lon),
        width: isSelected ? 54 : 48,
        height: isSelected ? 54 : 48,
        child: GestureDetector(
          onTap: () => _center(bus, true),
          child: Container(
            decoration: BoxDecoration(
              color: isSelected
                  ? const Color(0xFFB8F26B)
                  : const Color(0xFF111827),
              shape: BoxShape.circle,
              border: Border.all(
                color: Colors.white,
                width: 3,
              ),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x33000000),
                  blurRadius: 8,
                ),
              ],
            ),
            child: Icon(
              Icons.directions_bus_rounded,
              color: isSelected ? Colors.black : Colors.white,
              size: 22,
            ),
          ),
        ),
      ),
    );
  }

  markers.add(
    Marker(
      point: location,
      width: 40,
      height: 40,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFF2563EB),
          shape: BoxShape.circle,
          border: Border.all(
            color: Colors.white,
            width: 4,
          ),
        ),
        child: const Icon(
          Icons.my_location_rounded,
          color: Colors.white,
          size: 18,
        ),
      ),
    ),
  );

  if (stops) {
    for (final stop in stopData) {
      markers.add(
        Marker(
          point: LatLng(
            stop[1] as double,
            stop[2] as double,
          ),
          width: 32,
          height: 32,
          child: Tooltip(
            message: stop[0] as String,
            child: const Icon(
              Icons.location_on,
              color: Color(0xFFB45309),
              size: 27,
            ),
          ),
        ),
      );
    }
  }

  return Card(
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(24),
    ),
    clipBehavior: Clip.antiAlias,
    child: Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 6, 7),
          child: Row(
            children: [
              const Expanded(
                child: Text(
                  'LIVE MAP',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              IconButton(
                onPressed: () => setState(() => stops = !stops),
                icon: Icon(
                  stops
                      ? Icons.visibility
                      : Icons.location_on_outlined,
                ),
              ),
              IconButton(
                onPressed: _location,
                icon: const Icon(Icons.my_location),
              ),
              IconButton(
                onPressed: () => setState(() => movePin = !movePin),
                icon: Icon(
                  movePin
                      ? Icons.pin_drop
                      : Icons.edit_location_alt,
                ),
              ),
              if (trail.isNotEmpty)
                IconButton(
                  onPressed: () => setState(() => trail = []),
                  icon: const Icon(Icons.clear),
                ),
            ],
          ),
        ),
        if (movePin)
          const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text(
              'Tap the map to choose a new location',
              style: TextStyle(
                fontSize: 12,
                color: Color(0xFF6B7280),
              ),
            ),
          ),
        SizedBox(
          height: 340,
          child: FlutterMap(
            mapController: map,
            options: MapOptions(
              initialCenter: location,
              initialZoom: 12.5,
              onTap: _tap,
            ),
            children: [
              TileLayer(
                urlTemplate:
                    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName:
                    'com.example.noida_bus_tracker',
              ),
              if (trail.length > 1)
                PolylineLayer(
                  polylines: [
                    Polyline(
                      points: trail,
                      strokeWidth: 5,
                    ),
                  ],
                ),
              MarkerLayer(
                markers: markers,
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

 Widget _header(){final t=refreshed==null?'Waiting for a location':'Updated '+refreshed!.hour.toString().padLeft(2,'0')+':'+refreshed!.minute.toString().padLeft(2,'0')+' · Auto refresh 45s';return Row(children:[Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Text('Nearby electric buses',style:TextStyle(fontSize:20,fontWeight:FontWeight.w800)),Text(t,style:const TextStyle(fontSize:12,color:Color(0xFF6B7280)))])),IconButton(onPressed:loading?null:_load,icon:const Icon(Icons.refresh))]);}
 Widget _card(dynamic b){
  final id=b['bus_id'].toString();
  final speed=double.tryParse(b['speed'].toString());
  final dist=double.tryParse(b['distance_km'].toString());
  final dir=b['likely_towards'];
  final route=_routeForBus(id);
  final moved=_movedLastMinutes(id);
  final isSelected=selected==id;

  return Card(
    elevation:isSelected?4:0,
    margin:const EdgeInsets.only(top:10),
    shape:RoundedRectangleBorder(
      borderRadius:BorderRadius.circular(20),
      side:BorderSide(
        color:isSelected?const Color(0xFFB8F26B):Theme.of(context).dividerColor,
        width:isSelected?1.5:1,
      ),
    ),
    child:InkWell(
      borderRadius:BorderRadius.circular(20),
      onTap:()=>_center(b,true),
      child:Padding(
        padding:const EdgeInsets.all(15),
        child:Column(
          crossAxisAlignment:CrossAxisAlignment.start,
          children:[
            Row(
              children:[
                Container(
                  width:50,
                  height:50,
                  decoration:BoxDecoration(
                    color:Theme.of(context).colorScheme.surfaceContainerHighest,
                    borderRadius:BorderRadius.circular(15),
                  ),
                  child:const Icon(Icons.directions_bus,size:26),
                ),
                const SizedBox(width:12),
                Expanded(
                  child:Column(
                    crossAxisAlignment:CrossAxisAlignment.start,
                    children:[
                      Row(
                        children:[
                          Flexible(
                            child:Text(
                              id,
                              maxLines:1,
                              overflow:TextOverflow.ellipsis,
                              style:const TextStyle(fontSize:16,fontWeight:FontWeight.w800),
                            ),
                          ),
                          if(route!=null) ...[
                            const SizedBox(width:8),
                            Container(
                              padding:const EdgeInsets.symmetric(horizontal:8,vertical:4),
                              decoration:BoxDecoration(
                                color:const Color(0xFF111827),
                                borderRadius:BorderRadius.circular(7),
                              ),
                              child:Text(
                                route,
                                style:const TextStyle(
                                  color:Colors.white,
                                  fontSize:10,
                                  fontWeight:FontWeight.w800,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height:4),
                      Wrap(
                        spacing:10,
                        runSpacing:3,
                        children:[
                          if(dist!=null)Text(
                            dist.toStringAsFixed(2)+' km',
                            style:const TextStyle(fontSize:12,color:Color(0xFF6B7280)),
                          ),
                          if(speed!=null)Text(
                            speed.toStringAsFixed(0)+' km/h',
                            style:const TextStyle(fontSize:12,color:Color(0xFF6B7280)),
                          ),
                          Text(
                            (b['vehicle_status']??'Status unknown').toString(),
                            style:const TextStyle(fontSize:12,color:Color(0xFF6B7280)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed:()=>_fav(id),
                  icon:Icon(
                    favs.contains(id)?Icons.star:Icons.star_border,
                    color:favs.contains(id)?const Color(0xFFB45309):null,
                  ),
                ),
              ],
            ),
            if(dir is String&&dir.isNotEmpty)
              Padding(
                padding:const EdgeInsets.only(top:10),
                child:Row(
                  children:[
                    const Icon(Icons.trending_flat,size:20),
                    const SizedBox(width:7),
                    Expanded(
                      child:Text(
                        'Moving towards '+dir,
                        style:const TextStyle(fontWeight:FontWeight.w700),
                      ),
                    ),
                  ],
                ),
              ),
            const SizedBox(height:10),
            Container(
              width:double.infinity,
              padding:const EdgeInsets.symmetric(horizontal:11,vertical:10),
              decoration:BoxDecoration(
                color:Theme.of(context).colorScheme.surfaceContainerHighest.withOpacity(.55),
                borderRadius:BorderRadius.circular(13),
              ),
              child:Row(
                children:[
                  const Icon(Icons.route_rounded,size:18,color:Color(0xFF15803D)),
                  const SizedBox(width:8),
                  Expanded(
                    child:Text(
                      'Moved '+moved.toStringAsFixed(2)+' km in the last 5 min',
                      style:const TextStyle(fontSize:12,fontWeight:FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height:9),
            Wrap(
              spacing:6,
              runSpacing:6,
              children:[
                _chip('ETA',Icons.timer_outlined,()=>_eta(b)),
                _chip(followed==id&&following?'Following':'Follow',Icons.center_focus_strong,()=>_follow(b)),
                _chip('Trail',Icons.route_outlined,()=>_trail(b)),
                _chip('Playback',Icons.play_arrow,()=>_play(b)),
                _chip('Share',Icons.share_outlined,()=>_share(b)),
                _chip('Report',Icons.flag_outlined,()=>_report(b)),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

 Widget _error() {
  return Card(
    color: const Color(0xFFFFF7ED),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          const Icon(
            Icons.warning_amber,
            color: Color(0xFFB45309),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              error ?? 'Unable to refresh bus data.',
              style: const TextStyle(
                color: Color(0xFF92400E),
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

 Widget _empty() {
  return const Card(
    child: Padding(
      padding: EdgeInsets.all(28),
      child: Column(
        children: [
          Icon(
            Icons.directions_bus_outlined,
            size: 44,
            color: Color(0xFF9CA3AF),
          ),
          SizedBox(height: 10),
          Text(
            'No buses found nearby',
            style: TextStyle(
              fontWeight: FontWeight.w800,
            ),
          ),
          SizedBox(height: 5),
          Text(
            'Try increasing the radius or choosing another location.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFF6B7280),
              fontSize: 13,
            ),
          ),
        ],
      ),
    ),
  );
}

}