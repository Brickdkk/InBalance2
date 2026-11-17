from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),

    # Vista de Usuario y Acciones en Vivo
    path('user-dashboard/', views.user_view, name='user_view'),
    path('user-dashboard/log-pomodoro/', views.log_pomodoro, name='log_pomodoro'),
    path('user-dashboard/redeem-reward/', views.redeem_reward, name='redeem_reward'),
    path('user-dashboard/update-risk/', views.update_my_risk, name='update_my_risk'),

    # Admin Panel & Mantenedor de Usuarios (CRUD)
    path('admin-dashboard/', views.admin_view, name='admin_view'),
    path('admin-dashboard/create-user/', views.create_user, name='create_user'),
    path('admin-dashboard/edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('admin-dashboard/delete-user/<int:user_id>/', views.delete_user, name='delete_user'),

    # Endpoints API para gráficos anidados y modales
    path('api/user-stats/<int:user_id>/', views.user_stats_api, name='user_stats_api'),
    path('api/month-activity/', views.month_activity_api, name='month_activity_api'),
    path('api/month-reward-detail/', views.month_reward_detail_api, name='month_reward_detail_api'),
    path('api/risk-detail/', views.risk_detail_api, name='risk_detail_api'),
    path('api/day-pomo-detail/', views.day_pomo_detail_api, name='day_pomo_detail_api'),

    # Autenticación
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]