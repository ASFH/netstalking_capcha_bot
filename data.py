"""
    this module provides data-management interface
"""

import plotly.graph_objects as go
import plotly.io as pio

from config import config

class Graph:
    """
        class for drawing graphs from user data
    """
    def __init__(self, users, counts):
        self.users = users
        self.counts = counts

        if config['graphs']['orca']['remote']:
            pio.orca.config.server_url = config['graphs']['orca']['url']

    @staticmethod
    def _orca_draw(fig, to_path=None):
        """
            renders figure using either local or remote orca
            to PNG format (which is hardcoded currently)
            returns image as bytes
        """
        image_bytes = pio.to_image(fig, format='png')
        if to_path:
            with open(to_path, 'w+b') as to_f:
                # see to_image, it has more params
                to_f.write(image_bytes)
        return image_bytes

    def get_stats(self):
        """
            draws simple bar diagram
        """
        fig = go.Figure([go.Bar(x=self.users, y=self.counts)])
        return self._orca_draw(fig)
