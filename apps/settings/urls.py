from django.urls import path
from . import views

app_name = 'settings' 

urlpatterns = [
    path('general/', views.generalsetting.as_view(), name='general_settings'),
    path('payment/', views.PaymentSettingView.as_view(), name='payment_setting'),
    path('profile/', views.GymProfileView.as_view(), name='gym_profile'),
]