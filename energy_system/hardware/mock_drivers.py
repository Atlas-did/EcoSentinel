# 传感器数据驱动桩（仿真代替）
class MockSensorDriver:
    def __init__(self, mode="simulation"):
        self.mode = mode
        self.is_simulation = True
        
    def read_temperature(self):
        return 20.0
        
    def read_humidity(self):
        return 50.0
        
    def read_illuminance(self):
        return 300.0

class MockRelayDriver:
    def __init__(self, mode="simulation"):
        self.mode = mode
        self.is_simulation = True
        
    def set_ac_state(self, is_on, mode):
        pass
        
    def set_light_state(self, level):
        pass
