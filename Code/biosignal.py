
import numpy as np

class BioSignalGenerator:
    def __init__(self):
        self.hr = np.random.uniform(60, 70)
        self.eda = 0.5

    def step(self, risk):
        self.hr += 0.2 * risk + np.random.normal(0, 0.05)
        self.eda += 0.3 * risk + np.random.normal(0, 0.02)
        hrv = max(20.0, 50.0 - 25.0 * risk + np.random.normal(0, 2))
        return {"HR": self.hr, "HRV": hrv, "EDA": self.eda}
