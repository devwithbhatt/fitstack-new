from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('add_gym/', views.add_gym, name='add_gym'),
    path('', views.dashboard, name='dashboard'),
    path('gym_list', views.gym_list, name='gym_list'),
    path('update/<int:gym_id>/', views.update_gym, name='update_gym'),
    path('delete/<int:gym_id>/', views.delete_gym, name='delete_gym'),
    path('create_admin/<int:gym_id>/', views.create_gym_admin, name='create_gym_admin'),
    path('gym_profile/<int:gym_id>/', views.gym_profile, name='gym_profile'),
    path('gym_settings/<int:gym_id>/', views.update_gym_settings, name='update_gym_settings'),
    path('toggle_freeze/<int:gym_id>/', views.toggle_gym_freeze, name='toggle_gym_freeze'),
    path('toggle_whatsapp/<int:gym_id>/', views.toggle_whatsapp, name='toggle_whatsapp'),
    path('reset_admin_password/<int:admin_id>/', views.reset_admin_password, name='reset_admin_password'),
    path('subscription_plans/', views.subscription_plan_list, name='subscription_plan_list'),
    path('subscription_plans/add/', views.add_subscription_plan, name='add_subscription_plan'),
    path('subscription_plans/update/<int:plan_id>/', views.update_subscription_plan, name='update_subscription_plan'),
    path('subscription_plans/delete/<int:plan_id>/', views.delete_subscription_plan, name='delete_subscription_plan'),
    path('assign_subscription/', views.assign_subscription, name='assign_subscription'),
    path('billing_history/', views.billing_history, name='billing_history'),
    path('submit_due/', views.submit_due, name='submit_due'),
    path('get_due_amount/<int:gym_id>/', views.get_due_amount, name='get_due_amount'),
    path('invoice/<int:subscription_id>/', views.invoice_view, name='invoice'),
    path('website_contact_submissions/', views.website_contact_submissions, name='website_contact_submissions'),
    path('website_contact_submissions/mark_read/<int:submission_id>/', views.mark_submission_read, name='mark_read'),
    path('website_contact_submissions/delete/<int:submission_id>/', views.delete_submission, name='delete_submission'),
    path('delete_subscription/<int:subscription_id>/', views.delete_subscription, name='delete_subscription'),
    path('delete_payment/<int:payment_id>/', views.delete_payment, name='delete_payment'),
    path('billing_history/trash/', views.billing_trash, name='billing_trash'),
    path('billing_history/restore/<int:item_id>/<str:item_type>/', views.restore_billing, name='restore_billing'),
    path('billing_history/permanent_delete/<int:item_id>/<str:item_type>/', views.permanent_delete_billing, name='permanent_delete_billing'),
]