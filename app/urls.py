from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('user-dashboard/', views.user_view, name='user_view'),
    path('admin-dashboard/', views.admin_view, name='admin_view'),
    path('admin-dashboard/delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    
    # API endpoints for interactive modals
    path('api/user-stats/<int:user_id>/', views.user_stats_api, name='user_stats_api'),
    path('api/month-activity/', views.month_activity_api, name='month_activity_api'),

    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]