import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum
from .models import Profile, PomodoroSession, RewardRedemption

def is_admin(user):
    return user.is_authenticated and user.is_staff

@login_required
def index(request):
    return render(request, 'index.html')

@login_required
def user_view(request):
    return render(request, 'user.html')

@user_passes_test(is_admin, login_url='login')
def admin_view(request):
    users = User.objects.select_related('profile').order_by('-date_joined')
    total_users = users.count()

    # 1. Risk Distribution
    risk_low = Profile.objects.filter(risk_level='low').count()
    risk_med = Profile.objects.filter(risk_level='medium').count()
    risk_high = Profile.objects.filter(risk_level='high').count()

    # 2. Pomodoros in the last 7 days
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)
    recent_pomos = PomodoroSession.objects.filter(completed_at__date__gte=seven_days_ago)

    pomo_counts_by_day = [0] * 7  # [Lun, Mar, Mié, Jue, Vie, Sáb, Dom]
    for session in recent_pomos:
        day_index = session.completed_at.weekday()
        pomo_counts_by_day[day_index] += 1

    total_pomodoros = PomodoroSession.objects.count()

    # 3. Rewards Redemptions
    rewards_data = [
        RewardRedemption.objects.filter(reward_type='pausas').count(),
        RewardRedemption.objects.filter(reward_type='apuntes').count(),
        RewardRedemption.objects.filter(reward_type='puntos').count(),
        RewardRedemption.objects.filter(reward_type='libre').count(),
    ]
    total_rewards = sum(rewards_data)

    # 4. User Growth by Month (Past 6 months cumulative with year/month tokens)
    growth_labels = []
    growth_counts = []
    month_tokens = []  # format: 'YYYY-MM'
    current_month = today.month
    current_year = today.year

    for i in range(5, -1, -1):
        target_month = current_month - i
        target_year = current_year
        while target_month <= 0:
            target_month += 12
            target_year -= 1

        month_names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        growth_labels.append(month_names[target_month - 1])
        month_tokens.append(f"{target_year}-{target_month:02d}")

        if target_month == 12:
            cutoff_date = timezone.datetime(target_year + 1, 1, 1, tzinfo=timezone.UTC)
        else:
            cutoff_date = timezone.datetime(target_year, target_month + 1, 1, tzinfo=timezone.UTC)

        count = User.objects.filter(date_joined__lt=cutoff_date).count()
        growth_counts.append(count)

    context = {
        'users': users,
        'total_users': total_users,
        'risk_high': risk_high,
        'risk_med': risk_med,
        'risk_low': risk_low,
        'total_pomodoros': total_pomodoros,
        'total_rewards': total_rewards,
        'growth_labels_json': json.dumps(growth_labels),
        'growth_data_json': json.dumps(growth_counts),
        'month_tokens_json': json.dumps(month_tokens),
        'pomos_data_json': json.dumps(pomo_counts_by_day),
        'rewards_data_json': json.dumps(rewards_data),
    }
    return render(request, 'admin.html', context)

# 5. API: Specific User Statistics from Database
@user_passes_test(is_admin)
def user_stats_api(request, user_id):
    target_user = get_object_or_404(User.objects.select_related('profile'), id=user_id)
    profile = getattr(target_user, 'profile', None)

    total_pomos = PomodoroSession.objects.filter(user=target_user).count()
    total_minutes = PomodoroSession.objects.filter(user=target_user).aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
    total_rewards = RewardRedemption.objects.filter(user=target_user).count()

    recent_sessions = list(
        PomodoroSession.objects.filter(user=target_user)
        .order_by('-completed_at')[:5]
        .values('completed_at', 'duration_minutes')
    )

    formatted_sessions = [
        {
            'date': s['completed_at'].strftime('%d/%m/%Y %H:%M'),
            'duration': s['duration_minutes']
        }
        for s in recent_sessions
    ]

    data = {
        'username': target_user.username,
        'email': target_user.email or 'Sin correo',
        'date_joined': target_user.date_joined.strftime('%d/%m/%Y %H:%M'),
        'role': 'Superadmin' if target_user.is_superuser else ('Staff Admin' if target_user.is_staff else 'Estudiante'),
        'risk_level': profile.risk_level if profile else 'low',
        'xp': profile.xp if profile else 0,
        'total_pomos': total_pomos,
        'study_hours': round(total_minutes / 60, 1),
        'total_rewards': total_rewards,
        'recent_sessions': formatted_sessions
    }
    return JsonResponse(data)

# 6. API: Monthly Activity Drilldown from Database
@user_passes_test(is_admin)
def month_activity_api(request):
    month_token = request.GET.get('token')  # 'YYYY-MM'
    month_label = request.GET.get('label', 'Mes')

    if not month_token:
        return JsonResponse({'error': 'Token missing'}, status=400)

    year, month = map(int, month_token.split('-'))

    # Query database for events matching this month and year
    new_users = User.objects.filter(date_joined__year=year, date_joined__month=month).count()
    total_pomos = PomodoroSession.objects.filter(completed_at__year=year, completed_at__month=month).count()
    total_rewards = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month).count()

    # Detailed reward split for this month
    reward_pausas = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='pausas').count()
    reward_apuntes = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='apuntes').count()
    reward_puntos = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='puntos').count()
    reward_libre = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='libre').count()

    data = {
        'month_label': f"{month_label} {year}",
        'new_users': new_users,
        'total_pomos': total_pomos,
        'total_rewards': total_rewards,
        'reward_breakdown': [reward_pausas, reward_apuntes, reward_puntos, reward_libre]
    }
    return JsonResponse(data)

# 7. Delete User Action
@user_passes_test(is_admin, login_url='login')
def delete_user(request, user_id):
    if request.method == 'POST':
        user_to_delete = get_object_or_404(User, id=user_id)
        if user_to_delete == request.user:
            messages.error(request, "No puedes eliminar tu propia cuenta de administrador.")
        else:
            username = user_to_delete.username
            user_to_delete.delete()
            messages.success(request, f"Usuario '{username}' eliminado correctamente de la base de datos.")
    return redirect('admin_view')