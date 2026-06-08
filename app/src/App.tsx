import { Routes, Route } from 'react-router-dom';
import TopBar from '@/components/layout/TopBar';
import SideNav from '@/components/layout/SideNav';
import ToastContainer from '@/components/common/ToastContainer';
import DashboardPage from '@/pages/DashboardPage';
import RealtimePage from '@/pages/RealtimePage';
import AIDecisionPage from '@/pages/AIDecisionPage';
import EnergyAnalysisPage from '@/pages/EnergyAnalysisPage';
import HealthPage from '@/pages/HealthPage';
import SimulationPage from '@/pages/SimulationPage';
import { useAppStore } from '@/store/useAppStore';

function AppLayout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen } = useAppStore();

  return (
    <div className="min-h-screen bg-[#020c1b]">
      <TopBar />
      <SideNav />
      <main
        className={`transition-all duration-300 ${
          sidebarOpen ? 'pl-56' : 'pl-14'
        }`}
      >
        {children}
      </main>
      <ToastContainer />
    </div>
  );
}

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/realtime" element={<RealtimePage />} />
        <Route path="/ai" element={<AIDecisionPage />} />
        <Route path="/energy" element={<EnergyAnalysisPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/simulation" element={<SimulationPage />} />
      </Routes>
    </AppLayout>
  );
}
