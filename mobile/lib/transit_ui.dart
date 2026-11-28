import 'package:flutter/material.dart';

Duration motionTime(BuildContext context, [int milliseconds = 260]) =>
    MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : Duration(milliseconds: milliseconds);

ThemeData transitTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final colors = ColorScheme.fromSeed(
    seedColor: const Color(0xff5045bd),
    brightness: brightness,
    surface: dark ? const Color(0xff202238) : Colors.white,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: colors,
    scaffoldBackgroundColor: dark ? const Color(0xff121425) : const Color(0xfff1f2fa),
    appBarTheme: AppBarTheme(
      backgroundColor: dark ? const Color(0xff121425) : const Color(0xfff1f2fa),
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: colors.surface,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
    ),
    snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
  );
}

class RouteReveal extends StatelessWidget {
  final Widget child;
  final int milliseconds;
  const RouteReveal({super.key, required this.child, this.milliseconds = 350});

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.disableAnimationsOf(context)) return child;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: milliseconds),
      curve: Curves.easeOutCubic,
      child: child,
      builder: (_, t, content) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, 12 * (1 - t)), child: content),
      ),
    );
  }
}

class FleetBanner extends StatelessWidget {
  final VoidCallback open;
  const FleetBanner({super.key, required this.open});
  @override
  Widget build(BuildContext context) {
    return Material(
      borderRadius: BorderRadius.circular(22),
      clipBehavior: Clip.antiAlias,
      child: Ink(
        decoration: const BoxDecoration(gradient: LinearGradient(
          colors: [Color(0xff242453), Color(0xff5144ad)],
        )),
        child: InkWell(
          onTap: open,
          child: Stack(alignment: Alignment.centerRight, children: [
            const Positioned(right: 0, top: 0, bottom: 0, width: 104,
              child: CustomPaint(painter: _Lines())),
            Padding(padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 18),
              child: Row(children: [
                const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('NOIDA  /  GREATER NOIDA', style: TextStyle(fontSize: 11, letterSpacing: 1.4, fontWeight: FontWeight.w700, color: Color(0xffd7d3ff))),
                  SizedBox(height: 5),
                  Text('Electric Fleet Map', style: TextStyle(color: Colors.white, fontSize: 23, fontWeight: FontWeight.w800, letterSpacing: -.6)),
                ])),
                Chip(label: const Text('New'), visualDensity: VisualDensity.compact,
                  side: BorderSide.none, backgroundColor: const Color(0xffb9f3eb),
                  labelStyle: const TextStyle(color: Color(0xff123e42), fontWeight: FontWeight.bold)),
                const SizedBox(width: 5), const Icon(Icons.north_east, color: Colors.white, size: 19),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

class _Lines extends CustomPainter {
  const _Lines();
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0x40b9f3eb)..strokeWidth = 2..style = PaintingStyle.stroke;
    for (final y in [12.0, 26.0, 40.0]) {
      final path = Path()..moveTo(0, size.height + y)..lineTo(42, size.height - 42 + y)
        ..quadraticBezierTo(49, size.height - 49 + y, 60, size.height - 49 + y)
        ..lineTo(size.width, size.height - 49 + y);
      canvas.drawPath(path, paint);
    }
  }
  @override
  bool shouldRepaint(_Lines oldDelegate) => false;
}
