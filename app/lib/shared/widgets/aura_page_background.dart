import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:flutter/material.dart';

class AuraPageBackground extends StatelessWidget {
  const AuraPageBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: aura.bg,
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            aura.bg,
            Color.alphaBlend(aura.primary.withValues(alpha: 0.04), aura.bg),
            aura.bg,
          ],
          stops: const [0, 0.48, 1],
        ),
      ),
      child: child,
    );
  }
}
