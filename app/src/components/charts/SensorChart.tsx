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
  showComfort?: boolean;
  height?: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-lg shadow-2xl backdrop-blur-md">
        <p className="text-slate-400 text-[10px] font-mono mb-2 uppercase tracking-wider">
          {label}
        </p>
        {payload.map((entry: any, index: number) => (
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
  showComfort = false,
  height = 300,
}: SensorChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          {showTemp && (
            <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
            </linearGradient>
          )}
          {showHumidity && (
            <linearGradient id="colorHum" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          )}
          {showPower && (
            <linearGradient id="colorPower" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          )}
          {showSolar && (
            <linearGradient id="colorSolar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#eab308" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
            </linearGradient>
          )}
          {showBaseline && (
            <linearGradient id="colorBaseline" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#94a3b8" stopOpacity={0} />
            </linearGradient>
          )}
          {showSaving && (
            <linearGradient id="colorSaving" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          )}
          {showComfort && (
            <linearGradient id="colorComfort" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
            </linearGradient>
          )}
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
            stroke="#f97316"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorTemp)"
          />
        )}
        {showHumidity && (
          <Area
            type="monotone"
            dataKey="humidity"
            name="湿度%"
            stroke="#3b82f6"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorHum)"
          />
        )}
        {showIlluminance && (
          <Area
            type="monotone"
            dataKey="illuminance"
            name="光照lx"
            stroke="#eab308"
            strokeWidth={1.5}
            fillOpacity={0}
          />
        )}
        {showEco2 && (
          <Area
            type="monotone"
            dataKey="eco2"
            name="eCO2ppm"
            stroke="#06b6d4"
            strokeWidth={1.5}
            fillOpacity={0}
          />
        )}
        {showPower && (
          <Area
            type="monotone"
            dataKey="power_w"
            name="功率W"
            stroke="#ef4444"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorPower)"
          />
        )}
        {showSolar && (
          <Area
            type="monotone"
            dataKey="solar_power_w"
            name="太阳能W"
            stroke="#eab308"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorSolar)"
          />
        )}
        {showBaseline && (
          <Area
            type="monotone"
            dataKey="baseline_power"
            name="基线功率"
            stroke="#94a3b8"
            strokeWidth={1.5}
            strokeDasharray="5 5"
            fillOpacity={1}
            fill="url(#colorBaseline)"
          />
        )}
        {showSaving && (
          <Area
            type="monotone"
            dataKey="saving_power"
            name="节能功率"
            stroke="#10b981"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorSaving)"
          />
        )}
        {showComfort && (
          <Area
            type="monotone"
            dataKey="comfort_score"
            name="舒适度"
            stroke="#8b5cf6"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorComfort)"
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
