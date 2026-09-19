'use client';

/*
 * Bento Grid — adapted from 21st.dev (kokonutd/bento-grid).
 * Changes: dark-only styling in the site's palette, an amber glow on hover,
 * scroll-in animation per card, and tags rendered as a wrapping list.
 */
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

export interface BentoItem {
    title: string;
    description: string;
    icon: React.ReactNode;
    status?: string;
    tags?: string[];
    meta?: string;
    colSpan?: 1 | 2;
    hasPersistentHover?: boolean;
}

export function BentoGrid({ items }: { items: BentoItem[] }) {
    return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {items.map((item, index) => (
                <motion.div
                    key={item.title}
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-60px' }}
                    transition={{ duration: 0.5, delay: (index % 3) * 0.08, ease: 'easeOut' }}
                    className={cn(
                        'group relative overflow-hidden rounded-2xl p-5 transition-all duration-300',
                        'border border-white/[0.08] bg-white/[0.02]',
                        'hover:-translate-y-1 hover:border-amber-500/30 hover:shadow-[0_8px_30px_rgba(245,158,11,0.08)]',
                        item.colSpan === 2 && 'md:col-span-2',
                        item.hasPersistentHover && 'border-amber-500/25 shadow-[0_8px_30px_rgba(245,158,11,0.06)]',
                    )}
                >
                    <div
                        className={cn(
                            'absolute inset-0 transition-opacity duration-300',
                            item.hasPersistentHover ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
                        )}
                    >
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[length:4px_4px]" />
                    </div>

                    <div className="relative flex h-full flex-col gap-3">
                        <div className="flex items-center justify-between">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.06] transition-colors duration-300 group-hover:bg-amber-500/15">
                                {item.icon}
                            </div>
                            {item.status && (
                                <span className="rounded-lg bg-white/[0.06] px-2 py-1 text-xs font-medium text-slate-300 transition-colors duration-300 group-hover:bg-white/[0.1]">
                                    {item.status}
                                </span>
                            )}
                        </div>

                        <div className="space-y-2">
                            <h3 className="text-[15px] font-semibold tracking-tight text-white">
                                {item.title}
                                {item.meta && <span className="ml-2 text-xs font-normal text-slate-500">{item.meta}</span>}
                            </h3>
                            <p className="text-sm leading-relaxed text-slate-400">{item.description}</p>
                        </div>

                        {item.tags && (
                            <ul className="mt-auto flex flex-wrap gap-1.5 pt-2 text-xs text-slate-400">
                                {item.tags.map((tag) => (
                                    <li key={tag} className="rounded-md bg-white/[0.05] px-2 py-1 font-mono transition-colors duration-200 hover:bg-white/[0.1]">
                                        {tag}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </motion.div>
            ))}
        </div>
    );
}
