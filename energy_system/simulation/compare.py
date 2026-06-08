from energy_system.simulation.simulator import Simulator
from energy_system.algorithms.energy_saving import calculate_savings

def run_compare():
    print("="*60)
    print(" Energy Model Full Simulation (3 days)")
    print(" dt=300s, TCI/EER metrics demo")
    print("="*60)
    
    sim_base = Simulator(mode="baseline")
    history_base = sim_base.run_simulation(days=3)
    
    sim_save = Simulator(mode="saving")
    history_save = sim_save.run_simulation(days=3)
    
    # 获取纯指标
    report = calculate_savings(history_base["total_kwh"], history_save["total_kwh"])
    
    avg_comfort_base = sum(history_base["comfort"]) / len(history_base["comfort"])
    avg_comfort_save = sum(history_save["comfort"]) / len(history_save["comfort"])
    
    print(f"[OK] Baseline 3-day energy:  {report['baseline_energy_kwh']:.2f} kWh")
    print(f"[OK] Saving 3-day energy:    {report['actual_energy_kwh']:.2f} kWh")
    print(f"[OK] Energy saved:           {report['energy_saved_kwh']:.2f} kWh")
    print(f"[>>] Saving rate:            {report['saving_rate_percent']:.1f}%")
    print(f"[>>] Carbon reduced:         {report['carbon_reduced_kg']:.2f} kgCO2")
    print(f"-"*30)
    print(f"Baseline avg comfort: {avg_comfort_base:.1%}")
    print(f"Saving avg comfort:   {avg_comfort_save:.1%}")
    print("="*60)

if __name__ == "__main__":
    run_compare()
