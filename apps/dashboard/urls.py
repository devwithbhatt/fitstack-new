from django.urls import path
from . import views

urlpatterns = [
    path('member-growth-chart-data/', views.member_growth_chart_data, name='member_growth_chart_data'),
]