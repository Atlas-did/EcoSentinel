import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { ChartDataPoint } from '@/types';
import { useId } from 'react';
import { METRICS } from '@/lib/metrics';
import type { TooltipProps } from 'recharts';

interface SensorChartProps {
  data: ChartDataPoint[];
  showTemp?: boolean;
  showHumidity?: boolean;
  showIlluminance?: boolean;
  showEco2?: boolean;
  showPower?: boolean;
  showSolar?: boolean;
  showBaseline?: boolean;
  showSaving?: boolean;
  /** true 时基准/节省系列绑定 `*_cum`（累计电量），而不是逐点功率（评审 P1：算完没人用） */
  cumulative?: boolean;
  showComfort?: boolean;
  height?: number;
}

const CustomTooltip = ({ active, payload, label }: TooltipProps<number, string>) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-lg shadow-2xl backdrop-blur-md">
        <p className="text-slate-400 text-[10px] font-mono mb-2 uppercase tracking-wider">
          {label}
        </p>
        {payload.map((entry, index: number) => (
          <p
            key={index}
            className="text-xs font-mono"
            style={{ color: entry.color }}
          >
            {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function SensorChart({
  data,
  showTemp = true,
  showHumidity = true,
  showIlluminance = false,
  showEco2 = false,
  showPower = false,
  showSolar = false,
  showBaseline = false,
  showSaving = false,
  cumulative = false,
  showComfort = false,
  height = 300,
}: SensorChartProps) {
  // 渐变颜色取自 '@/lib/metrics'（单一真值）。
  // id 加 useId() 前缀：固定 id（colorTemp…）在**同页两个图表实例**时会互相覆盖
  // （后渲染的 <linearGradient> 定义会遮蔽前一个，导致前一个图表填充色错乱）。
  // useId() 返回值含冒号（如 :r0:），在 CSS 选择器里不安全，去掉后用作前缀。
  const uid = useId().replace(/:/g, '');
  const gid = (suffix: string) => `${uid}-${suffix}`;
  const gradients = [
    { id: 'colorTemp', metric: 'temp', visible: showTemp, top: 0.3 },
    { id: 'colorHum', metric: 'humidity', visible: showHumidity, top: 0.3 },
    { id: 'colorPower', metric: 'power_w', visible: showPower, top: 0.3 },
    { id: 'colorSolar', metric: 'solar_power_w', visible: showSolar, top: 0.3 },
    { id: 'colorBaseline', metric: 'baseline_power', visible: showBaseline, top: 0.2 },
    { id: 'colorSaving', metric: 'saving_power', visible: showSaving, top: 0.3 },
    { id: 'colorComfort', metric: 'comfort_score', visible: showComfort, top: 0.3 },
  ] as const

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          {gradients
            .filter((g) => g.visible)
            .map((g) => (
              <linearGradient key={g.id} id={gid(g.id)} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={METRICS[g.metric].color} stopOpacity={g.top} />
                <stop offset="95%" stopColor={METRICS[g.metric].color} stopOpacity={0} />
              </linearGradient>
            ))}
        </defs>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="#1e293b"
          vertical={false}
        />
        <XAxis
          dataKey="time"
          stroke="#334155"
          tick={{ fill: '#475569', fontSize: 10, fontFamily: 'monospace' }}
          tickLine={false}
        />
        <YAxis
          stroke="#334155"
          tick={{ fill: '#475569', fontSize: 10, fontFamily: 'monospace' }}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 10, fontFamily: 'monospace' }}
          iconType="circle"
          iconSize={6}
        />

        {showTemp && (
          <Area
            type="monotone"
            dataKey="temp"
            name="温度°C"
            stroke={METRICS.temp.color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gid('colorTemp')})`}
          />
        )}
        {showHumidity && (
          <Area
            type="monotone"
            dataKey="humidity"
            name="湿度%"
            stroke={METRICS.humidity.color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gid('colorHum')})`}
          />
        )}
        {showIlluminance && (
          <Area
            type="monotone"
            dataKey="illuminance"
            name="光照lx"
            stroke={METRICS.illuminance.color}
            strokeWidth={1.5}
            fillOpacity={0}
          />
        )}
        {showEco2 && (
          <Area
            type="monotone"
            dataKey="eco2"
            name="eCO2ppm"
            stroke={METRICS.eco2.color}
            strokeWidth={1.5}
            fillOpacity={0}
          />
        )}
        {showPower && (
          <Area
            type="monotone"
            dataKey="power_w"
            name="功率W"
            stroke={METRICS.power_w.color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gid('colorPower')})`}
          />
        )}
        {showSolar && (
          <Area
            type="monotone"
            dataKey="solar_power_w"
            name="太阳能W"
            stroke={METRICS.solar_power_w.color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gid('colorSolar')})`}
          />
        )}
        {showBaseline && (
          <Area
            type="monotone"
            dataKey={cumulative ? 'baseline_cum' : 'baseline_power'}
            name={cumulative ? '基线累计电量' : '基线功率'}
            stroke={METRICS.baseline_power.color}
            strokeWidth={1.5}
            strokeDasharray="5 5"
            fillOpacity={1}
            fill={`url(#${gid('colorBaseline')})`}
          />
        )}
        {showSaving && (
          <Area
            type="monotone"
            dataKey={cumulative ? 'saving_cum' : 'saving_power'}
            name={cumulative ? '节能累计电量' : '节能功率'}
            stroke={METRICS.saving_power.color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gid('colorSaving')})`}
          />
        )}
        {showComfort && (
          <Area
            type="monotone"
            dataKey="comfort_score"
            name="舒适度"
            stroke={METRICS.comfort_score.color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gid('colorComfort')})`}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
