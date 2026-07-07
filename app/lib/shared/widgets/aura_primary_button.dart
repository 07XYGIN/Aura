import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:flutter/material.dart';

class AuraPrimaryButton extends StatelessWidget {
  const AuraPrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.danger = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final foreground = danger ? const Color(0xFF34151A) : aura.onGradient;
    final gradient = danger
        ? LinearGradient(
            colors: [aura.danger, aura.danger.withValues(alpha: 0.82)],
          )
        : aura.primaryGradient;

    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: onPressed == null ? null : gradient,
        color: onPressed == null ? aura.surfaceStrong : null,
        borderRadius: BorderRadius.circular(20),
        boxShadow: onPressed == null
            ? null
            : [
                BoxShadow(
                  color: (danger ? aura.danger : aura.primary).withValues(
                    alpha: 0.24,
                  ),
                  blurRadius: 30,
                  offset: const Offset(0, 18),
                ),
              ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 15),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 18, color: foreground),
                  const SizedBox(width: 10),
                ],
                Text(
                  label,
                  style: TextStyle(
                    color: onPressed == null ? aura.textSoft : foreground,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
