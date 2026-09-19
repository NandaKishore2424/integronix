import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge Tailwind classes, letting later ones win (the shadcn / 21st.dev convention). */
export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}
