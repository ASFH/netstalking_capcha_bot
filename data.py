"""
    this module provides data-management interface
"""

import yaml
import plotly.graph_objects as go
import plotly.io as pio

config = yaml.safe_load('config.yaml')

class Graph:
    """
        class for drawing graphs from user data
    """
    def __init__(self, all_users, messages_count, images_count=None):
        self.all_users = all_users
        self.messages_count = messages_count
        self.images_count = images_count

        if config.get('graphs', {}).get('orca', {}).get('remote'):
            pio.orca.config.server_url = config['graphs']['orca'].get('url', 'http://localhost:9091/')

    @staticmethod
    def orca_draw(fig, to_path=None):
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


    def get_users_stat(self):
        fig = go.Figure([go.Bar(x=self.all_users, y=self.messages_count)])
        return self.orca_draw(fig)

    def get_images_stat(self):
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=self.all_users,
                y=self.messages_count,
                name='Messages',
                marker_color='rgb(55, 83, 109)'
            )
        )
        fig.add_trace(
            go.Bar(
                x=self.all_users,
                y=self.images_count,
                name='Images',
                marker_color='rgb(26, 118, 255)'
            )
        )
        fig.update_layout(barmode='group')
        return self.orca_draw(fig)
