import { useEffect, useState } from 'react';
import { useAppStore, startAutoRefresh, stopAutoRefresh } from '@/store/useAppStore';
import { motion } from 'framer-motion';
import {
  Thermometer,
  Droplets,
  Sun,
  Wind,
  Zap,
  Activity,
  AlertTriangle,
} from 'lucide-react';
import SensorChart from '@/components/charts/SensorChart';
import TimeRangeSelector from '@/components/common/TimeRangeSelector';
import StatusBadge from '@/components/common/StatusBadge';
import type { TimeRange } from '@/types';

const sensorConfigs = [
  { key: 'temp', label: '温度', unit: '°C', icon: Thermometer, color: '#f97316', threshold: 30 },
  { key: 'humidity', label: '湿度', unit: '%', icon: Droplets, color: '#3b82f6', threshold: 80 },
  { key: 'illuminance', label: '光照', unit: 'lx', icon: Sun, color: '#eab308', threshold: 1000 },
  { key: 'eco2', label: 'eCO2', unit: 'ppm', icon: Wind, color: '#06b6d4', threshold: 1200 },
  { key: 'power_w', label: '功率', unit: 'W', icon: Zap, color: '#ef4444', threshold: 20 },
];

export default function RealtimePage() {
  const { chartData, latestSnapshot, selectedTimeRange, setTimeRange } = useAppStore();
  const [activeSensors, setActiveSensors] = useState<Record<string, boolean>>({
    temp: true,
    humidity: true,
    illuminance: true,
    eco2: false,
    power_w: true,
  });

  useEffect(() => {
    startAutoRefresh();
    return () => stopAutoRefresh();
  }, []);

  const toggleSensor = (key: string) => {
    setActiveSensors((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleTimeRangeChange = (range: TimeRange) => {
    setTimeRange(range);
  };

  const anomalies = chartData.filter((d) => {
    return (d.temp && d.temp > 30) || (d.eco2 && d.eco2 > 1000);
  });

  return (
    <div className="min-h-screen bg-[#020c1b] pt-16 pb-6">
      <div className="px-6 py-6 space-y-6">
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="text-xl font-bold text-slate-100 font-mono tracking-tight">
              实时曲线
            </h1>
            <p className="text-xs text-slate-500 font-mono mt-1">
              Real-time Sensor Monitoring
            </p>
          </div>
          <TimeRangeSelector value={selectedTimeRange} onChange={handleTimeRangeChange} />
        </motion.div>

        {/* Sensor Toggles */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex items-center gap-2"
        >
          <span className="text-xs font-mono text-slate-500 mr-2">传感器:</span>
          {sensorConfigs.map((sensor) => {
            const Icon = sensor.icon;
            const isActive = activeSensors[sensor.key];
            const currentValue = latestSnapshot?.[sensor.key as keyof typeof latestSnapshot] as number | undefined;
            const isAlert = currentValue && currentValue > sensor.threshold;

            return (
              <button
                key={sensor.key}
                onClick={() => toggleSensor(sensor.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all ${
                  isActive
                    ? 'bg-slate-800/60 border-slate-600/50 text-slate-200'
                    : 'bg-transparent border-slate-800 text-slate-600'
                }`}
              >
                <Icon className="w-3 h-3" style={{ color: isActive ? sensor.color : undefined }} />
                <span>{sensor.label}</span>
                {currentValue !== undefined && (
                  <span className={`ml-1 ${isAlert ? 'text-red-400' : 'text-slate-400'}`}>
                    {currentValue.toFixed(1)}{sensor.unit}
                  </span>
                )}
                {isAlert && <AlertTriangle className="w-3 h-3 text-red-400" />}
              </button>
            );
          })}
        </motion.div>

        {/* Main Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-cyan-400" />
              多传感器联动图
            </h3>
            {anomalies.length > 0 && (
              <StatusBadge label={`${anomalies.length} 异常点`} status="warning" />
            )}
          </div>
          <SensorChart
            data={chartData}
            showTemp={activeSensors.temp}
            showHumidity={activeSensors.humidity}
            showIlluminance={activeSensors.illuminance}
            showEco2={activeSensors.eco2}
            showPower={activeSensors.power_w}
            height={420}
          />
        </motion.div>

        {/* Bottom Stats */}
        <div className="grid grid-cols-5 gap-4">
          {sensorConfigs.map((sensor, i) => {
            const Icon = sensor.icon;
            const value = latestSnapshot?.[sensor.key as keyof typeof latestSnapshot] as number | undefined;
            const isAlert = value && value > sensor.threshold;

            return (
              <motion.div
                key={sensor.key}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + i * 0.05 }}
                className={`p-4 rounded-xl border ${
                  isAlert
                    ? 'border-red-500/20 bg-red-500/5'
                    : 'border-slate-800 bg-slate-900/40'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="w-4 h-4" style={{ color: sensor.color }} />
                  <span className="text-xs font-mono text-slate-500">{sensor.label}</span>
                </div>
                <div className="text-2xl font-bold text-slate-100 font-mono">
                  {value?.toFixed(1) ?? '--'}
                  <span className="text-xs text-slate-500 ml-1">{sensor.unit}</span>
                </div>
                <div className="mt-1 text-[10px] font-mono text-slate-600">
                  阈值: {sensor.threshold}{sensor.unit}
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Anomaly Events */}
        {anomalies.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/60 border border-red-500/20 rounded-2xl p-5"
          >
            <h3 className="text-red-400 text-xs font-mono uppercase tracking-widest flex items-center gap-2 mb-3">
              <AlertTriangle className="w-3.5 h-3.5" />
              异常事件 ({anomalies.length})
            </h3>
            <div className="space-y-2 max-h-32 overflow-y-auto">
              {anomalies.slice(-5).map((a, i) => (
                <div key={i} className="flex items-center gap-3 text-xs font-mono">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
                  <span className="text-slate-500">{a.time}</span>
                  {a.temp && a.temp > 30 && (
                    <span className="text-red-400">温度异常: {a.temp.toFixed(1)}°C</span>
                  )}
                  {a.eco2 && a.eco2 > 1000 && (
                    <span className="text-red-400">CO2超标: {a.eco2.toFixed(0)}ppm</span>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
