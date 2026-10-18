import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

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
      duration: const Duration(milliseconds: 850),
    )..forward();

    travel = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat(reverse: true);

    Future.delayed(const Duration(milliseconds: 1100), () {
      if (!mounted) return;

      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          pageBuilder: (_, __, ___) => widget.child,
          transitionDuration: const Duration(milliseconds: 320),
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

class _HomeState extends State<Home> with WidgetsBindingObserver {
 static const api='https://noida-bus-tracker.onrender.com';
 String? analyticsVisitorId;
 late String analyticsSessionId;
 String analyticsAppVersion='1.1.0';
 Map<String,Object> analyticsDeviceMetadata={};
 bool analyticsEnabled=false;
 DateTime? analyticsLastActivity;
 bool _wasBackgrounded=false;
 final map=MapController(); final search=TextEditingController(); Timer? refreshTimer,searchTimer,maintenanceTimer; bool maintenanceMode=false,maintenanceCheckRunning=false; String maintenanceMessage='We are making a few improvements. Please check back shortly.'; int? maintenanceExpiresAt;
 LatLng location=const LatLng(28.4598,77.5184); List<dynamic> buses=[]; List<dynamic> suggestions=[]; List<dynamic> routeData=[]; Set<String> favs={}; Map<String,List<LatLng>> history={}; Map<String,List<DateTime>> historyTimes={}; List<LatLng> trail=[]; Map<String,DateTime> alertHistory={};
 double radius=5; bool loading=false,locating=false,movePin=false,stops=false,showRoutes=false,following=false,permissionBlocked=false,dontShowNotice=false,nearbyAlerts=false; String? error,selected,followed; String locationLabel='Use your current location'; DateTime? refreshed;
 final stopData=const [['Botanical Garden',28.5640,77.3340],['Sector 37',28.5700,77.3450],['Noida City Center',28.5740,77.3560],['Sector 52',28.5890,77.3730],['Pari Chowk',28.4595,77.5082],['Chaar Murti',28.5650,77.4370],['Ek Murti',28.6040,77.4370],['Surajpur',28.5140,77.4830],['Kasna Village',28.4050,77.5060]];
 final searchPlaces=const [['Botanical Garden',28.5640,77.3340],['Sector 37',28.5700,77.3450],['Noida City Center',28.5740,77.3560],['Sector 52',28.5890,77.3730],['Sector 62',28.6280,77.3770],['Pari Chowk',28.4595,77.5082],['Chaar Murti',28.5650,77.4370],['Ek Murti',28.6040,77.4370],['Gaur Chowk',28.6150,77.4350],['Gaur City',28.6155,77.4240],['Surajpur',28.5140,77.4830],['Kasna Village',28.4050,77.5060],['Sector 90',28.5340,77.4380],['Noida International Airport',28.5562,77.5849]];

 @override void initState(){super.initState();WidgetsBinding.instance.addObserver(this);analyticsSessionId=DateTime.now().microsecondsSinceEpoch.toString()+'-'+hashCode.toString();_initAnalytics();_initApp();_loadRoutes();_checkForUpdate();_pollMaintenanceStatus();maintenanceTimer=Timer.periodic(const Duration(seconds:5),(_)=>_pollMaintenanceStatus());}
 @override void dispose(){WidgetsBinding.instance.removeObserver(this);refreshTimer?.cancel();searchTimer?.cancel();maintenanceTimer?.cancel();search.dispose();super.dispose();}

 @override
 void didChangeAppLifecycleState(AppLifecycleState state) {
  if (state == AppLifecycleState.paused || state == AppLifecycleState.inactive || state == AppLifecycleState.hidden) {
    _wasBackgrounded = true;
    return;
  }
  if (state == AppLifecycleState.resumed && _wasBackgrounded) {
    _wasBackgrounded = false;
    if (analyticsEnabled) unawaited(_recordAppOpen());
    if (maintenanceMode) unawaited(_pollMaintenanceStatus());
  }
}
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
      await _notice();
    }
  }

  await _requestAnalyticsConsent();
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

  Future<void> _requestAnalyticsConsent() async {
  final prefs = await SharedPreferences.getInstance();
  if (prefs.containsKey('analytics_consent_v2') || !mounted) return;

  final choice = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      title: const Text('Optional usage analytics'),
      content: const SingleChildScrollView(
        child: Text(
          'Help improve Noida Bus Tracker by sharing app usage events, sessions, app version, phone brand and model, Android version, and an approximate area inferred from your network IP. IP-based area is not GPS and can be inaccurate. Analytics does not need your device GPS location.\n\n'
          'This is optional. Bus tracking works if you decline, and you can change this choice any time in App settings. See Privacy notice for details.',
          style: TextStyle(height: 1.5),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, false),
          child: const Text('Continue without analytics'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(dialogContext, true),
          child: const Text('Allow analytics'),
        ),
      ],
    ),
  );

  if (!mounted) return;
  final enabled = choice == true;
  await prefs.setBool('analytics_consent_v2', enabled);
  await prefs.setBool('analytics_enabled', enabled);
  if (!mounted) return;
  setState(() => analyticsEnabled = enabled);
  if (enabled) await _recordAppOpen();
}

 Future<void> _initAnalytics() async {
  try {
   final prefs=await SharedPreferences.getInstance();
   analyticsEnabled=prefs.getBool('analytics_consent_v2')??false;
   analyticsVisitorId=prefs.getString('analytics_visitor_id');
   if(analyticsVisitorId==null||analyticsVisitorId!.isEmpty){
    analyticsVisitorId=DateTime.now().microsecondsSinceEpoch.toString()+'-'+hashCode.toString();
    await prefs.setString('analytics_visitor_id',analyticsVisitorId!);
   }
   final info=await PackageInfo.fromPlatform();
   analyticsAppVersion=info.version;
   if(Platform.isAndroid){
    try{
     final android=await DeviceInfoPlugin().androidInfo;
     analyticsDeviceMetadata={
      'device_brand':android.brand,
      'device_manufacturer':android.manufacturer,
      'device_model':android.model,
      'android_version':android.version.release,
      'android_sdk_int':android.version.sdkInt,
     };
    }catch(_){}
   }
   if(analyticsEnabled)await _recordAppOpen();
  } catch (_) {}
 }

 Future<void> _recordAppOpen() async {
  if(!analyticsEnabled)return;
  await _sendAnalytics('app_open');
  final prefs=await SharedPreferences.getInstance();
  final firstOpenTracked=prefs.getBool('analytics_first_open_tracked')??false;
  if(!firstOpenTracked){
   final recorded=await _sendAnalytics('first_open');
   if(recorded)await prefs.setBool('analytics_first_open_tracked',true);
  }
 }

 Future<Map<String,String>> _appHeaders([Map<String,String> base = const {}]) async {
  final headers = <String,String>{...base};
  try {
    analyticsAppVersion = (await PackageInfo.fromPlatform()).version;
  } catch (_) {}
  headers['X-App-Version'] = analyticsAppVersion;
  headers['X-App-Platform'] = 'android';
  return headers;
 }

 Future<bool> _sendAnalytics(String name,[Map<String,Object>? parameters]) async {
  if(!analyticsEnabled)return false;
  final visitor=analyticsVisitorId;
  if(visitor==null||visitor.isEmpty)return false;
  final now=DateTime.now();
  if(analyticsLastActivity==null||now.difference(analyticsLastActivity!)>const Duration(minutes:30)){
   analyticsSessionId=now.microsecondsSinceEpoch.toString()+'-'+hashCode.toString();
  }
  analyticsLastActivity=now;
  try {
   final response=await http.post(
    Uri.parse(api+'/api/analytics/event'),
    headers: await _appHeaders({'Content-Type':'application/json','Accept':'application/json'}),
    body:jsonEncode({
     'event_name':name,
     'path':'/mobile',
     'session_id':analyticsSessionId,
     'visitor_id':visitor,
     'source':'android',
     'device_type':'mobile',
     'os':Platform.operatingSystem,
     'language':Platform.localeName,
     'app_version':analyticsAppVersion,
     'metadata':{
      ...analyticsDeviceMetadata,
      'install_id':visitor,
      if(parameters!=null)...parameters,
     },
    }),
   ).timeout(const Duration(seconds:5));
   if(response.statusCode<200||response.statusCode>=300)return false;
   final body=jsonDecode(response.body);
   return body is Map<String,dynamic>&&body['success']==true;
  } catch (_) {
   return false;
  }
 }

 Future<void> _analytics(String name, [Map<String,Object>? parameters]) async {
  if(!analyticsEnabled)return;
  final normalizedEvent = switch(name){
   'current_location_used' => 'location_used',
   'location_searched' => 'place_search',
   _ => name,
  };
  await _sendAnalytics(normalizedEvent,parameters);
 }
 Future<void> _checkForUpdate() async {
  try {
    final info = await PackageInfo.fromPlatform();
    final manifestUri = Uri.parse('https://raw.githubusercontent.com/Aryan1684/noida-bus-tracker/main/mobile/app_version.json?ts=${DateTime.now().millisecondsSinceEpoch}');
    final response = await http.get(manifestUri, headers: const {'Cache-Control': 'no-cache'}).timeout(const Duration(seconds: 8));
    if (response.statusCode != 200) return;
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) return;

    final data = decoded;
    final latest = data['latest_version']?.toString() ?? info.version;
    final minimum = data['minimum_version']?.toString() ?? info.version;
    final mandatory = _isVersionNewer(minimum, info.version);
    final optionalUpdate = _isVersionNewer(latest, info.version);
    if (!mandatory && !optionalUpdate) return;
    if (!mounted) return;

    final message = data['message']?.toString() ?? 'A newer version of Noida Bus Tracker is available.';
    final rawUrl = data['download_url']?.toString() ?? '';
    final updateUri = Uri.tryParse(rawUrl);
    final validUpdateUri = updateUri != null &&
        updateUri.scheme == 'https' &&
        updateUri.host.isNotEmpty;

    await showDialog<void>(
      context: context,
      barrierDismissible: !mandatory,
      builder: (dialogContext) => PopScope(
        canPop: !mandatory,
        child: Dialog(
          backgroundColor: const Color(0xFF151D16),
          insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(22, 26, 22, 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 82,
                      height: 82,
                      decoration: BoxDecoration(
                        color: const Color(0xFFB8F26B),
                        borderRadius: BorderRadius.circular(26),
                      ),
                      child: const Icon(
                        Icons.system_update_alt_rounded,
                        size: 43,
                        color: Color(0xFF172016),
                      ),
                    ),
                  ),
                  const SizedBox(height: 22),
                  Text(
                    mandatory ? 'Update required' : 'A better ride starts here',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      height: 1.15,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    mandatory
                        ? 'This version is no longer supported. Update the app to continue tracking buses.'
                        : 'Noida Bus Tracker version $latest is ready to install.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Color(0xFFD3D9D0),
                      fontSize: 14,
                      height: 1.45,
                    ),
                  ),
                  const SizedBox(height: 18),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFF242E25),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0xFF384439)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.verified_rounded, color: Color(0xFFB8F26B), size: 21),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            message,
                            style: const TextStyle(
                              color: Color(0xFFE5EAE2),
                              fontSize: 12,
                              height: 1.45,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 15),
                  Wrap(
                    alignment: WrapAlignment.center,
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
                        decoration: BoxDecoration(
                          color: const Color(0xFF252E26),
                          borderRadius: BorderRadius.circular(30),
                        ),
                        child: Text(
                          'Installed: ${info.version}',
                          style: const TextStyle(color: Color(0xFFE5EAE2), fontSize: 11, fontWeight: FontWeight.w700),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
                        decoration: BoxDecoration(
                          color: const Color(0xFFB8F26B),
                          borderRadius: BorderRadius.circular(30),
                        ),
                        child: Text(
                          'Latest: $latest',
                          style: const TextStyle(color: Color(0xFF172016), fontSize: 11, fontWeight: FontWeight.w800),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    height: 54,
                    child: FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFFB8F26B),
                        foregroundColor: const Color(0xFF172016),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900),
                      ),
                      onPressed: () async {
                        if (!validUpdateUri) {
                          await Clipboard.setData(ClipboardData(text: rawUrl));
                          if (dialogContext.mounted) {
                            _info('The update link is not configured correctly. The available link has been copied.');
                          }
                          return;
                        }
                        try {
                          final opened = await launchUrl(
                            updateUri,
                            mode: LaunchMode.externalApplication,
                          );
                          if (!opened && dialogContext.mounted) {
                            await Clipboard.setData(ClipboardData(text: rawUrl));
                            _info('Could not open the APK link. It has been copied so you can open it in your browser.');
                          } else if (opened && !mandatory && dialogContext.mounted) {
                            Navigator.pop(dialogContext);
                          }
                        } catch (_) {
                          if (dialogContext.mounted) {
                            await Clipboard.setData(ClipboardData(text: rawUrl));
                            _info('Could not open the APK link. It has been copied so you can open it in your browser.');
                          }
                        }
                      },
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.download_rounded, size: 21),
                          SizedBox(width: 9),
                          Text('Update Now'),
                          SizedBox(width: 8),
                          Icon(Icons.north_east_rounded, size: 17),
                        ],
                      ),
                    ),
                  ),
                  if (!mandatory) ...[
                    const SizedBox(height: 7),
                    TextButton(
                      onPressed: () => Navigator.pop(dialogContext),
                      child: const Text('Maybe later', style: TextStyle(color: Color(0xFFD3D9D0))),
                    ),
                  ] else ...[
                    const SizedBox(height: 14),
                    const Text(
                      'Update required to continue using the app',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Color(0xFFB8F26B), fontSize: 11, fontWeight: FontWeight.w700),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  } catch (_) {}
 }

 bool _isVersionNewer(String a, String b) {
  List<int> parts(String v) => v.split('.').map((x) => int.tryParse(x.replaceAll(RegExp(r'[^0-9]'), '')) ?? 0).toList();
  final x = parts(a), y = parts(b);
  for (var i = 0; i < 3; i++) {
    final xv = i < x.length ? x[i] : 0;
    final yv = i < y.length ? y[i] : 0;
    if (xv != yv) return xv > yv;
  }
  return false;
 }

 Future<bool> _checkMaintenanceStatus() async {
  if (maintenanceCheckRunning) return maintenanceMode;
  maintenanceCheckRunning = true;

  try {
    final response = await http.get(
      Uri.parse('$api/api/maintenance?_=${DateTime.now().millisecondsSinceEpoch}'),
      headers: await _appHeaders({'Cache-Control': 'no-cache'}),
    ).timeout(const Duration(seconds: 5));

    if (response.statusCode != 200) return maintenanceMode;

    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) return maintenanceMode;

    if (decoded['enabled'] == true) {
      _enableMaintenance(decoded);
      return true;
    }

    _disableMaintenance();
    return false;
  } catch (_) {
    return maintenanceMode;
  } finally {
    maintenanceCheckRunning = false;
  }
}

 Future<void> _pollMaintenanceStatus() async {
  final wasEnabled = maintenanceMode;
  final enabled = await _checkMaintenanceStatus();

  if (wasEnabled && !enabled && mounted) {
    await _load(auto: true);
  }
}

 void _enableMaintenance(Map<String, dynamic> data) {
  final message = (data['message'] ?? 'We are making a few improvements. Please check back shortly.').toString();
  final rawExpiry = data['expires_at'];
  final expiry = rawExpiry is num ? rawExpiry.toInt() : int.tryParse(rawExpiry?.toString() ?? '');

  refreshTimer?.cancel();

  if (!mounted) return;
  if (maintenanceMode && maintenanceMessage == message && maintenanceExpiresAt == expiry) return;

  setState(() {
    maintenanceMode = true;
    maintenanceMessage = message;
    maintenanceExpiresAt = expiry;
    buses = [];
    selected = null;
    followed = null;
    following = false;
    loading = false;
    error = null;
  });
}

 void _disableMaintenance() {
  if (!mounted || !maintenanceMode) return;
  setState(() {
    maintenanceMode = false;
    maintenanceMessage = 'We are making a few improvements. Please check back shortly.';
    maintenanceExpiresAt = null;
  });
}

 Widget _maintenancePage() {
  final expiry = maintenanceExpiresAt == null
      ? null
      : DateTime.fromMillisecondsSinceEpoch(maintenanceExpiresAt!);
  final scheduledTime = expiry == null
      ? null
      : '${expiry.hour.toString().padLeft(2, '0')}:${expiry.minute.toString().padLeft(2, '0')} on ${expiry.day.toString().padLeft(2, '0')}/${expiry.month.toString().padLeft(2, '0')}/${expiry.year}';

  return Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Card(
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(28),
                side: BorderSide(color: Theme.of(context).dividerColor),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 36),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 88,
                      height: 88,
                      decoration: BoxDecoration(
                        color: const Color(0xFFB8F26B).withOpacity(.2),
                        borderRadius: BorderRadius.circular(26),
                      ),
                      child: const Icon(
                        Icons.construction_rounded,
                        size: 44,
                        color: Color(0xFF668A2E),
                      ),
                    ),
                    const SizedBox(height: 24),
                    const Text(
                      'We’ll be back soon.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 28, fontWeight: FontWeight.w900),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      maintenanceMessage,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 15, height: 1.55),
                    ),
                    const SizedBox(height: 18),
                    if (scheduledTime != null)
                      Text(
                        'Scheduled return: $scheduledTime',
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    const SizedBox(height: 12),
                    const Text(
                      'Live bus tracking is paused during maintenance. The app will check service status automatically.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 13, height: 1.5, color: Color(0xFF6B7280)),
                    ),
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: () => _pollMaintenanceStatus(),
                        icon: const Icon(Icons.refresh_rounded),
                        label: const Text('Check status'),
                      ),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: _feedback,
                        icon: const Icon(Icons.feedback_outlined),
                        label: const Text('Feedback & suggestions'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

 Future<void> _loadRoutes() async {
  try {
    final response = await http.get(Uri.parse(api + '/api/routes'), headers: await _appHeaders()).timeout(const Duration(seconds: 10));
    if (response.statusCode != 200) return;
    final data = jsonDecode(response.body);
    final received = List<dynamic>.from(data['routes'] ?? []);
    if (mounted) setState(() => routeData = received);
  } catch (_) {}
 }

 void _openRoutes() {
  unawaited(_analytics('routes_opened'));
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (sheetContext) => SafeArea(
      child: SizedBox(
        height: MediaQuery.of(sheetContext).size.height * .75,
        child: routeData.isEmpty
            ? const Center(child: Text('Route data is unavailable right now.'))
            : ListView(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
                children: [
                  const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('Routes & stops', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
                  ),
                  const Padding(
                    padding: EdgeInsets.fromLTRB(12, 0, 12, 12),
                    child: Text('Choose a route or tap a stop to centre the map and find nearby buses.', style: TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                  ),
                  ...routeData.map((route) {
                    final points = List<dynamic>.from(route['points'] ?? []);
                    return ExpansionTile(
                      leading: const Icon(Icons.route_rounded),
                      title: Text((route['name'] ?? route['id'] ?? 'Route').toString(), style: const TextStyle(fontWeight: FontWeight.w800)),
                      subtitle: Text('${points.length} mapped stops'),
                      onExpansionChanged: (expanded) {
                        if (!expanded || points.isEmpty) return;
                        final coordinates = points.map((point) => LatLng(
                          double.tryParse(point['latitude'].toString()) ?? 0,
                          double.tryParse(point['longitude'].toString()) ?? 0,
                        )).toList();
                        setState(() => showRoutes = true);
                        if (coordinates.length >= 2) {
                          map.fitCamera(CameraFit.coordinates(coordinates: coordinates, padding: const EdgeInsets.all(35)));
                        }
                      },
                      children: points.map((point) => ListTile(
                        dense: true,
                        leading: const Icon(Icons.location_on_outlined, size: 18),
                        title: Text((point['name'] ?? 'Stop').toString()),
                        onTap: () async {
                          final latitude = double.tryParse(point['latitude'].toString());
                          final longitude = double.tryParse(point['longitude'].toString());
                          if (latitude == null || longitude == null) return;
                          Navigator.pop(sheetContext);
                          setState(() { showRoutes = true; stops = true; });
                          await _set(LatLng(latitude, longitude), point['name'].toString(), true);
                        },
                      )).toList(),
                    );
                  }),
                ],
              ),
      ),
    ),
  );
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
    await _analytics('current_location_used');
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
  if (loading || maintenanceMode) return;
  if (await _checkMaintenanceStatus()) return;
  if (!mounted || loading || maintenanceMode) return;
  await _analytics('refresh', {'refresh_mode': auto ? 'automatic' : 'manual'});
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
    final r = await http.get(u, headers: await _appHeaders()).timeout(const Duration(seconds: 20));
    if (r.statusCode == 503) {
      try {
        final body = jsonDecode(r.body);
        if (body is Map<String, dynamic> && body['maintenance'] == true) {
          _enableMaintenance(body);
          return;
        }
      } catch (_) {}
    }
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
    if (mounted && !maintenanceMode) {
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

 String? _routeForBus(dynamic bus){
  final backendRoute=bus['route_id']?.toString().trim();
  if(backendRoute!=null&&backendRoute.isNotEmpty&&backendRoute.toLowerCase()!='null'){
    return backendRoute=='R01'?'R1':backendRoute;
  }
  return null;
 }

 dynamic _find(String id){for(final b in buses){if(b['bus_id'].toString()==id)return b;}return null;}
 void _center(dynamic b,bool select){
  final a=double.tryParse(b['latitude'].toString());
  final o=double.tryParse(b['longitude'].toString());
  if(a==null||o==null)return;

  if(select){
    _analytics('bus_selected', {'bus_id': b['bus_id'].toString()});
    final id=b['bus_id'].toString();
    final index=buses.indexWhere((item)=>item['bus_id'].toString()==id);

    if(index>0){
      setState((){
        selected=id;
        final picked=buses.removeAt(index);
        buses.insert(0,picked);
      });
    }else{
      setState(()=>selected=id);
    }
  }

  map.move(LatLng(a,o),16);
}

 void _clearBusSelection(){
  if(selected==null)return;
  final copy=List<dynamic>.from(buses);
  copy.sort((a,b){
    final da=double.tryParse(a['distance_km']?.toString()??'');
    final db=double.tryParse(b['distance_km']?.toString()??'');
    return (da??double.infinity).compareTo(db??double.infinity);
  });
  setState((){
    selected=null;
    buses=copy;
  });
}
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

      final response = await http.get(uri, headers: await _appHeaders()).timeout(
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

 Future<void> _pick(dynamic x)async{await _analytics('place_search', {'place': x['name'].toString()});final a=double.tryParse(x['latitude'].toString()),o=double.tryParse(x['longitude'].toString());if(a==null||o==null)return;search.text=x['name'].toString();FocusScope.of(context).unfocus();setState(()=>suggestions=[]);await _set(LatLng(a,o),x['name'].toString(),true);}
 void _tap(TapPosition _,LatLng p){
  if(movePin){
    _set(p,'Selected map location',true);
    setState(()=>movePin=false);
    return;
  }
  _clearBusSelection();
}
 Future<void> _fav(String id)async{final existed=favs.contains(id);unawaited(_analytics(existed?'favorite_removed':'favorite_added', {'bus_id':id}));final n=Set<String>.from(favs);n.contains(id)?n.remove(id):n.add(id);final p=await SharedPreferences.getInstance();await p.setStringList('favs',n.toList());if(mounted)setState(()=>favs=n);}
 void _follow(dynamic b){final id=b['bus_id'].toString();unawaited(_analytics('bus_follow_toggled', {'bus_id':id, 'following':followed!=id}));setState(() { followed=followed==id?null:id; following=followed!=null; });_center(b,true);}
 void _trail(dynamic b){unawaited(_analytics('movement_trail_opened', {'bus_id':b['bus_id'].toString()}));final p=history[b['bus_id'].toString()]??[];if(p.length<2){_info('Trail needs a few refreshes first.');return;}setState(()=>trail=List<LatLng>.from(p));map.fitCamera(CameraFit.coordinates(coordinates:trail,padding:const EdgeInsets.all(45)));}
 void _play(dynamic b){unawaited(_analytics('playback_opened', {'bus_id':b['bus_id'].toString()}));final p=history[b['bus_id'].toString()]??[];if(p.length<2){_info('Playback needs a few recorded positions first.');return;}var i=0;Timer.periodic(const Duration(milliseconds:450),(t){if(!mounted||i>=p.length){t.cancel();return;}map.move(p[i++],16);});}
 void _eta(dynamic b){unawaited(_analytics('eta_requested', {'bus_id':b['bus_id'].toString()}));final minutes=int.tryParse(b['eta_minutes']?.toString()??'');final status=(b['eta_status']??'').toString();final next=(b['likely_next_stop']??b['likely_towards']??'next stop').toString();final last=(b['last_passed_stop']??b['last_stop']??'unavailable').toString();if(status=='not_ahead'){_info('This bus is not currently heading toward the selected location.');return;}if(minutes==null){_info('Last passed stop: '+last+'\\nNext stop: '+next+'\\nETA unavailable. '+(b['eta_label']??'Recent movement data is not sufficient for a reliable estimate.').toString());return;}_info('Last passed stop: '+last+'\\nNext stop: '+next+'\\nEstimated arrival: '+minutes.toString()+' min\\n'+(b['eta_label']??'Based on recent GPS movement.').toString());}
 void _share(dynamic b){unawaited(_analytics('bus_shared', {'bus_id': b['bus_id'].toString()}));Clipboard.setData(ClipboardData(text:'Noida Bus Tracker · Bus '+b['bus_id'].toString()));_info('Bus ID copied to clipboard.');}
 void _report(dynamic b){
  unawaited(_analytics('report_opened', {'bus_id':b['bus_id'].toString()}));
  showModalBottomSheet<void> (
    context: context,
    showDragHandle: true,
    builder: (c) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 6),
            child: Text('Report ${b['bus_id']}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Text('Your selected issue and bus ID will be sent to the project team.', style: TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
          ),
          ...['Not moving', 'Wrong location', 'Already passed', 'Crowded'].map((issue) => ListTile(
            title: Text(issue),
            leading: const Icon(Icons.flag_outlined),
            onTap: () {
              Navigator.pop(c);
              unawaited(_submitBusReport(b, issue));
            },
          )),
        ],
      ),
    ),
  );
 }

 Future<void> _submitBusReport(dynamic bus, String issue) async {
  try {
    final response = await http.post(
      Uri.parse(api + '/api/report'),
      headers: await _appHeaders({'Content-Type': 'application/json', 'Accept': 'application/json'}),
      body: jsonEncode({
        'bus_id': bus['bus_id'].toString(),
        'report_type': issue.toLowerCase().replaceAll(' ', '_'),
        'value': issue,
        'note': 'Submitted from Android app',
        'consent': 'yes',
        'time': DateTime.now().toIso8601String(),
      }),
    ).timeout(const Duration(seconds: 12));
    final data = jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300 || data is! Map<String, dynamic> || data['success'] != true) {
      throw Exception(data is Map<String, dynamic> ? data['detail']?.toString() : 'Report submission failed');
    }
    await _analytics('report_submitted', {'bus_id': bus['bus_id'].toString(), 'report_type': issue});
    if (mounted) _info('Report submitted. Thanks for helping improve bus data.');
  } catch (_) {
    if (mounted) _info('The report could not be sent right now. Please try again when the backend is available.');
  }
 }
 void _info(String s){if(!mounted)return;showDialog(context:context,builder:(c)=>AlertDialog(title:const Text('Noida Bus Tracker'),content:Text(s),actions:[TextButton(onPressed:()=>Navigator.pop(c),child:const Text('OK'))]));}
 void _openFavourites() {
  unawaited(_analytics('favorites_opened'));
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

 Future<void> _openWebsitePage(String page) async {
  final uri = Uri.parse('https://noidabus.netlify.app/' + page);
  try {
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && mounted) _info('Could not open the page. Website address: ' + uri.toString());
  } catch (_) {
    if (mounted) _info('Could not open the page. Website address: ' + uri.toString());
  }
 }

 Future<void> _shareApproximateLocation() async {
  final accepted = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: const Text('Help improve this area'),
      content: const Text(
        'Share your current location once? The app sends coordinates to the tracker backend, which rounds them to an approximate area. Admin analytics only shows aggregated areas with at least 3 unique visitor identifiers. This is optional and is not required to track buses.',
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Not now')),
        FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Share area')),
      ],
    ),
  );
  if (accepted != true || !mounted) return;

  try {
    await _initAnalytics();
    if (!await Geolocator.isLocationServiceEnabled()) {
      _info('Turn on Location/GPS before sharing an approximate area.');
      return;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      _info('Location permission was not granted. You can still use the tracker without sharing an area.');
      return;
    }
    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.low,
        timeLimit: Duration(seconds: 12),
      ),
    );
    final response = await http.post(
      Uri.parse(api + '/api/analytics/location'),
      headers: await _appHeaders({'Content-Type': 'application/json', 'Accept': 'application/json'}),
      body: jsonEncode({
        'latitude': position.latitude,
        'longitude': position.longitude,
        'path': '/mobile',
        'session_id': analyticsSessionId,
        'visitor_id': analyticsVisitorId,
        'source': 'android',
      }),
    ).timeout(const Duration(seconds: 12));
    final data = jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300 || data is! Map<String, dynamic> || data['success'] != true) {
      throw Exception('Area sharing failed');
    }
    if (mounted) _info('Thanks. Your location was rounded into an approximate area for aggregate demand analytics.');
  } catch (_) {
    if (mounted) _info('Could not share the approximate area right now. You can continue using the tracker without it.');
  }
 }

 Future<void> _feedback() async {
  unawaited(_analytics('feedback_opened'));
  final messageController = TextEditingController();
  String rating = '5';
  String type = 'general';
  String status = '';
  bool sending = false;

  await showDialog<void>(
    context: context,
    builder: (dialogContext) => StatefulBuilder(
      builder: (context, setDialogState) => AlertDialog(
        title: const Text('Feedback & suggestions'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DropdownButtonFormField<String>(
                initialValue: rating,
                decoration: const InputDecoration(labelText: 'Rating'),
                items: const [
                  DropdownMenuItem(value: '5', child: Text('5 · Excellent')),
                  DropdownMenuItem(value: '4', child: Text('4 · Good')),
                  DropdownMenuItem(value: '3', child: Text('3 · Okay')),
                  DropdownMenuItem(value: '2', child: Text('2 · Poor')),
                  DropdownMenuItem(value: '1', child: Text('1 · Very poor')),
                ],
                onChanged: sending ? null : (value) { if (value != null) setDialogState(() => rating = value); },
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: type,
                decoration: const InputDecoration(labelText: 'Category'),
                items: const [
                  DropdownMenuItem(value: 'general', child: Text('General')),
                  DropdownMenuItem(value: 'location', child: Text('Location / map')),
                  DropdownMenuItem(value: 'bus-data', child: Text('Bus data / accuracy')),
                  DropdownMenuItem(value: 'performance', child: Text('Speed / performance')),
                  DropdownMenuItem(value: 'bug', child: Text('Bug or problem')),
                  DropdownMenuItem(value: 'other', child: Text('Other')),
                ],
                onChanged: sending ? null : (value) { if (value != null) setDialogState(() => type = value); },
              ),
              const SizedBox(height: 10),
              TextField(
                controller: messageController,
                maxLength: 1500,
                minLines: 3,
                maxLines: 6,
                decoration: const InputDecoration(
                  labelText: 'Your feedback',
                  hintText: 'What should we improve?',
                  border: OutlineInputBorder(),
                ),
              ),
              if (status.isNotEmpty) Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(status, style: TextStyle(color: status.startsWith('Sent') ? Colors.green : Colors.red, fontSize: 12)),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: sending ? null : () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: sending ? null : () async {
              final message = messageController.text.trim();
              if (message.isEmpty) {
                setDialogState(() => status = 'Enter a suggestion before sending.');
                return;
              }
              setDialogState(() { sending = true; status = 'Sending…'; });
              try {
                final response = await http.post(
                  Uri.parse(api + '/api/feedback'),
                  headers: await _appHeaders({'Content-Type': 'application/json', 'Accept': 'application/json'}),
                  body: jsonEncode({
                    'rating': rating,
                    'feedback_type': type,
                    'message': message,
                    'time': DateTime.now().toIso8601String(),
                  }),
                ).timeout(const Duration(seconds: 12));
                final data = jsonDecode(response.body);
                if (response.statusCode < 200 || response.statusCode >= 300 || data is! Map<String, dynamic> || data['success'] != true) {
                  throw Exception(data is Map<String, dynamic> ? data['detail']?.toString() : 'Feedback submission failed');
                }
                await _analytics('feedback_submitted', {'feedback_type': type, 'rating': rating});
                if (dialogContext.mounted) Navigator.pop(dialogContext);
                if (mounted) _info('Feedback sent. Thank you for helping improve the tracker.');
              } catch (_) {
                setDialogState(() { sending = false; status = 'Could not send feedback. Try again later.'; });
              }
            },
            child: Text(sending ? 'Sending…' : 'Send feedback'),
          ),
        ],
      ),
    ),
  );

  messageController.dispose();
 }

 void _settings() {
  unawaited(_analytics('settings_opened'));
  var currentDark = widget.dark;
  var alertsEnabled = nearbyAlerts;
  var currentAnalyticsEnabled = analyticsEnabled;

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
                  leading: const Icon(Icons.feedback_outlined),
                  title: const Text('Feedback & suggestions'),
                  subtitle: const Text('Send ideas or report app problems'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _feedback();
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.location_searching_outlined),
                  title: const Text('Help improve this area'),
                  subtitle: const Text('Optional one-time approximate location share'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _shareApproximateLocation();
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.privacy_tip_outlined),
                  title: const Text('Privacy notice'),
                  subtitle: const Text('Analytics, location and data controls'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _openWebsitePage('privacy.html');
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.gavel_outlined),
                  title: const Text('Terms of use'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _openWebsitePage('terms.html');
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.storage_outlined),
                  title: const Text('Data sources'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _openWebsitePage('data-sources.html');
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.accessibility_new_outlined),
                  title: const Text('Accessibility'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _openWebsitePage('accessibility.html');
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.cookie_outlined),
                  title: const Text('Cookies & storage'),
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _openWebsitePage('cookies.html');
                  },
                ),
                SwitchListTile(
                  value: currentAnalyticsEnabled,
                  secondary: const Icon(Icons.insights_outlined),
                  title: const Text('Usage analytics'),
                  subtitle: Text(
                    currentAnalyticsEnabled
                        ? 'Enabled · app usage, device details and approximate network area'
                        : 'Disabled · no new app analytics events will be sent',
                  ),
                  onChanged: (value) async {
                    setSheetState(() => currentAnalyticsEnabled = value);
                    final prefs = await SharedPreferences.getInstance();
                    await prefs.setBool('analytics_consent_v2', value);
                    await prefs.setBool('analytics_enabled', value);
                    if (mounted) {
                      setState(() => analyticsEnabled = value);
                      if (value) await _recordAppOpen();
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
  if (maintenanceMode) return _maintenancePage();
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
            if (value == 'routes') _openRoutes();
            if (value == 'favourites') _openFavourites();
            if (value == 'settings') _settings();
          },
          itemBuilder: (context) => const [
            PopupMenuItem(
              value: 'routes',
              child: Text('Routes & stops'),
            ),
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
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 700;
          final content = <Widget>[
            if (compact) ...[
              _mapCard(),
              const SizedBox(height: 10),
              _searchCard(),
              const SizedBox(height: 10),
              _locationCard(),
            ] else ...[
              _locationCard(),
              const SizedBox(height: 12),
              _searchCard(),
              const SizedBox(height: 12),
              _mapCard(),
            ],
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
          ];

          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
            children: content,
          );
        },
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
  final stopByName = <String, Map<String, dynamic>>{};
  for (final route in routeData) {
    final points = route['points'];
    if (points is! List) continue;
    for (final point in points) {
      if (point is! Map) continue;
      final stop = Map<String, dynamic>.from(point);
      final name = stop['name']?.toString() ?? '';
      if (name.isNotEmpty) stopByName.putIfAbsent(name, () => stop);
    }
  }
  final stopsToShow = stopByName.isNotEmpty
      ? stopByName.values.toList()
      : stopData.map((stop) => <String, dynamic>{
          'name': stop[0],
          'latitude': stop[1],
          'longitude': stop[2],
        }).toList();


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
    for (final stop in stopsToShow) {
      final latitude = double.tryParse(stop['latitude'].toString());
      final longitude = double.tryParse(stop['longitude'].toString());
      if (latitude == null || longitude == null) continue;
      markers.add(
        Marker(
          point: LatLng(latitude, longitude),
          width: 32,
          height: 32,
          child: Tooltip(
            message: stop['name'].toString(),
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
              Tooltip(
                message: showRoutes ? 'Hide routes' : 'Show routes',
                child: IconButton(
                  onPressed: () {
                    if (routeData.isEmpty) unawaited(_loadRoutes());
                    setState(() => showRoutes = !showRoutes);
                  },
                  icon: Icon(showRoutes ? Icons.alt_route : Icons.route_outlined),
                ),
              ),
              Tooltip(
                message: stops ? 'Hide stops' : 'Show stops',
                child: IconButton(
                  onPressed: () => setState(() => stops = !stops),
                  icon: Icon(
                    stops
                        ? Icons.visibility
                        : Icons.location_on_outlined,
                  ),
                ),
              ),
              Tooltip(
                message: 'Use my location',
                child: IconButton(
                  onPressed: _location,
                  icon: const Icon(Icons.my_location),
                ),
              ),
              Tooltip(
                message: movePin ? 'Finish choosing location' : 'Move location pin',
                child: IconButton(
                  onPressed: () => setState(() => movePin = !movePin),
                  icon: Icon(
                    movePin
                        ? Icons.pin_drop
                        : Icons.edit_location_alt,
                  ),
                ),
              ),
              if (trail.isNotEmpty)
                Tooltip(
                  message: 'Clear trail',
                  child: IconButton(
                    onPressed: () => setState(() => trail = []),
                    icon: const Icon(Icons.clear),
                  ),
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
              if (showRoutes && routeData.isNotEmpty)
                PolylineLayer(
                  polylines: routeData.map<Polyline>((route) {
                    final points = List<dynamic>.from(route['points'] ?? []);
                    return Polyline(
                      points: points.map((point) => LatLng(
                        double.tryParse(point['latitude'].toString()) ?? 0,
                        double.tryParse(point['longitude'].toString()) ?? 0,
                      )).toList(),
                      strokeWidth: 3,
                      color: const Color(0xFF668A2E).withOpacity(.75),
                    );
                  }).where((line) => line.points.length >= 2).toList(),
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
  final lastStop=(b['last_passed_stop']??b['last_stop'])?.toString();
  final nextStop=(b['likely_next_stop']??b['likely_towards'])?.toString();
  final destination=(b['likely_destination']??'').toString();
  final etaLabel=(b['eta_label']??'').toString();
  final etaMin=int.tryParse(b['eta_min']?.toString()??'');
  final etaMax=int.tryParse(b['eta_max']?.toString()??'');
  final positionConfidence=(b['confidence_label']??b['position_confidence']??b['gps_confidence']??'').toString();
  final nearbyPlace=(b['nearby_place']??b['location_label']??'').toString();
  final gpsAge=int.tryParse((b['gps_age_seconds']??b['fix_age_seconds']??'').toString());
  final gpsFreshness=(b['gps_freshness']??'').toString().toLowerCase();
  final stale=b['data_stale']==true||b['is_stale']==true||gpsFreshness=='stale'||gpsFreshness=='unknown'||(gpsAge!=null&&gpsAge>120);
  final route=_routeForBus(b);
  final moved=_movedLastMinutes(id);
  final status=(b['movement_status']??b['vehicle_status']??'unknown').toString().toLowerCase();
  final isMoving=!stale&&status=='moving'&&((speed??0)>=3);
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
                            stale
                                ? 'Last known GPS'
                                : isMoving
                                    ? 'Live GPS'
                                    : status=='stationary'
                                        ? 'Stationary'
                                        : 'Not moving',
                            style:TextStyle(fontSize:12,color:stale?const Color(0xFFB45309):const Color(0xFF6B7280),fontWeight:FontWeight.w700),
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
            Padding(
              padding:const EdgeInsets.only(top:10),
              child:Row(
                children:[
                  Icon(
                    isMoving?Icons.navigation_rounded:Icons.pause_circle_outline_rounded,
                    size:20,
                  ),
                  const SizedBox(width:7),
                  Expanded(
                    child:Text(
                      isMoving
                          ? 'Moving towards '+((dir is String&&dir.isNotEmpty)?dir:'destination')
                          : status=='stationary'
                              ? 'Stationary'
                              : 'Not moving',
                      style:const TextStyle(fontWeight:FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ),
            if ((lastStop != null && lastStop.isNotEmpty) || (nextStop != null && nextStop.isNotEmpty) || destination.isNotEmpty || etaLabel.isNotEmpty || positionConfidence.isNotEmpty || nearbyPlace.isNotEmpty || gpsAge != null)
              Container(
                width: double.infinity,
                margin: const EdgeInsets.only(top: 10),
                padding: const EdgeInsets.all(11),
                decoration: BoxDecoration(
                  border: Border.all(color: Theme.of(context).dividerColor),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (lastStop != null && lastStop.isNotEmpty)
                      Text('Last passed stop · $lastStop', style: const TextStyle(fontSize: 12)),
                    if (nextStop != null && nextStop.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text('Next stop · $nextStop', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                      ),
                    if (destination.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text('Likely destination · $destination', style: const TextStyle(fontSize: 12)),
                      ),
                    if (nearbyPlace.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text(nearbyPlace, style: const TextStyle(fontSize: 12)),
                      ),
                    if (gpsAge != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text(
                          stale ? 'GPS delayed · updated ${gpsAge}s ago' : 'GPS updated ${gpsAge}s ago',
                          style: TextStyle(fontSize: 11, color: stale ? const Color(0xFFB45309) : const Color(0xFF6B7280)),
                        ),
                      ),
                    if (positionConfidence.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text('Position confidence · $positionConfidence', style: const TextStyle(fontSize: 11, color: Color(0xFF6B7280))),
                      ),
                    if (etaMin != null && etaMax != null && etaMax >= etaMin && b['eta_status'] == 'estimated')
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text('ETA range · $etaMin–$etaMax min', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                      ),
                    if (etaLabel.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text(etaLabel, style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
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
              crossAxisAlignment:WrapCrossAlignment.center,
              children:[
                _chip(followed==id&&following?'Following':'Track bus',Icons.center_focus_strong,()=>_follow(b)),
                _chip('Share',Icons.share_outlined,()=>_share(b)),
                PopupMenuButton<String>(
                  tooltip:'More bus actions',
                  onSelected:(value){
                    if(value=='eta')_eta(b);
                    if(value=='trail')_trail(b);
                    if(value=='play')_play(b);
                    if(value=='report')_report(b);
                  },
                  itemBuilder:(context)=>const [
                    PopupMenuItem(value:'eta',child:Text('ETA')),
                    PopupMenuItem(value:'trail',child:Text('View trail')),
                    PopupMenuItem(value:'play',child:Text('Playback')),
                    PopupMenuItem(value:'report',child:Text('Report issue')),
                  ],
                  child:const Padding(
                    padding:EdgeInsets.symmetric(horizontal:13,vertical:9),
                    child:Icon(Icons.more_horiz_rounded,size:20),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

 Widget _chip(String label, IconData icon, VoidCallback onTap) {
  return ActionChip(
    avatar: Icon(icon, size: 17),
    label: Text(
      label,
      style: const TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w700,
      ),
    ),
    onPressed: onTap,
    padding: const EdgeInsets.symmetric(horizontal: 4),
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