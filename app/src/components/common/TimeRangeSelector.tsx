import { motion } from 'framer-motion';
import type { TimeRange } from '@/types';

interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

const ranges: { label: string; value: TimeRange }[] = [
  { label: '5分钟', value: '5m' },
  { label: '1小时', value: '1h' },
  { label: '24小时', value: '24h' },
];

export default function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <div className="flex items-center gap-1 bg-slate-800/40 rounded-lg p-0.5 border border-slate-700/30">
      {ranges.map((range) => (
        <button
          key={range.value}
          onClick={() => onChange(range.value)}
          className={`relative px-3 py-1 text-[11px] font-mono rounded-md transition-all ${
            value === range.value
              ? 'text-cyan-400'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          {value === range.value && (
            <motion.div
              layoutId="timeRangeBg"
              className="absolute inset-0 bg-cyan-500/10 border border-cyan-500/20 rounded-md"
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
          )}
          <span className="relative z-10">{range.label}</span>
        </button>
      ))}
    </div>
  );
}
