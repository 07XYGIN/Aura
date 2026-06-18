import { fetchEventSource } from '@microsoft/fetch-event-source';

interface RequestOptions {
    body?: BodyInit;
    headers?: Record<string, string>;
    onMessage?: (data: string) => void;
    onError?: (data: unknown) => void;
    onClose?: () => void;
}

interface ConnectOptions {
    body?: BodyInit;
}

export function UseSse(url: string, options: RequestOptions = {}) {
    const { headers, onMessage, onError, onClose } = options;
    let ctrl: AbortController | null = null;
    let connecting = false;

    const connect = async (connectOptions?: ConnectOptions) => {
        if (connecting || ctrl) {
            return false;
        }

        ctrl = new AbortController();
        connecting = true;
        const currentCtrl = ctrl;

        try {
            await fetchEventSource(url, {
                method: 'POST',
                openWhenHidden: true,
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
                    onClose?.();
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
            connecting = false;
            onClose?.();
        }

        return true;
    };

    const disconnect = () => {
        if (ctrl) {
            ctrl.abort();
            ctrl = null;
        }
        connecting = false;
    };

    const isConnected = () => Boolean(ctrl) || connecting;

    return {
        connect,
        disconnect,
        isConnected,
    };
}
