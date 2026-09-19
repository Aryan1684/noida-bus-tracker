import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NoidaBusTrackerApp());
}

class NoidaBusTrackerApp extends StatelessWidget {
  const NoidaBusTrackerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Noida Bus Tracker',
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF4F6F8),
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF111827)),
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  static const apiBase = 'https://noida-bus-tracker.onrender.com';
  final mapController = MapController();

  LatLng location = const LatLng(28.4598, 77.5184);
  List<dynamic> buses = [];
  double radius = 5;
  bool loading = false;
  bool locationLoading = false;
  bool permissionDenied = false;
  String? error;
  String locationLabel = 'Use your current location';
  DateTime? lastRefreshed;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _showStartupNotice());
  }

  Future<void> _showStartupNotice() async {
    if (!mounted) return;
    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: const Row(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: Color(0xFFFFF4E5),
              child: Icon(Icons.info_outline, color: Color(0xFFB45309)),
            ),
            SizedBox(width: 12),
            Expanded(child: Text('One important note')),
          ],
        ),
        content: const Text(
          'Bus locations come from live GPS data. The “moving towards” information is an estimate from recent movement and can be wrong near junctions, turns or route changes.\n\nNot a government website.\nThis is an independent project made by a curious BTech student.\n\nData source: MARGDARSHI · UPSRTC',
          style: TextStyle(height: 1.45),
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Got it'),
          ),
        ],
      ),
    );
    if (mounted) await _requestLocation();
  }

  Future<void> _requestLocation() async {
    if (locationLoading) return;
    setState(() {
      locationLoading = true;
      error = null;
      permissionDenied = false;
    });

    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        setState(() {
          permissionDenied = true;
          locationLabel = permission == LocationPermission.deniedForever
              ? 'Location permission is blocked'
              : 'Location permission is needed';
          error = permission == LocationPermission.deniedForever
              ? 'Allow location permission from Android Settings to use your current location.'
              : 'Allow location permission to find buses near you.';
        });
        return;
      }

      if (!await Geolocator.isLocationServiceEnabled()) {
        setState(() {
          error = 'Location services are turned off on your phone.';
          locationLabel = 'Turn on location services';
        });
        return;
      }

      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
      );

      final next = LatLng(position.latitude, position.longitude);
      setState(() {
        location = next;
        locationLabel = 'Current location';
      });
      mapController.move(next, 14.5);
      await _loadBuses();
    } catch (_) {
      setState(() {
        error = 'Could not get your current location. You can move the map instead.';
        locationLabel = 'Location unavailable';
      });
    } finally {
      if (mounted) setState(() => locationLoading = false);
    }
  }

  Future<void> _loadBuses() async {
    if (loading) return;
    setState(() {
      loading = true;
      error = null;
    });

    final uri = Uri.parse(
      '$apiBase/api/buses/nearby?lat=${location.latitude}&lon=${location.longitude}&radius=$radius',
    );

    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 20));
      if (response.statusCode != 200) throw Exception();
      final data = jsonDecode(response.body);
      if (!mounted) return;
      setState(() {
        buses = data['buses'] ?? [];
        lastRefreshed = DateTime.now();
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        error = 'The bus service is temporarily unavailable. Showing the last results if available.';
      });
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        elevation: 0,
        titleSpacing: 18,
        title: const Row(
          children: [
            Icon(Icons.directions_bus_rounded, size: 27),
            SizedBox(width: 9),
            Text('Noida Bus Tracker', style: TextStyle(fontWeight: FontWeight.w800)),
          ],
        ),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: const Color(0xFFEAF8EF),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Row(
              children: [
                Icon(Icons.circle, size: 7, color: Color(0xFF16A34A)),
                SizedBox(width: 5),
                Text('LIVE', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: Color(0xFF15803D))),
              ],
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadBuses,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            _buildLocationCard(),
            const SizedBox(height: 14),
            _buildMap(),
            const SizedBox(height: 14),
            _buildResultsHeader(),
            if (error != null) _buildError(),
            if (loading && buses.isEmpty)
              const Padding(
                padding: EdgeInsets.all(30),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (buses.isEmpty)
              _buildEmpty()
            else
              ...buses.map(_buildBusCard),
            const SizedBox(height: 16),
            _buildDisclaimer(),
          ],
        ),
      ),
    );
  }

  Widget _buildLocationCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE5E7EB)),
        boxShadow: const [BoxShadow(color: Color(0x0A000000), blurRadius: 18, offset: Offset(0, 6))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('FIND BUSES NEAR YOU', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 1.1, color: Color(0xFF6B7280))),
          const SizedBox(height: 7),
          const Text('Where are you?', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(locationLabel, style: const TextStyle(color: Color(0xFF6B7280))),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            height: 50,
            child: FilledButton.icon(
              onPressed: locationLoading ? null : _requestLocation,
              icon: locationLoading
                  ? const SizedBox(width: 19, height: 19, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.my_location_rounded),
              label: Text(locationLoading ? 'Getting location…' : 'Use current location'),
            ),
          ),
          if (permissionDenied) ...[
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: Geolocator.openAppSettings,
                icon: const Icon(Icons.settings_outlined),
                label: const Text('Open location settings'),
              ),
            ),
          ],
          const SizedBox(height: 10),
          Row(
            children: [
              const Icon(Icons.tune_rounded, size: 18, color: Color(0xFF6B7280)),
              const SizedBox(width: 7),
              const Text('Search radius', style: TextStyle(fontWeight: FontWeight.w600)),
              const Spacer(),
              DropdownButtonHideUnderline(
                child: DropdownButton<double>(
                  value: radius,
                  items: const [
                    DropdownMenuItem(value: 2, child: Text('2 km')),
                    DropdownMenuItem(value: 5, child: Text('5 km')),
                    DropdownMenuItem(value: 10, child: Text('10 km')),
                    DropdownMenuItem(value: 15, child: Text('15 km')),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => radius = value);
                    _loadBuses();
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMap() {
    final markers = buses.map<Marker?>((bus) {
      final lat = double.tryParse('${bus['latitude']}');
      final lon = double.tryParse('${bus['longitude']}');
      if (lat == null || lon == null) return null;
      return Marker(
        point: LatLng(lat, lon),
        width: 46,
        height: 46,
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF111827),
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 3),
            boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 8, offset: Offset(0, 3))],
          ),
          child: const Icon(Icons.directions_bus_rounded, color: Colors.white, size: 22),
        ),
      );
    }).whereType<Marker>().toList();

    markers.add(
      Marker(
        point: location,
        width: 38,
        height: 38,
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF2563EB),
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 4),
            boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 8)],
          ),
          child: const Icon(Icons.my_location_rounded, color: Colors.white, size: 18),
        ),
      ),
    );

    return Container(
      height: 330,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Stack(
        children: [
          FlutterMap(
            mapController: mapController,
            options: MapOptions(initialCenter: location, initialZoom: 12.5),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.example.noida_bus_tracker',
              ),
              MarkerLayer(markers: markers),
            ],
          ),
          Positioned(
            right: 12,
            bottom: 12,
            child: Material(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              elevation: 3,
              child: InkWell(
                borderRadius: BorderRadius.circular(14),
                onTap: _requestLocation,
                child: const Padding(
                  padding: EdgeInsets.all(12),
                  child: Icon(Icons.my_location_rounded),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultsHeader() {
    final time = lastRefreshed == null
        ? 'Not refreshed yet'
        : 'Updated ${lastRefreshed!.hour.toString().padLeft(2, '0')}:${lastRefreshed!.minute.toString().padLeft(2, '0')}';
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Nearby electric buses', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
              const SizedBox(height: 3),
              Text(time, style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
            ],
          ),
        ),
        IconButton(
          onPressed: loading ? null : _loadBuses,
          tooltip: 'Refresh buses',
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    );
  }

  Widget _buildBusCard(dynamic bus) {
    final speed = double.tryParse('${bus['speed'] ?? ''}');
    final distance = double.tryParse('${bus['distance_km'] ?? ''}');
    final direction = bus['likely_towards'];
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(19),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(
              color: const Color(0xFFF1F3F5),
              borderRadius: BorderRadius.circular(15),
            ),
            child: const Icon(Icons.directions_bus_rounded, size: 26),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${bus['bus_id'] ?? 'Unknown bus'}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 10,
                  children: [
                    if (distance != null) Text('${distance.toStringAsFixed(2)} km', style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                    if (speed != null) Text('${speed.toStringAsFixed(0)} km/h', style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                  ],
                ),
                if (direction is String && direction.isNotEmpty) ...[
                  const SizedBox(height: 7),
                  Text('Moving towards $direction', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(color: const Color(0xFFFFF7ED), borderRadius: BorderRadius.circular(15)),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Color(0xFFB45309)),
          const SizedBox(width: 9),
          Expanded(child: Text(error!, style: const TextStyle(color: Color(0xFF92400E), fontSize: 12, fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }

  Widget _buildEmpty() {
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(19), border: Border.all(color: const Color(0xFFE5E7EB))),
      child: const Column(
        children: [
          Icon(Icons.directions_bus_outlined, size: 44, color: Color(0xFF9CA3AF)),
          SizedBox(height: 10),
          Text('No buses found nearby', style: TextStyle(fontWeight: FontWeight.w800)),
          SizedBox(height: 5),
          Text('Try increasing the radius or moving the map.', textAlign: TextAlign.center, style: TextStyle(color: Color(0xFF6B7280), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildDisclaimer() {
    return const Text(
      'Independent project. Not a government website.\nLive GPS data sourced from MARGDARSHI · UPSRTC.',
      textAlign: TextAlign.center,
      style: TextStyle(color: Color(0xFF6B7280), fontSize: 11, height: 1.5),
    );
  }
}
