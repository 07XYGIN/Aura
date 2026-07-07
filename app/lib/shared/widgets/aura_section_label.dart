import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:flutter/material.dart';

class AuraSectionLabel extends StatelessWidget {
  const AuraSectionLabel(this.label, {super.key});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 6, bottom: 10),
      child: Text(
        label,
        style: TextStyle(
          color: context.aura.textSoft,
          fontSize: 12,
          fontWeight: FontWeight.w800,
          letterSpacing: 1.4,
        ),
      ),
    );
  }
}
