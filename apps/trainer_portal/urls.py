from django.urls import path
from . import views

urlpatterns = [
    path('', views.trainer_dashboard, name='dashboard'),
    path('dashboard/', views.trainer_dashboard, name='dashboard_alias'),
    path('clients/', views.trainer_clients_view, name='clients'),
    path('personal-training/', views.trainer_pt_view, name='personal_training'),
    path('client/<int:member_id>/', views.trainer_client_detail_view, name='client_detail'),
    path('attendance/', views.trainer_attendance_view, name='attendance'),
    path('attendance/action/', views.trainer_attendance_action, name='attendance_action'),
    path('profile/', views.trainer_profile_view, name='profile'),
]
