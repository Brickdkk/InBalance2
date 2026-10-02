

from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('admin-dashboard/', views.admin_view, name='admin_view'),
    path('user-dashboard/', views.user_view, name='user_view'),
]