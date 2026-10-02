from django.shortcuts import render

def index(requests):
    return render(requests, 'index.html')

def admin_view(requests):
    return render(requests, 'admin.html')

def user_view(requests):
    return render(requests, 'user.html')