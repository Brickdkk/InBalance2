from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    return render(request, 'index.html')

@login_required
def user_view(request):
    return render(request, 'user.html')

@login_required
def admin_view(request):
    return render(request, 'admin.html')