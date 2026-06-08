import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: ReactNode;
  status?: 'normal' | 'success' | 'warning' | 'error' | 'unknown';
  subtitle?: string;
  trend?: 'up' | 'down' | 'neutral';
  delay?: number;
}

const statusColors = {
  normal: 'border-cyan-500/20 bg-cyan-500/5',
  success: 'border-emerald-500/20 bg-emerald-500/5',
  warning: 'border-amber-500/20 bg-amber-500/5',
  error: 'border-red-500/20 bg-red-500/5',
  unknown: 'border-slate-500/20 bg-slate-500/5',
};

const statusDotColors = {
  normal: 'bg-cyan-400',
  success: 'bg-emerald-400',
  warning: 'bg-amber-400',
  error: 'bg-red-400',
  unknown: 'bg-slate-400',
};

export default function MetricCard({
  title,
  value,
  unit,
  icon,
  status = 'normal',
  subtitle,
  trend,
  delay = 0,
}: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className={`relative p-5 rounded-xl border ${statusColors[status]} backdrop-blur-sm hover:border-opacity-40 transition-all group`}
    >
      {/* Status dot */}
      <div
        className={`absolute top-3 right-3 w-2 h-2 rounded-full ${statusDotColors[status]} ${status === 'normal' || status === 'success' ? 'animate-pulse' : ''}`}
      />

      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-slate-800/50 text-slate-400 group-hover:text-cyan-400 transition-colors">
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-1">
            {title}
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-slate-100 font-mono tracking-tight">
              {typeof value === 'number' ? value.toFixed(1) : value}
            </span>
            {unit && (
              <span className="text-xs text-slate-500 font-mono">{unit}</span>
            )}
          </div>
          {subtitle && (
            <div className="flex items-center gap-1 mt-1">
              {trend === 'up' && (
                <span className="text-emerald-400 text-xs">↑</span>
              )}
              {trend === 'down' && (
                <span className="text-red-400 text-xs">↓</span>
              )}
              <span className="text-xs text-slate-500">{subtitle}</span>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
