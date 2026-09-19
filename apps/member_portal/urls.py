from django.urls import path
from . import views

urlpatterns = [
    path('', views.member_dashboard, name='dashboard'),
    path('dashboard/', views.member_dashboard, name='dashboard_alias'),
    path('attendance/', views.member_attendance_view, name='attendance'),
    path('attendance/action/', views.member_attendance_action, name='attendance_action'),
    path('workout/', views.member_workout_view, name='workout_plan'),
    path('diet/', views.member_diet_view, name='diet_plan'),
    path('billing/', views.member_billing_view, name='billing'),
    path('personal-training/', views.member_pt_view, name='personal_training'),
    path('profile/', views.member_profile_view, name='profile'),
]
