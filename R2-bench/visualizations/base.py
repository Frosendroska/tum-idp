"""
Base classes for plot visualization.
"""

import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BasePlotter:
    """Base class for all plotters with common functionality."""
    
    def __init__(self, data: pd.DataFrame, output_dir: str):
        self.data = data
        self.output_dir = output_dir
    
    def filter_successful_requests(self):
        """Filter data to only include successful requests."""
        if self.data is None or len(self.data) == 0:
            return None
        return self.data[self.data['http_status'] == 200]
    
    def get_unique_phases(self):
        """Get unique phase IDs from data."""
        if self.data is None or len(self.data) == 0:
            return []
        return self.data['phase_id'].unique()
    
    def get_phase_colors(self):
        """Generate color map for phases."""
        import matplotlib.pyplot as plt
        phases = self.get_unique_phases()
        phase_colors = plt.cm.Set1(range(len(phases)))
        return dict(zip(phases, phase_colors))

