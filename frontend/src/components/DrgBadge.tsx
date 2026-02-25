'use client';

import { DrgFlag } from '@/types/coding';
import { AlertTriangle, ShieldAlert, TrendingDown } from 'lucide-react';

interface Props { flag: DrgFlag }

const DRG_CONFIG = {
    MCC_MISSED: {
        icon: ShieldAlert,
        label: 'Severity Level Underdocumented',
        detail: 'Documentation supports a higher severity classification. Correcting this code may qualify for a higher reimbursement tier.',
        color: 'text-danger-light',
        border: 'border-danger/25',
        bg: 'bg-danger/10',
        dot: 'bg-danger',
    },
    CC_MISSED: {
        icon: AlertTriangle,
        label: 'Complication Not Captured',
        detail: 'A documented complication or comorbidity was not reflected in the submitted code. Review for potential claim reclassification.',
        color: 'text-warning',
        border: 'border-warning/25',
        bg: 'bg-warning/10',
        dot: 'bg-warning',
    },
    MCC_OVERCODED: {
        icon: TrendingDown,
        label: 'Severity Level Overstated',
        detail: 'The submitted code reflects a higher severity than the clinical documentation supports. This presents a compliance risk.',
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
                <p className={`text-sm font-bold ${cfg.color}`}>Billing Alert: {cfg.label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{cfg.detail}</p>
            </div>
        </div>
    );
}
