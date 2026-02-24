'use client';

import { DrgFlag } from '@/types/coding';
import { AlertTriangle, ShieldAlert, TrendingDown } from 'lucide-react';

interface Props { flag: DrgFlag }

const DRG_CONFIG = {
    MCC_MISSED: {
        icon: ShieldAlert,
        label: 'MCC Missed',
        detail: 'Human coder missed a Major Complication/Comorbidity. This triggers a DRG weight downgrade — significant revenue impact.',
        color: 'text-danger-light',
        border: 'border-danger/25',
        bg: 'bg-danger/10',
        dot: 'bg-danger',
    },
    CC_MISSED: {
        icon: AlertTriangle,
        label: 'CC Missed',
        detail: 'Human coder missed a Complication/Comorbidity. DRG downgrade risk — review for potential DRG reclassification.',
        color: 'text-warning',
        border: 'border-warning/25',
        bg: 'bg-warning/10',
        dot: 'bg-warning',
    },
    MCC_OVERCODED: {
        icon: TrendingDown,
        label: 'MCC Overcoded',
        detail: 'Human coded a Major Complication/Comorbidity not supported by clinical documentation. Compliance risk.',
        color: 'text-orange-400',
        border: 'border-orange-500/25',
        bg: 'bg-orange-500/10',
        dot: 'bg-orange-400',
    },
};

export default function DrgBadge({ flag }: Props) {
    if (!flag || !(flag in DRG_CONFIG)) return null;

    const cfg = DRG_CONFIG[flag as keyof typeof DRG_CONFIG];
    const Icon = cfg.icon;

    return (
        <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${cfg.bg} ${cfg.border}`}>
            <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${cfg.dot} animate-pulse`} />
            <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.color}`} />
            <div>
                <p className={`text-sm font-bold ${cfg.color}`}>DRG Alert: {cfg.label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{cfg.detail}</p>
            </div>
        </div>
    );
}
