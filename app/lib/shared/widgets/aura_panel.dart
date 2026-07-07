import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:flutter/material.dart';

class AuraPanel extends StatelessWidget {
  const AuraPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.borderRadius = 28,
    this.color,
    this.borderColor,
    this.withShadow = false,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final Color? color;
  final Color? borderColor;
  final bool withShadow;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? aura.surface,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(color: borderColor ?? aura.border),
        boxShadow: withShadow
            ? [
                BoxShadow(
                  color: aura.shadow.withValues(alpha: 0.32),
                  blurRadius: 36,
                  offset: const Offset(0, 20),
                ),
              ]
            : null,
      ),
      child: child,
    );
  }
}
