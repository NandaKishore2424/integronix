'use client';

/*
 * Small animation helpers for the public page. The page itself stays a server
 * component; only these wrappers ship JavaScript. MotionConfig honours the
 * visitor's "reduce motion" setting, so none of this moves for them.
 */
import { animate, motion, MotionConfig, useInView, useReducedMotion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';

export function MotionRoot({ children }: { children: React.ReactNode }) {
    return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/** Fades and lifts its children into place the first time they scroll into view. */
export function Reveal({
    children,
    delay = 0,
    className,
}: {
    children: React.ReactNode;
    delay?: number;
    className?: string;
}) {
    return (
        <motion.div
            className={className}
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.6, delay, ease: [0.21, 0.47, 0.32, 0.98] }}
        >
            {children}
        </motion.div>
    );
}

/** A list whose items appear one after another. */
export function StaggerList({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <motion.ol
            className={className}
            initial="hidden"
            whileInView="shown"
            viewport={{ once: true, margin: '-80px' }}
            variants={{ hidden: {}, shown: { transition: { staggerChildren: 0.07 } } }}
        >
            {children}
        </motion.ol>
    );
}

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <motion.li
            className={className}
            variants={{
                hidden: { opacity: 0, y: 18, scale: 0.97 },
                shown: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.45, ease: 'easeOut' } },
            }}
        >
            {children}
        </motion.li>
    );
}

/** Counts up to `value` once visible. Server-rendered with the final number, so it is never blank. */
export function CountUp({ value, className }: { value: number; className?: string }) {
    const ref = useRef<HTMLSpanElement>(null);
    const inView = useInView(ref, { once: true });
    const reduce = useReducedMotion();
    const [shown, setShown] = useState(value);

    useEffect(() => {
        if (!inView || reduce) return;
        const controls = animate(0, value, {
            duration: 1.6,
            ease: 'easeOut',
            onUpdate: (v) => setShown(Math.round(v)),
        });
        return () => controls.stop();
    }, [inView, reduce, value]);

    return (
        <span ref={ref} className={className}>
            {shown.toLocaleString('en-US')}
        </span>
    );
}

/** Staggered entrance for the hero copy. */
export function HeroStagger({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <motion.div
            className={className}
            initial="hidden"
            animate="shown"
            variants={{ hidden: {}, shown: { transition: { staggerChildren: 0.12, delayChildren: 0.1 } } }}
        >
            {children}
        </motion.div>
    );
}

export function HeroItem({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <motion.div
            className={className}
            variants={{
                hidden: { opacity: 0, y: 20, filter: 'blur(6px)' },
                shown: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.7, ease: 'easeOut' } },
            }}
        >
            {children}
        </motion.div>
    );
}
