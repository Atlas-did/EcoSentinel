import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { motion } from 'framer-motion';
import {
  Zap,
  TrendingDown,
  Leaf,
  Coins,
  BarChart3,
  Clock,
  Download,
} from 'lucide-react';
import SensorChart from '@/components/charts/SensorChart';
import { treesEquivalent } from '@/lib/format';

type Period = 'day' | 'week' | 'month';

export default function EnergyAnalysisPage() {
  const { chartData, energySummary } = useAppStore();
  const [period, setPeriod] = useState<Period>('day');

  const periods: { label: string; value: Period }[] = [
    { label: '日', value: 'day' },
    { label: '周', value: 'week' },
    { label: '月', value: 'month' },
  ];

  // Generate cumulative data
  const cumulativeData = chartData.map((d, i) => ({
    ...d,
    baseline_cum: chartData.slice(0, i + 1).reduce((acc, p) => acc + (p.baseline_power || 0) * 0.0167, 0),
    saving_cum: chartData.slice(0, i + 1).reduce((acc, p) => acc + (p.saving_power || 0) * 0.0167, 0),
  }));

  return (
    <div className="min-h-screen bg-[#020c1b] pt-16 pb-6">
      <div className="px-6 py-6 space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="text-xl font-bold text-slate-100 font-mono tracking-tight flex items-center gap-2">
              <Zap className="w-5 h-5 text-emerald-400" />
              能耗分析
            </h1>
            <p className="text-xs text-slate-500 font-mono mt-1">
              Energy Analysis - Baseline vs Saving Comparison
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-slate-800/40 rounded-lg p-0.5 border border-slate-700/30">
              {periods.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPeriod(p.value)}
                  className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                    period === p.value
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-slate-800/40 text-slate-400 border border-slate-700/30 rounded-lg hover:text-slate-200 transition-colors">
              <Download className="w-3.5 h-3.5" />
              导出报告
            </button>
          </div>
        </motion.div>

        {/* KPI Cards */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-4 gap-4"
        >
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-2 rounded-lg bg-slate-800/50">
                <BarChart3 className="w-4 h-4 text-slate-400" />
              </div>
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">基线能耗</span>
            </div>
            <div className="text-3xl font-bold text-slate-100 font-mono">
              {energySummary?.baseline_kwh.toFixed(1) ?? '--'}
              <span className="text-sm text-slate-500 ml-1">kWh</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-2 rounded-lg bg-emerald-500/10">
                <Zap className="w-4 h-4 text-emerald-400" />
              </div>
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">节能后能耗</span>
            </div>
            <div className="text-3xl font-bold text-emerald-400 font-mono">
              {energySummary?.saving_kwh.toFixed(1) ?? '--'}
              <span className="text-sm text-emerald-500/50 ml-1">kWh</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-2 rounded-lg bg-emerald-500/10">
                <TrendingDown className="w-4 h-4 text-emerald-400" />
              </div>
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">节能率</span>
            </div>
            <div className="text-3xl font-bold text-emerald-400 font-mono">
              {energySummary?.saving_rate.toFixed(1) ?? '--'}
              <span className="text-sm text-emerald-500/50 ml-1">%</span>
            </div>
            <div className="mt-2 h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-emerald-400"
                initial={{ width: 0 }}
                animate={{ width: `${energySummary?.saving_rate ?? 0}%` }}
                transition={{ duration: 1, delay: 0.3 }}
              />
            </div>
          </div>

          <div className="p-5 rounded-xl border border-cyan-500/20 bg-cyan-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-2 rounded-lg bg-cyan-500/10">
                <Coins className="w-4 h-4 text-cyan-400" />
              </div>
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">节省电费</span>
            </div>
            <div className="text-3xl font-bold text-cyan-400 font-mono">
              ¥{energySummary?.cost_saved_cny.toFixed(1) ?? '--'}
            </div>
          </div>
        </motion.div>

        {/* Baseline vs Saving Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              Baseline vs Saving 功率对比
            </h3>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-slate-400 rounded" />
                基线
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-emerald-400 rounded" />
                节能
              </span>
            </div>
          </div>
          <SensorChart
            data={chartData}
            showBaseline
            showSaving
            height={360}
          />
        </motion.div>

        {/* Cumulative Energy + Carbon Reduction */}
        <div className="grid grid-cols-2 gap-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest mb-4">
              累计能耗曲线
            </h3>
            <SensorChart
              data={cumulativeData}
              showTemp={false}
              showHumidity={false}
              showBaseline
              showSaving
              height={260}
            />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
              <Leaf className="w-3.5 h-3.5 text-emerald-400" />
              减碳贡献
            </h3>
            <div className="flex flex-col items-center justify-center h-[260px]">
              <div className="relative w-40 h-40">
                <svg className="w-full h-full -rotate-90">
                  <circle cx="50%" cy="50%" r="42%" fill="none" stroke="#1e293b" strokeWidth="12" />
                  <motion.circle
                    cx="50%" cy="50%" r="42%"
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="12"
                    strokeLinecap="round"
                    strokeDasharray={`${(energySummary?.saving_rate ?? 0) / 100 * 264}, 264`}
                    initial={{ strokeDashoffset: 264 }}
                    animate={{ strokeDashoffset: 0 }}
                    transition={{ duration: 1.5, delay: 0.3 }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <Leaf className="w-6 h-6 text-emerald-400 mb-1" />
                  <span className="text-2xl font-bold text-emerald-400 font-mono">
                    {energySummary?.carbon_reduced_kg.toFixed(1) ?? '--'}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">kg CO2</span>
                </div>
              </div>
              <p className="text-xs font-mono text-slate-500 mt-4 text-center">
                相当于种植了 {treesEquivalent(energySummary?.carbon_reduced_kg).toFixed(1)} 棵树的年碳吸收量
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
