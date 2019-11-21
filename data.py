"""
    this module provides data-management interface
"""

import plotly.graph_objects as go
import plotly.io as pio
import config

class Graph:
    """
        class for drawing graphs from user data
    """
    def __init__(self, all_users, messages_count, images_count=None):
        self.all_users = all_users
        self.messages_count = messages_count
        self.images_count = images_count

        if config.ORCA_REMOTE:
            pio.orca.config.server_url = config.ORCA_URL

    @staticmethod
    def orca_draw(fig, to_path):
        """
            renders figure using either local or remote orca
            to PNG format (which is hardcoded currently)
        """
        if config.ORCA_REMOTE:
            with open(to_path, 'w+b') as to_f:
                # see to_image, it has more params
                to_f.write(pio.to_image(fig, format='png'))
        else:
            fig.write_image(to_path)


    def get_users_stat(self):
        fig = go.Figure([go.Bar(x=self.all_users, y=self.messages_count)])
        self.orca_draw(fig, 'images/fig1.png')

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
        self.orca_draw(fig, 'images/fig2.png')
