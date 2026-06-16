import { fetchEventSource } from '@microsoft/fetch-event-source';

interface requestOptions {
    body?: BodyInit;
    headers?: Record<string, string>;
    onMessage?: (data: string) => void;
    onError?: (data: unknown) => void;
}

interface ConnectOptions {
    body?: BodyInit;
}

export function UseSse(url: string, options: requestOptions = {}) {
    const { headers, onMessage, onError } = options;
    let ctrl: AbortController | null = null;

    const connect = async (connectOptions?: ConnectOptions) => {
        // 连接前先清理旧连接，避免多个流同时写入同一段 UI。
        if (ctrl) {
            ctrl.abort();
        }

        ctrl = new AbortController();
        const currentCtrl = ctrl;

        try {
            await fetchEventSource(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...headers,
                },
                body: connectOptions?.body,
                signal: currentCtrl.signal,
                onmessage(ev) {
                    onMessage?.(ev.data);
                },
                onerror(err) {
                    throw err;
                },
                onclose() {
                    if (ctrl === currentCtrl) {
                        ctrl = null;
                    }
                },
            });
        } catch (err) {
            if (!currentCtrl.signal.aborted) {
                onError?.(err);
            }
        } finally {
            if (ctrl === currentCtrl) {
                ctrl = null;
            }
        }
    };

    const disconnect = () => {
        if (ctrl) {
            ctrl.abort();
            ctrl = null;
        }
    };

    return {
        connect,
        disconnect,
    };
}
