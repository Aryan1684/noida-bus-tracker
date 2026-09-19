import 'package:flutter/material.dart';

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
      theme: ThemeData(useMaterial3: true),
      home: const Scaffold(
        body: Center(
          child: Text('Noida Bus Tracker'),
        ),
      ),
    );
  }
}
