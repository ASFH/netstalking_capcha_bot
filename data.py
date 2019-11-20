from datetime import date, timedelta, datetime
import plotly.graph_objects as go

class Graph:
    def __init__(self, all_users, messages_count, images_count=None):
        self.all_users = all_users
        self.messages_count = messages_count
        self.images_count = images_count

    def get_users_stat(self):
        fig = go.Figure([go.Bar(x=self.all_users, y=self.messages_count)])
        fig.write_image("images/fig1.png")
    
    def get_images_stat(self):
        fig = go.Figure()
        fig.add_trace(go.Bar(x=self.all_users,
                        y=self.messages_count,
                        name='Messages',
                        marker_color='rgb(55, 83, 109)'
                        ))
        fig.add_trace(go.Bar(x=self.all_users,
                        y=self.images_count,
                        name='Images',
                        marker_color='rgb(26, 118, 255)'
                        ))
        fig.update_layout(
            barmode='group'
        )
        fig.write_image("images/fig2.png")