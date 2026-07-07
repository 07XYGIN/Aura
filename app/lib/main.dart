import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:aifrd_app/features/app/application/aura_app_state.dart';
import 'package:aifrd_app/features/app/presentation/aura_mobile_shell.dart';
import 'package:aifrd_app/features/auth/presentation/auth_screen.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => AuraAppState(),
      child: const AuraApp(),
    ),
  );
}

class AuraApp extends StatelessWidget {
  const AuraApp({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AuraAppState>(
      builder: (context, appState, _) {
        return MaterialApp(
          title: 'Arua',
          debugShowCheckedModeBanner: false,
          theme: AuraTheme.light(),
          darkTheme: AuraTheme.dark(),
          themeMode: appState.isDarkMode ? ThemeMode.dark : ThemeMode.light,
          home: appState.isAuthenticated
              ? const AuraMobileShell()
              : const AuthScreen(),
        );
      },
    );
  }
}
