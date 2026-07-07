import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:aifrd_app/features/app/application/aura_app_state.dart';
import 'package:aifrd_app/features/chat/presentation/chat_screen.dart';
import 'package:aifrd_app/features/memories/presentation/memories_screen.dart';
import 'package:aifrd_app/features/settings/presentation/settings_screen.dart';
import 'package:aifrd_app/shared/widgets/aura_page_background.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class AuraMobileShell extends StatelessWidget {
  const AuraMobileShell({super.key});

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AuraAppState>();

    return AuraPageBackground(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: IndexedStack(
          index: appState.currentTab.index,
          children: const [ChatScreen(), MemoriesScreen(), SettingsScreen()],
        ),
        bottomNavigationBar: const _AuraBottomNavigationBar(),
      ),
    );
  }
}

class _AuraBottomNavigationBar extends StatelessWidget {
  const _AuraBottomNavigationBar();

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final appState = context.watch<AuraAppState>();

    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 12),
        decoration: BoxDecoration(
          color: aura.surfaceSolid.withValues(alpha: 0.94),
          border: Border(top: BorderSide(color: aura.border)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _NavItem(
              tab: AuraTab.chat,
              activeTab: appState.currentTab,
              icon: Icons.chat_bubble_outline_rounded,
              activeIcon: Icons.chat_bubble_rounded,
              label: '对话',
            ),
            _NavItem(
              tab: AuraTab.memories,
              activeTab: appState.currentTab,
              icon: Icons.auto_awesome_motion_outlined,
              activeIcon: Icons.auto_awesome_motion,
              label: '记忆',
            ),
            _NavItem(
              tab: AuraTab.settings,
              activeTab: appState.currentTab,
              icon: Icons.settings_outlined,
              activeIcon: Icons.settings,
              label: '设置',
            ),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.tab,
    required this.activeTab,
    required this.icon,
    required this.activeIcon,
    required this.label,
  });

  final AuraTab tab;
  final AuraTab activeTab;
  final IconData icon;
  final IconData activeIcon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final isActive = tab == activeTab;

    return Semantics(
      button: true,
      selected: isActive,
      label: label,
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () => context.read<AuraAppState>().changeTab(tab),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: 76,
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isActive
                ? aura.primarySoft.withValues(alpha: 0.42)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                isActive ? activeIcon : icon,
                color: isActive ? aura.primary : aura.textSoft,
                size: 26,
              ),
              const SizedBox(height: 5),
              Text(
                label,
                style: TextStyle(
                  color: isActive ? aura.primary : aura.textSoft,
                  fontSize: 12,
                  fontWeight: isActive ? FontWeight.w800 : FontWeight.w600,
                  letterSpacing: 0.2,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
