'use client';

import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: 'online' | 'blue' | 'gold' | 'error';
  children: React.ReactNode;
  className?: string;
}

export function StatusBadge({ status, children, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'status-badge',
        {
          'status-online': status === 'online',
          'status-blue': status === 'blue',
          'status-gold': status === 'gold',
          'status-error': status === 'error',
        },
        className
      )}
    >
      {children}
    </span>
  );
}
