import 'package:flutter/material.dart';

@immutable
class AuraTokens extends ThemeExtension<AuraTokens> {
  const AuraTokens({
    required this.bg,
    required this.surface,
    required this.surfaceSolid,
    required this.surfaceMuted,
    required this.surfaceStrong,
    required this.border,
    required this.borderStrong,
    required this.text,
    required this.textMuted,
    required this.textSoft,
    required this.primary,
    required this.primaryStrong,
    required this.primarySoft,
    required this.secondary,
    required this.secondarySoft,
    required this.tertiary,
    required this.danger,
    required this.glow,
    required this.shadow,
    required this.onGradient,
  });

  final Color bg;
  final Color surface;
  final Color surfaceSolid;
  final Color surfaceMuted;
  final Color surfaceStrong;
  final Color border;
  final Color borderStrong;
  final Color text;
  final Color textMuted;
  final Color textSoft;
  final Color primary;
  final Color primaryStrong;
  final Color primarySoft;
  final Color secondary;
  final Color secondarySoft;
  final Color tertiary;
  final Color danger;
  final Color glow;
  final Color shadow;
  final Color onGradient;

  LinearGradient get primaryGradient => LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, secondary],
  );

  @override
  AuraTokens copyWith({
    Color? bg,
    Color? surface,
    Color? surfaceSolid,
    Color? surfaceMuted,
    Color? surfaceStrong,
    Color? border,
    Color? borderStrong,
    Color? text,
    Color? textMuted,
    Color? textSoft,
    Color? primary,
    Color? primaryStrong,
    Color? primarySoft,
    Color? secondary,
    Color? secondarySoft,
    Color? tertiary,
    Color? danger,
    Color? glow,
    Color? shadow,
    Color? onGradient,
  }) {
    return AuraTokens(
      bg: bg ?? this.bg,
      surface: surface ?? this.surface,
      surfaceSolid: surfaceSolid ?? this.surfaceSolid,
      surfaceMuted: surfaceMuted ?? this.surfaceMuted,
      surfaceStrong: surfaceStrong ?? this.surfaceStrong,
      border: border ?? this.border,
      borderStrong: borderStrong ?? this.borderStrong,
      text: text ?? this.text,
      textMuted: textMuted ?? this.textMuted,
      textSoft: textSoft ?? this.textSoft,
      primary: primary ?? this.primary,
      primaryStrong: primaryStrong ?? this.primaryStrong,
      primarySoft: primarySoft ?? this.primarySoft,
      secondary: secondary ?? this.secondary,
      secondarySoft: secondarySoft ?? this.secondarySoft,
      tertiary: tertiary ?? this.tertiary,
      danger: danger ?? this.danger,
      glow: glow ?? this.glow,
      shadow: shadow ?? this.shadow,
      onGradient: onGradient ?? this.onGradient,
    );
  }

  @override
  AuraTokens lerp(ThemeExtension<AuraTokens>? other, double t) {
    if (other is! AuraTokens) {
      return this;
    }

    Color mix(Color a, Color b) => Color.lerp(a, b, t) ?? a;

    return AuraTokens(
      bg: mix(bg, other.bg),
      surface: mix(surface, other.surface),
      surfaceSolid: mix(surfaceSolid, other.surfaceSolid),
      surfaceMuted: mix(surfaceMuted, other.surfaceMuted),
      surfaceStrong: mix(surfaceStrong, other.surfaceStrong),
      border: mix(border, other.border),
      borderStrong: mix(borderStrong, other.borderStrong),
      text: mix(text, other.text),
      textMuted: mix(textMuted, other.textMuted),
      textSoft: mix(textSoft, other.textSoft),
      primary: mix(primary, other.primary),
      primaryStrong: mix(primaryStrong, other.primaryStrong),
      primarySoft: mix(primarySoft, other.primarySoft),
      secondary: mix(secondary, other.secondary),
      secondarySoft: mix(secondarySoft, other.secondarySoft),
      tertiary: mix(tertiary, other.tertiary),
      danger: mix(danger, other.danger),
      glow: mix(glow, other.glow),
      shadow: mix(shadow, other.shadow),
      onGradient: mix(onGradient, other.onGradient),
    );
  }
}

extension AuraThemeX on BuildContext {
  AuraTokens get aura => Theme.of(this).extension<AuraTokens>()!;
}

class AuraTheme {
  static ThemeData light() => _build(_lightTokens, Brightness.light);

  static ThemeData dark() => _build(_darkTokens, Brightness.dark);

  static ThemeData _build(AuraTokens tokens, Brightness brightness) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: tokens.primary,
      brightness: brightness,
      surface: tokens.surfaceSolid,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: colorScheme.copyWith(
        primary: tokens.primary,
        secondary: tokens.secondary,
        error: tokens.danger,
        surface: tokens.surfaceSolid,
      ),
      scaffoldBackgroundColor: tokens.bg,
      fontFamily: 'Inter',
      extensions: [tokens],
      textTheme: const TextTheme().apply(
        fontFamily: 'Inter',
        bodyColor: tokens.text,
        displayColor: tokens.text,
      ),
      iconTheme: IconThemeData(color: tokens.textMuted),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: tokens.surfaceStrong.withValues(alpha: 0.62),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        hintStyle: TextStyle(color: tokens.textSoft.withValues(alpha: 0.62)),
        labelStyle: TextStyle(color: tokens.textMuted),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: BorderSide(color: tokens.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: BorderSide(color: tokens.borderStrong),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: tokens.surfaceStrong,
        contentTextStyle: TextStyle(color: tokens.text),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    );
  }
}

const _darkTokens = AuraTokens(
  bg: Color(0xFF0B1326),
  surface: Color(0xC2131B2E),
  surfaceSolid: Color(0xFF131B2E),
  surfaceMuted: Color(0xE0171F33),
  surfaceStrong: Color(0xFF2D3449),
  border: Color(0x2E958EA0),
  borderStrong: Color(0x57D0BCFF),
  text: Color(0xFFDAE2FD),
  textMuted: Color(0xFFCBC3D7),
  textSoft: Color(0xFF958EA0),
  primary: Color(0xFFD0BCFF),
  primaryStrong: Color(0xFFA078FF),
  primarySoft: Color(0xE6573878),
  secondary: Color(0xFFDBB8FF),
  secondarySoft: Color(0x29DBB8FF),
  tertiary: Color(0xFFFFB869),
  danger: Color(0xFFFFB4AB),
  glow: Color(0x3DD0BCFF),
  shadow: Color(0x8C000000),
  onGradient: Color(0xFF251739),
);

const _lightTokens = AuraTokens(
  bg: Color(0xFFF4F6FF),
  surface: Color(0xE0FFFFFF),
  surfaceSolid: Color(0xFFFFFFFF),
  surfaceMuted: Color(0xE0EBEFFC),
  surfaceStrong: Color(0xFFE6EAFB),
  border: Color(0x29695CAD),
  borderStrong: Color(0x47695CAD),
  text: Color(0xFF202A42),
  textMuted: Color(0xFF617090),
  textSoft: Color(0xFF8793AD),
  primary: Color(0xFF8D6CF7),
  primaryStrong: Color(0xFF6D44DA),
  primarySoft: Color(0xFFEDE6FF),
  secondary: Color(0xFFC79CFF),
  secondarySoft: Color(0x29C79CFF),
  tertiary: Color(0xFFFFB869),
  danger: Color(0xFFD95C69),
  glow: Color(0x472A385C),
  shadow: Color(0x592A385C),
  onGradient: Color(0xFF241637),
);
