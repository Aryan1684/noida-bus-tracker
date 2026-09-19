import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:latlong2/latlong.dart';

void main() {
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
        scaffoldBackgroundColor: const Color(0xFFF5F7FA),
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
  bool loading = false;
  String? error;
  double radius = 5;

  @override
  void initState() {
    super.initState();
    loadLocationAndBuses();
  }

  Future<void> loadLocationAndBuses() async {
    setState(() {
      loading = true;
      error = null;
    });

    try {
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.always ||
          permission == LocationPermission.whileInUse) {
        final position = await Geolocator.getCurrentPosition();
        location = LatLng(position.latitude, position.longitude);
      }

      await loadBuses();
    } catch (_) {
      if (mounted) {
        setState(() {
          error = 'Unable to get your location.';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          loading = false;
        });
      }
    }
  }

  Future<void> loadBuses() async {
    final uri = Uri.parse(
      '$apiBase/api/buses/nearby?lat=${location.latitude}&lon=${location.longitude}&radius=$radius',
    );

    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 20));

      if (response.statusCode != 200) {
        throw Exception('Server error');
      }

      final data = jsonDecode(response.body);

      if (mounted) {
        setState(() {
          buses = data['buses'] ?? [];
          error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          error = 'Unable to load buses right now.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: RefreshIndicator(
                onRefresh: loadLocationAndBuses,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  children: [
                    _buildLocationCard(),
                    const SizedBox(height: 12),
                    _buildMap(),
                    const SizedBox(height: 16),
                    _buildResultsHeader(),
                    if (error != null) _buildError(),
                    if (loading && buses.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(28),
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else if (buses.isEmpty)
                      _buildEmpty()
                    else
                      ...buses.map((bus) => _buildBusCard(bus)),
                    const SizedBox(height: 12),
                    _buildDisclaimer(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: loading ? null : loadLocationAndBuses,
        child: const Icon(Icons.refresh),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 12),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xFFE5E7EB))),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(13),
            ),
            child: const Icon(Icons.directions_bus, color: Colors.white),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Noida Bus Tracker',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                ),
                Text(
                  'Electric buses • Live GPS',
                  style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
            decoration: BoxDecoration(
              color: const Color(0xFFEAF8EF),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Row(
              children: [
                Icon(Icons.circle, size: 8, color: Color(0xFF16A34A)),
                SizedBox(width: 6),
                Text(
                  'LIVE',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF15803D),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        children: [
          const Icon(Icons.location_on_outlined, color: Color(0xFF111827)),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'Nearby buses',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
            ),
          ),
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
                loadBuses();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMap() {
    final markers = buses.map<Marker?>((bus) {
      final lat = double.tryParse('${bus['latitude']}');
      final lon = double.tryParse('${bus['longitude']}');

      if (lat == null || lon == null) {
        return null;
      }

      return Marker(
        point: LatLng(lat, lon),
        width: 46,
        height: 46,
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF111827),
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 3),
          ),
          child: const Icon(Icons.directions_bus, color: Colors.white, size: 22),
        ),
      );
    }).whereType<Marker>().toList();

    markers.add(
      Marker(
        point: location,
        width: 34,
        height: 34,
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF2563EB),
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 4),
          ),
        ),
      ),
    );

    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: SizedBox(
        height: 310,
        child: FlutterMap(
          mapController: mapController,
          options: MapOptions(
            initialCenter: location,
            initialZoom: 12.5,
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'com.example.noida_bus_tracker',
            ),
            MarkerLayer(markers: markers),
          ],
        ),
      ),
    );
  }

  Widget _buildResultsHeader() {
    return Row(
      children: [
        Text(
          '${buses.length} buses nearby',
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
        ),
        const Spacer(),
        Text(
          'Live GPS',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: Colors.grey.shade600,
          ),
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
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: const Color(0xFFF0F2F5),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.directions_bus, color: Color(0xFF111827)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${bus['bus_id'] ?? 'Unknown bus'}',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 5),
                Wrap(
                  spacing: 8,
                  runSpacing: 5,
                  children: [
                    if (distance != null)
                      Text(
                        '${distance.toStringAsFixed(2)} km away',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                      ),
                    if (speed != null)
                      Text(
                        '${speed.toStringAsFixed(0)} km/h',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                      ),
                  ],
                ),
                if (direction is String && direction.isNotEmpty) ...[
                  const SizedBox(height: 7),
                  Text(
                    'Moving towards $direction',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
                  ),
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
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7ED),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        error!,
        style: const TextStyle(color: Color(0xFF9A3412), fontSize: 13, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _buildEmpty() {
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: const Column(
        children: [
          Icon(Icons.directions_bus_outlined, size: 42, color: Color(0xFF9CA3AF)),
          SizedBox(height: 10),
          Text('No buses found nearby', style: TextStyle(fontWeight: FontWeight.w800)),
          SizedBox(height: 5),
          Text(
            'Try increasing the search radius.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Color(0xFF6B7280), fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildDisclaimer() {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 8),
      child: Text(
        'Independent project. Not a government website. Live GPS data sourced from MARGDARSHI (UPSRTC).',
        textAlign: TextAlign.center,
        style: TextStyle(color: Color(0xFF6B7280), fontSize: 11),
      ),
    );
  }
}
