import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { motion } from 'framer-motion';
import {
  Play,
  Pause,
  RotateCcw,
  Settings,
  Sun,
  Thermometer,
  Zap,
  Brain,
  Shield,
  BarChart3,
} from 'lucide-react';
import SensorChart from '@/components/charts/SensorChart';
import type { SimulationParams } from '@/types';

export default function SimulationPage() {
  const { chartData, simulationParams, updateSimulationParams } = useAppStore();
  const [isRunning, setIsRunning] = useState(false);
  const [isRealData, setIsRealData] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const handleRunSimulation = () => {
    setIsRunning(!isRunning);
  };

  const handleParamChange = (key: keyof SimulationParams, value: number | boolean | string) => {
    updateSimulationParams({ [key]: value });
  };

  // Generate simulation preview data. Deterministic variation (index-based) so
  // the preview stays pure across re-renders instead of using Math.random().
  const simData = chartData.map((d, i) => ({
    ...d,
    outdoor_temp: (d.temp || 0) + 5 + (i % 4),
    solar_rad: Math.max(0, Math.sin(i * 0.7) * simulationParams.solar_radiation_max),
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
              <BarChart3 className="w-5 h-5 text-purple-400" />
              仿真中心
            </h1>
            <p className="text-xs text-slate-500 font-mono mt-1">
              Simulation Center - 规则与 AI 策略对比
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsRealData(!isRealData)}
              className={`px-3 py-1.5 text-xs font-mono rounded-lg border transition-all ${
                isRealData
                  ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                  : 'bg-slate-800/40 text-slate-400 border-slate-700/30'
              }`}
            >
              {isRealData ? '真实数据' : '仿真数据'}
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="px-3 py-1.5 text-xs font-mono bg-slate-800/40 text-slate-400 border border-slate-700/30 rounded-lg hover:text-slate-200 transition-colors flex items-center gap-1.5"
            >
              <Settings className="w-3.5 h-3.5" />
              参数
            </button>
          </div>
        </motion.div>

        {/* Control Bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 flex items-center justify-between"
        >
          <div className="flex items-center gap-6">
            {/* Days Slider */}
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-slate-500">仿真天数</span>
              <input
                type="range"
                min={1}
                max={30}
                value={simulationParams.days}
                onChange={(e) => handleParamChange('days', Number(e.target.value))}
                className="w-32 h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-cyan-500"
              />
              <span className="text-xs font-mono text-cyan-400 w-6">{simulationParams.days}</span>
            </div>

            <div className="h-8 w-px bg-slate-700/50" />

            {/* Toggles */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={simulationParams.enable_ai}
                onChange={(e) => handleParamChange('enable_ai', e.target.checked)}
                className="w-3.5 h-3.5 rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500/20"
              />
              <span className="text-xs font-mono text-slate-400 flex items-center gap-1">
                <Brain className="w-3 h-3" />
                AI 策略
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={simulationParams.enable_rules}
                onChange={(e) => handleParamChange('enable_rules', e.target.checked)}
                className="w-3.5 h-3.5 rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500/20"
              />
              <span className="text-xs font-mono text-slate-400 flex items-center gap-1">
                <Shield className="w-3 h-3" />
                规则策略
              </span>
            </label>
          </div>

          {/* Run Button */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsRunning(false)}
              className="px-3 py-1.5 text-xs font-mono bg-slate-800/40 text-slate-400 border border-slate-700/30 rounded-lg hover:text-slate-200 transition-colors flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              重置
            </button>
            <button
              onClick={handleRunSimulation}
              className={`px-5 py-1.5 text-xs font-mono rounded-lg border transition-all flex items-center gap-1.5 ${
                isRunning
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 hover:bg-amber-500/20'
                  : 'bg-purple-500/10 text-purple-400 border-purple-500/20 hover:bg-purple-500/20'
              }`}
            >
              {isRunning ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  暂停
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  运行仿真
                </>
              )}
            </button>
          </div>
        </motion.div>

        {/* Main Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest">
              室内外温度响应与功率曲线
            </h3>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-orange-400 rounded" />
                室内温度
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-blue-400 rounded" />
                室外温度
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-purple-400 rounded" />
                功率响应
              </span>
            </div>
          </div>
          <SensorChart
            data={simData}
            showTemp
            showHumidity={false}
            showPower
            height={400}
          />
        </motion.div>

        {/* Comparison Results */}
        <div className="grid grid-cols-3 gap-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <Thermometer className="w-4 h-4 text-orange-400" />
              <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider">温度控制</h3>
            </div>
            <div className="space-y-3">
              <p className="text-[10px] font-mono text-amber-400/70">
                ⚠️ **示意（非实测）**：本卡原有的"规则/AI 温度波动与精度提升"数字为界面演示文本，
                已按审计要求移除 —— 它们未接入任何实测或仿真结果，不做无来源的对比。
                真实温度表现见「能源分析」页；且本模型目前**无热惯性**（τ≈13.9s ≪ dt=300s，见 README）。
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-4 h-4 text-yellow-400" />
              <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider">能耗对比</h3>
            </div>
            <div className="space-y-3">
              <p className="text-[10px] font-mono text-amber-400/70">
                ⚠️ 本页对比卡为**固定示例值**（未接入实测）：只用于演示界面布局，
                不代表本系统的实测节能率；真实仿真结果见「能源分析」页（现行口径 17.6%，且建筑参数未标定）
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <Sun className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider">舒适度</h3>
            </div>
            <div className="space-y-3">
              <p className="text-[10px] font-mono text-amber-400/70">
                ⚠️ **示意（非实测）**：本卡原有的"规则/AI 舒适度评分与提升幅度"数字为界面演示文本，已按审计要求移除。
                真实舒适度请用 **IPMVP 原生口径**（时间在 [23,26]℃ 带内占比）：
                现行实测 **baseline 41.7% → saving 20.6%**（见 README 与 `docs/pmv-ppd-study.md`）——
                也就是说节能策略**并没有"提升舒适度"，反而减少了带内时间**。
              </p>
            </div>
          </motion.div>
        </div>

        {/* Settings Panel (collapsible) */}
        {showSettings && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
              <Settings className="w-3.5 h-3.5" />
              仿真参数
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-xs font-mono text-slate-500 block mb-1.5">
                  室外温度基数 (°C)
                </label>
                <input
                  type="number"
                  value={simulationParams.outdoor_temp_base}
                  onChange={(e) => handleParamChange('outdoor_temp_base', Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/50"
                />
              </div>
              <div>
                <label className="text-xs font-mono text-slate-500 block mb-1.5">
                  最大太阳辐射 (W/m²)
                </label>
                <input
                  type="number"
                  value={simulationParams.solar_radiation_max}
                  onChange={(e) => handleParamChange('solar_radiation_max', Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/50"
                />
              </div>
              <div>
                <label className="text-xs font-mono text-slate-500 block mb-1.5">
                  建筑隔热系数 (R值)
                </label>
                <input
                  type="number"
                  step={0.1}
                  value={simulationParams.building_insulation_r}
                  onChange={(e) => handleParamChange('building_insulation_r', Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/50"
                />
              </div>
              <div>
                <label className="text-xs font-mono text-slate-500 block mb-1.5">
                  HVAC 效率
                </label>
                <input
                  type="number"
                  step={0.05}
                  max={1}
                  min={0}
                  value={simulationParams.hvac_efficiency}
                  onChange={(e) => handleParamChange('hvac_efficiency', Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/50"
                />
              </div>
              <div>
                <label className="text-xs font-mono text-slate-500 block mb-1.5">
                   occupancy 时间表
                </label>
                <select
                  value={simulationParams.occupancy_schedule}
                  onChange={(e) => handleParamChange('occupancy_schedule', e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/50"
                >
                  <option value="9-18">工作日 9-18</option>
                  <option value="8-22">长时 8-22</option>
                  <option value="24h">全天 24h</option>
                </select>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
