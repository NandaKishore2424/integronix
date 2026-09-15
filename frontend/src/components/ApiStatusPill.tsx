'use client';

import { useEffect, useState } from 'react';
import { fetchApiHealth, type ApiHealth } from '@/lib/api';

type PillState = ApiHealth | 'checking';

const STYLES: Record<PillState, { dot: string; text: string; label: string }> = {
    checking: { dot: 'bg-slate-500', text: 'text-slate-400', label: 'Checking API…' },
    online: { dot: 'bg-emerald-400', text: 'text-emerald-400', label: 'API online' },
    degraded: { dot: 'bg-amber-400', text: 'text-amber-400', label: 'API degraded' },
    offline: { dot: 'bg-red-400', text: 'text-red-400', label: 'API unreachable' },
};

/**
 * Live backend status, read from the public readiness probe.
 *
 * This replaced a hard-coded, always-green "System Online" badge. An indicator
 * that cannot turn red is worse than none: it reassures exactly when something
 * is wrong.
 */
export default function ApiStatusPill() {
    const [state, setState] = useState<PillState>('checking');

    useEffect(() => {
        let cancelled = false;
        const check = () =>
            fetchApiHealth().then((next) => {
                if (!cancelled) setState(next);
            });
        check();
        const timer = setInterval(check, 30_000);
        return () => {
            cancelled = true;
            clearInterval(timer);
        };
    }, []);

    const style = STYLES[state];
    return (
        <div role="status" aria-live="polite" className={`ml-auto flex items-center gap-1.5 text-xs font-medium ${style.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${style.dot} ${state === 'online' ? 'animate-pulse' : ''}`} />
            {style.label}
        </div>
    );
}
