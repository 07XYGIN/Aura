// 页面说明：
// 这个页面使用 StatefulWidget 管理输入框控制器，用 Provider 里的 AuraAppState 管理登录/注册 Tab、记住我和协议勾选等跨控件状态。
// 布局上用 SingleChildScrollView + ConstrainedBox 模拟移动端居中表单，AruaPanel 复用 PC 端的 glass/panel 视觉 token。

import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:aifrd_app/features/app/application/aura_app_state.dart';
import 'package:aifrd_app/shared/widgets/aura_page_background.dart';
import 'package:aifrd_app/shared/widgets/aura_panel.dart';
import 'package:aifrd_app/shared/widgets/aura_primary_button.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _usernameController = TextEditingController(text: 'xiaoyun');
  final _emailController = TextEditingController(
    text: 'xiaoyun.lin@example.com',
  );
  final _ageController = TextEditingController(text: '27');
  final _inviteController = TextEditingController();
  final _passwordController = TextEditingController(text: 'password');

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    _ageController.dispose();
    _inviteController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final appState = context.watch<AuraAppState>();
    final isRegister = appState.authMode == AuthMode.register;

    return AuraPageBackground(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(18, 34, 18, 28),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(
                  children: [
                    const SizedBox(height: 22),
                    Text(
                      'Arua',
                      style: TextStyle(
                        color: aura.primary,
                        fontSize: 46,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.5,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Always here for you',
                      style: TextStyle(
                        color: aura.textMuted,
                        fontSize: 18,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 38),
                    AuraPanel(
                      withShadow: true,
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _AuthTabs(isRegister: isRegister),
                          const SizedBox(height: 26),
                          AutofillGroup(
                            child: Column(
                              children: [
                                _AuraTextField(
                                  controller: _usernameController,
                                  icon: Icons.person_outline_rounded,
                                  label: '用户名',
                                  hint: isRegister ? '设置用户名' : '用户名 / 邮箱',
                                  autofillHints: const [AutofillHints.username],
                                ),
                                if (isRegister) ...[
                                  const SizedBox(height: 14),
                                  _AuraTextField(
                                    controller: _emailController,
                                    icon: Icons.mail_outline_rounded,
                                    label: '邮箱地址',
                                    hint: 'name@email.com',
                                    keyboardType: TextInputType.emailAddress,
                                    autofillHints: const [AutofillHints.email],
                                  ),
                                  const SizedBox(height: 14),
                                  _AuraTextField(
                                    controller: _ageController,
                                    icon: Icons.cake_outlined,
                                    label: '年龄',
                                    hint: '请输入年龄',
                                    keyboardType: TextInputType.number,
                                  ),
                                  const SizedBox(height: 14),
                                  _AuraTextField(
                                    controller: _inviteController,
                                    icon: Icons.key_rounded,
                                    label: '邀请码',
                                    hint: '如果有邀请码，请填写',
                                  ),
                                ],
                                const SizedBox(height: 14),
                                _AuraTextField(
                                  controller: _passwordController,
                                  icon: Icons.lock_outline_rounded,
                                  label: '密码',
                                  hint: isRegister ? '至少 8 个字符' : '输入密码',
                                  obscureText: true,
                                  autofillHints: const [AutofillHints.password],
                                ),
                              ],
                            ),
                          ),
                          if (isRegister) ...[
                            const SizedBox(height: 16),
                            const _SexPicker(),
                            const SizedBox(height: 16),
                            const _TermsRow(),
                          ] else ...[
                            const SizedBox(height: 16),
                            const _LoginOptionsRow(),
                          ],
                          const SizedBox(height: 24),
                          AuraPrimaryButton(
                            label: isRegister ? '创建账号' : '立即登录',
                            icon: isRegister
                                ? Icons.person_add_alt_1
                                : Icons.login_rounded,
                            onPressed: () => _submit(context, isRegister),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 30),
                    Text(
                      '已启用安全加密保护。继续使用即代表你同意服务条款。',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: aura.textSoft,
                        fontSize: 13,
                        height: 1.6,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _submit(BuildContext context, bool isRegister) {
    final appState = context.read<AuraAppState>();

    if (_usernameController.text.trim().isEmpty ||
        _passwordController.text.trim().isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('请先填写用户名和密码。')));
      return;
    }

    if (isRegister && !appState.acceptedTerms) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('注册前需要先同意服务条款。')));
      return;
    }

    appState.enterApp();
  }
}

class _AuthTabs extends StatelessWidget {
  const _AuthTabs({required this.isRegister});

  final bool isRegister;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(
        color: context.aura.surfaceStrong.withValues(alpha: 0.28),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: context.aura.border),
      ),
      child: Row(
        children: [
          _TabButton(
            label: '登录',
            selected: !isRegister,
            onTap: () =>
                context.read<AuraAppState>().setAuthMode(AuthMode.login),
          ),
          _TabButton(
            label: '注册',
            selected: isRegister,
            onTap: () =>
                context.read<AuraAppState>().setAuthMode(AuthMode.register),
          ),
        ],
      ),
    );
  }
}

class _TabButton extends StatelessWidget {
  const _TabButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          alignment: Alignment.center,
          padding: const EdgeInsets.symmetric(vertical: 11),
          decoration: BoxDecoration(
            color: selected ? aura.primarySoft : Colors.transparent,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: selected ? aura.primary : aura.textMuted,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.5,
            ),
          ),
        ),
      ),
    );
  }
}

class _AuraTextField extends StatelessWidget {
  const _AuraTextField({
    required this.controller,
    required this.icon,
    required this.label,
    required this.hint,
    this.obscureText = false,
    this.keyboardType,
    this.autofillHints,
  });

  final TextEditingController controller;
  final IconData icon;
  final String label;
  final String hint;
  final bool obscureText;
  final TextInputType? keyboardType;
  final Iterable<String>? autofillHints;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 7),
          child: Text(
            label,
            style: TextStyle(
              color: aura.textMuted,
              fontSize: 12,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.8,
            ),
          ),
        ),
        TextField(
          controller: controller,
          obscureText: obscureText,
          keyboardType: keyboardType,
          autofillHints: autofillHints,
          style: TextStyle(color: aura.text, fontWeight: FontWeight.w600),
          decoration: InputDecoration(
            prefixIcon: Icon(icon, color: aura.primary, size: 20),
            hintText: hint,
          ),
        ),
      ],
    );
  }
}

class _LoginOptionsRow extends StatelessWidget {
  const _LoginOptionsRow();

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final appState = context.watch<AuraAppState>();

    return Row(
      children: [
        Checkbox(
          value: appState.rememberMe,
          activeColor: aura.primary,
          checkColor: aura.onGradient,
          side: BorderSide(color: aura.borderStrong),
          onChanged: (value) =>
              context.read<AuraAppState>().setRememberMe(value ?? false),
        ),
        Text('记住我', style: TextStyle(color: aura.textMuted)),
        const Spacer(),
        TextButton(
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('密码找回需要邮箱或短信验证码接口接入后开放。')),
            );
          },
          child: Text('忘记密码？', style: TextStyle(color: aura.primary)),
        ),
      ],
    );
  }
}

class _SexPicker extends StatelessWidget {
  const _SexPicker();

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AuraAppState>();

    return Row(
      children: [
        Expanded(
          child: _ChoiceButton(
            label: '男',
            selected: appState.sex == '1',
            onTap: () => context.read<AuraAppState>().updateProfile(
              displayName: appState.displayName,
              email: appState.email,
              age: appState.age,
              sex: '1',
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _ChoiceButton(
            label: '女',
            selected: appState.sex == '0',
            onTap: () => context.read<AuraAppState>().updateProfile(
              displayName: appState.displayName,
              email: appState.email,
              age: appState.age,
              sex: '0',
            ),
          ),
        ),
      ],
    );
  }
}

class _ChoiceButton extends StatelessWidget {
  const _ChoiceButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(vertical: 13, horizontal: 14),
        decoration: BoxDecoration(
          color: selected
              ? aura.primarySoft
              : aura.surfaceStrong.withValues(alpha: 0.42),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: selected ? aura.borderStrong : aura.border),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(
                color: selected ? aura.primary : aura.textMuted,
                fontWeight: FontWeight.w700,
              ),
            ),
            Icon(
              selected ? Icons.radio_button_checked : Icons.radio_button_off,
              color: selected ? aura.primary : aura.textSoft,
              size: 18,
            ),
          ],
        ),
      ),
    );
  }
}

class _TermsRow extends StatelessWidget {
  const _TermsRow();

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AuraAppState>();
    final aura = context.aura;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Checkbox(
          value: appState.acceptedTerms,
          activeColor: aura.primary,
          checkColor: aura.onGradient,
          side: BorderSide(color: aura.borderStrong),
          onChanged: (value) =>
              context.read<AuraAppState>().setAcceptedTerms(value ?? false),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 11),
            child: Text.rich(
              TextSpan(
                text: '我已阅读并同意 ',
                children: [
                  TextSpan(
                    text: '服务条款',
                    style: TextStyle(color: aura.primary),
                  ),
                  const TextSpan(text: ' 与 '),
                  TextSpan(
                    text: '隐私政策',
                    style: TextStyle(color: aura.primary),
                  ),
                ],
              ),
              style: TextStyle(
                color: aura.textMuted,
                fontSize: 13,
                height: 1.5,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
