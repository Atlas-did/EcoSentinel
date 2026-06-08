import { motion } from 'framer-motion';

interface HardwarePortProps {
  label: string;
  active: boolean;
  subLabel?: string;
}

export default function HardwarePort({ label, active, subLabel }: HardwarePortProps) {
  return (
    <div className="relative flex flex-col items-center gap-1.5">
      <div className="relative w-10 h-10 rounded-full border border-slate-700 bg-slate-900 flex items-center justify-center shadow-[inset_0_2px_4px_rgba(0,0,0,0.5)]">
        <div
          className={`w-3 h-3 rounded-full border transition-colors duration-300 ${
            active
              ? 'bg-emerald-500 border-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]'
              : 'bg-slate-800 border-slate-600'
          }`}
        />
        {active && (
          <motion.div
            className="absolute inset-0 rounded-full border-t-2 border-r-2 border-emerald-400/60"
            animate={{ rotate: 360 }}
            transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
          />
        )}
      </div>
      <span className="text-[10px] font-mono text-slate-500 tracking-wider uppercase">
        {label}
      </span>
      {subLabel && (
        <span className="text-[9px] font-mono text-slate-600">{subLabel}</span>
      )}
    </div>
  );
}
