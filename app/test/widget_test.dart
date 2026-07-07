import 'package:aifrd_app/features/app/application/aura_app_state.dart';
import 'package:aifrd_app/main.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('Arua auth screen can enter the chat shell', (tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AuraAppState(),
        child: const AuraApp(),
      ),
    );

    expect(find.text('Arua'), findsOneWidget);
    expect(find.text('立即登录'), findsOneWidget);

    await tester.tap(find.text('立即登录'));
    await tester.pumpAndSettle();

    expect(find.text('对话'), findsOneWidget);
    expect(find.text('记忆'), findsOneWidget);
    expect(find.text('设置'), findsOneWidget);
    expect(find.text('给 Arua 发消息...'), findsOneWidget);
  });
}
