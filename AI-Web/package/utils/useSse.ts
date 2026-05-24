interface requestOptions {
    body?: BodyInit;
    headers?: Record<string, string>;
    onMessage?:(data:string)=>void;
    onError?:(data:string)=>void
}
interface ConnectOptions {
    body?: BodyInit;
}
import { fetchEventSource } from '@microsoft/fetch-event-source';

function useSse(url: string, options: requestOptions = {}) {
    const {headers,onMessage,onError } = options;
    let ctrl: AbortController | null = null; 
    // 连接
    const connect = async (connectOptions?: ConnectOptions) => {
        // 如果有旧连接则清除
        if (ctrl) {
            ctrl.abort();
        }
        ctrl = new AbortController();
        fetchEventSource(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...headers
            },
            body:connectOptions?.body,
            signal: ctrl.signal,
            onmessage(ev){
                onMessage?.(ev.data)
            },
            onerror(err) {
                onError?.(err)
                throw err
            },
        });
    };
    // 断开
    const disconnect = ()=>{
        if (ctrl) {
            ctrl.abort();
            ctrl = null;
        }
    }
    return {
        connect,
        disconnect
    }
}

export default useSse;
