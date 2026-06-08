import { motion } from 'framer-motion';

interface StatusBadgeProps {
  label: string;
  status: 'online' | 'offline' | 'warning' | 'error' | 'processing';
  pulse?: boolean;
}

const statusConfig = {
  online: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', dot: 'bg-emerald-400' },
  offline: { bg: 'bg-slate-500/10', text: 'text-slate-400', border: 'border-slate-500/20', dot: 'bg-slate-400' },
  warning: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', dot: 'bg-amber-400' },
  error: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', dot: 'bg-red-400' },
  processing: { bg: 'bg-cyan-500/10', text: 'text-cyan-400', border: 'border-cyan-500/20', dot: 'bg-cyan-400' },
};

export default function StatusBadge({ label, status, pulse = false }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border ${config.bg} ${config.border}`}>
      <motion.div
        className={`w-1.5 h-1.5 rounded-full ${config.dot}`}
        animate={pulse ? { opacity: [1, 0.4, 1] } : {}}
        transition={{ duration: 2, repeat: Infinity }}
      />
      <span className={`text-[10px] font-mono ${config.text} uppercase tracking-wider`}>
        {label}
      </span>
    </div>
  );
}
