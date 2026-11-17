import json
from datetime import datetime, timezone as dt_timezone, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count
from .models import Profile, PomodoroSession, RewardRedemption

def is_admin(user):
    return user.is_authenticated and user.is_staff

@login_required
def index(request):
    return render(request, 'index.html')

# ==============================================================================
# VISTA DE USUARIO (DASHBOARD TAILWIND)
# ==============================================================================

@login_required
def user_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    sessions = PomodoroSession.objects.filter(user=request.user).order_by('-completed_at')
    redemptions = RewardRedemption.objects.filter(user=request.user).order_by('-redeemed_at')

    total_pomos = sessions.count()
    total_minutes = sessions.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
    study_hours = round(total_minutes / 60, 1)

    level = (profile.xp // 500) + 1
    next_level_xp = level * 500
    xp_progress_pct = min(100, round(((profile.xp % 500) / 500) * 100, 1))

    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_last_week = start_of_week - timedelta(days=7)

    this_week_hours = [0.0] * 7
    last_week_hours = [0.0] * 7

    for s in sessions.filter(completed_at__date__gte=start_of_last_week):
        s_date = s.completed_at.date()
        hrs = round(s.duration_minutes / 60, 2)
        if s_date >= start_of_week:
            this_week_hours[s_date.weekday()] = round(this_week_hours[s_date.weekday()] + hrs, 1)
        elif s_date >= start_of_last_week:
            last_week_hours[s_date.weekday()] = round(last_week_hours[s_date.weekday()] + hrs, 1)

    all_profiles = list(Profile.objects.select_related('user').order_by('-xp'))
    total_students = len(all_profiles)
    user_rank = 1
    for idx, p in enumerate(all_profiles, start=1):
        if p.user_id == request.user.id:
            user_rank = idx
            break

    leaderboard = []
    for idx, p in enumerate(all_profiles[:5], start=1):
        uname = p.user.username
        initials = uname[:2].upper() if len(uname) >= 2 else uname.upper()
        leaderboard.append({
            'rank': idx,
            'username': uname,
            'initials': initials,
            'xp': p.xp,
            'level': (p.xp // 500) + 1,
            'is_me': p.user_id == request.user.id,
        })

    rewards_catalog = [
        {'key': 'pausas', 'name': 'Pausas Activas', 'desc': '10 min extra de descanso guiado', 'cost': 50, 'icon': 'fa-mug-hot'},
        {'key': 'apuntes', 'name': 'Descarga de Apuntes', 'desc': 'Acceso a resúmenes verificados', 'cost': 100, 'icon': 'fa-file-lines'},
        {'key': 'puntos', 'name': 'Puntos Extra (+150 XP)', 'desc': 'Bonificación directa a tu perfil', 'cost': 80, 'icon': 'fa-bolt'},
        {'key': 'libre', 'name': 'Horario Libre', 'desc': 'Bloque flexible sin penalización', 'cost': 200, 'icon': 'fa-calendar-check'},
    ]

    username = request.user.username
    initials = username[:2].upper() if len(username) >= 2 else username.upper()

    context = {
        'profile': profile,
        'initials': initials,
        'level': level,
        'next_level_xp': next_level_xp,
        'xp_progress_pct': xp_progress_pct,
        'total_pomos': total_pomos,
        'study_hours': study_hours,
        'this_week_total': round(sum(this_week_hours), 1),
        'this_week_hours_json': json.dumps(this_week_hours),
        'last_week_hours_json': json.dumps(last_week_hours),
        'user_rank': user_rank,
        'total_students': total_students,
        'leaderboard': leaderboard,
        'recent_sessions': sessions[:6],
        'recent_redemptions': redemptions[:6],
        'rewards_catalog': rewards_catalog,
    }
    return render(request, 'user.html', context)

@login_required
def log_pomodoro(request):
    if request.method == 'POST':
        try:
            duration = int(request.POST.get('duration_minutes', 25))
        except ValueError:
            duration = 25

        duration = max(5, min(300, duration))
        earned_xp = duration * 2

        PomodoroSession.objects.create(
            user=request.user,
            duration_minutes=duration,
            completed_at=timezone.now()
        )

        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.xp += earned_xp
        profile.save()

        messages.success(request, f"¡Sesión de {duration} min guardada! Ganaste +{earned_xp} XP.")
    return redirect('user_view')

@login_required
def redeem_reward(request):
    if request.method == 'POST':
        reward_type = request.POST.get('reward_type', '')
        costs = {
            'pausas': 50,
            'apuntes': 100,
            'puntos': 80,
            'libre': 200,
        }

        if reward_type not in costs:
            messages.error(request, "Recompensa no válida.")
            return redirect('user_view')

        profile, _ = Profile.objects.get_or_create(user=request.user)
        cost = costs[reward_type]

        if profile.xp < cost:
            messages.error(request, f"XP insuficiente: necesitas {cost} XP y tienes {profile.xp} XP.")
            return redirect('user_view')

        profile.xp -= cost
        if reward_type == 'puntos':
            profile.xp += 150
        profile.save()

        redemption = RewardRedemption.objects.create(
            user=request.user,
            reward_type=reward_type,
            redeemed_at=timezone.now()
        )

        messages.success(request, f"¡Canjeaste '{redemption.get_reward_type_display()}' por {cost} XP!")
    return redirect('user_view')

@login_required
def update_my_risk(request):
    if request.method == 'POST':
        risk_level = request.POST.get('risk_level', 'low')
        if risk_level in ['low', 'medium', 'high']:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            profile.risk_level = risk_level
            profile.save()
            messages.success(request, "Estado de carga académica actualizado.")
    return redirect('user_view')

# ==============================================================================
# PANEL DE ADMINISTRADOR CON CROSS-FILTERING Y GRÁFICOS DE 3 NIVELES
# ==============================================================================

def _build_dashboard_metrics(users_qs, pomos_qs, rewards_qs, today):
    """Calcula métricas y series de los 4 gráficos sobre un conjunto filtrado."""
    total_users = users_qs.count()
    risk_low = Profile.objects.filter(user__in=users_qs, risk_level='low').count()
    risk_med = Profile.objects.filter(user__in=users_qs, risk_level='medium').count()
    risk_high = Profile.objects.filter(user__in=users_qs, risk_level='high').count()

    seven_days_ago = today - timedelta(days=6)
    recent_pomos = pomos_qs.filter(completed_at__date__gte=seven_days_ago)

    pomo_counts_by_day = [0] * 7
    for session in recent_pomos:
        pomo_counts_by_day[session.completed_at.weekday()] += 1

    total_pomodoros = pomos_qs.count()

    rewards_data = [
        rewards_qs.filter(reward_type='pausas').count(),
        rewards_qs.filter(reward_type='apuntes').count(),
        rewards_qs.filter(reward_type='puntos').count(),
        rewards_qs.filter(reward_type='libre').count(),
    ]
    total_rewards = sum(rewards_data)

    growth_labels = []
    growth_counts = []
    month_tokens = []
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
            cutoff_date = datetime(target_year + 1, 1, 1, tzinfo=dt_timezone.utc)
        else:
            cutoff_date = datetime(target_year, target_month + 1, 1, tzinfo=dt_timezone.utc)

        growth_counts.append(users_qs.filter(date_joined__lt=cutoff_date).count())

    return {
        'total_users': total_users,
        'risk_low': risk_low,
        'risk_med': risk_med,
        'risk_high': risk_high,
        'total_pomodoros': total_pomodoros,
        'total_rewards': total_rewards,
        'growth_labels': growth_labels,
        'growth_counts': growth_counts,
        'month_tokens': month_tokens,
        'pomo_counts_by_day': pomo_counts_by_day,
        'rewards_data': rewards_data,
    }

@user_passes_test(is_admin, login_url='login')
def admin_view(request):
    users = User.objects.select_related('profile').order_by('-date_joined')
    today = timezone.now().date()
    metrics = _build_dashboard_metrics(
        users,
        PomodoroSession.objects.all(),
        RewardRedemption.objects.all(),
        today
    )

    context = {
        'users': users,
        'total_users': metrics['total_users'],
        'risk_high': metrics['risk_high'],
        'risk_med': metrics['risk_med'],
        'risk_low': metrics['risk_low'],
        'total_pomodoros': metrics['total_pomodoros'],
        'total_rewards': metrics['total_rewards'],
        'growth_labels_json': json.dumps(metrics['growth_labels']),
        'growth_data_json': json.dumps(metrics['growth_counts']),
        'month_tokens_json': json.dumps(metrics['month_tokens']),
        'pomos_data_json': json.dumps(metrics['pomo_counts_by_day']),
        'rewards_data_json': json.dumps(metrics['rewards_data']),
    }
    return render(request, 'admin.html', context)

# API CROSS-FILTERING: Sincroniza todos los gráficos y KPIs según el filtro elegido
@user_passes_test(is_admin)
def cross_filter_api(request):
    filter_type = request.GET.get('type', 'all')
    filter_value = request.GET.get('value', '')
    today = timezone.now().date()

    users_qs = User.objects.all()
    pomos_qs = PomodoroSession.objects.all()
    rewards_qs = RewardRedemption.objects.all()
    badge_label = "Vista Global (Todos los datos)"

    if filter_type == 'risk' and filter_value in ['low', 'medium', 'high']:
        risk_names = {'low': 'Bajo Riesgo', 'medium': 'Riesgo Medio', 'high': 'Alto Riesgo'}
        users_qs = users_qs.filter(profile__risk_level=filter_value)
        pomos_qs = pomos_qs.filter(user__in=users_qs)
        rewards_qs = rewards_qs.filter(user__in=users_qs)
        badge_label = f"Segmento: {risk_names[filter_value]}"

    elif filter_type == 'reward' and filter_value in ['pausas', 'apuntes', 'puntos', 'libre']:
        reward_names = {
            'pausas': 'Pausas Activas',
            'apuntes': 'Descarga de Apuntes',
            'puntos': 'Puntos Extra',
            'libre': 'Horario Libre',
        }
        user_ids = RewardRedemption.objects.filter(reward_type=filter_value).values_list('user_id', flat=True).distinct()
        users_qs = users_qs.filter(id__in=user_ids)
        pomos_qs = pomos_qs.filter(user__in=users_qs)
        rewards_qs = rewards_qs.filter(user__in=users_qs)
        badge_label = f"Estudiantes que canjearon: {reward_names[filter_value]}"

    elif filter_type == 'day':
        try:
            day_idx = int(filter_value)
            day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            seven_days_ago = today - timedelta(days=6)
            matching_user_ids = [
                s.user_id for s in PomodoroSession.objects.filter(completed_at__date__gte=seven_days_ago)
                if s.completed_at.weekday() == day_idx
            ]
            users_qs = users_qs.filter(id__in=set(matching_user_ids))
            pomos_qs = pomos_qs.filter(user__in=users_qs)
            rewards_qs = rewards_qs.filter(user__in=users_qs)
            badge_label = f"Activos el día: {day_names[day_idx]}"
        except (ValueError, IndexError):
            pass

    metrics = _build_dashboard_metrics(users_qs, pomos_qs, rewards_qs, today)
    metrics['filter_label'] = badge_label
    return JsonResponse(metrics)

# ==============================================================================
# APIs PARA DRILLDOWN DE 3 NIVELES E INSPECCIÓN DE USUARIO
# ==============================================================================

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

    return JsonResponse({
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
    })

@user_passes_test(is_admin)
def month_activity_api(request):
    month_token = request.GET.get('token')
    month_label = request.GET.get('label', 'Mes')

    if not month_token:
        return JsonResponse({'error': 'Token faltante'}, status=400)

    year, month = map(int, month_token.split('-'))

    new_users = User.objects.filter(date_joined__year=year, date_joined__month=month).count()
    total_pomos = PomodoroSession.objects.filter(completed_at__year=year, completed_at__month=month).count()
    total_rewards = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month).count()

    reward_pausas = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='pausas').count()
    reward_apuntes = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='apuntes').count()
    reward_puntos = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='puntos').count()
    reward_libre = RewardRedemption.objects.filter(redeemed_at__year=year, redeemed_at__month=month, reward_type='libre').count()

    return JsonResponse({
        'token': month_token,
        'month_label': f"{month_label} {year}",
        'new_users': new_users,
        'total_pomos': total_pomos,
        'total_rewards': total_rewards,
        'reward_breakdown': [reward_pausas, reward_apuntes, reward_puntos, reward_libre]
    })

@user_passes_test(is_admin)
def month_reward_detail_api(request):
    month_token = request.GET.get('token')
    reward_index = int(request.GET.get('reward_index', 0))

    reward_keys = ['pausas', 'apuntes', 'puntos', 'libre']
    reward_names = ['Pausas Activas', 'Descarga de Apuntes', 'Puntos Extra', 'Horario Libre']

    if not month_token or reward_index not in range(4):
        return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    year, month = map(int, month_token.split('-'))
    selected_key = reward_keys[reward_index]
    selected_name = reward_names[reward_index]

    user_counts = (
        RewardRedemption.objects.filter(
            redeemed_at__year=year,
            redeemed_at__month=month,
            reward_type=selected_key
        )
        .values('user__username')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    labels = [item['user__username'] for item in user_counts]
    counts = [item['total'] for item in user_counts]

    return JsonResponse({
        'reward_name': selected_name,
        'month_token': month_token,
        'labels': labels,
        'counts': counts,
        'total_claims': sum(counts)
    })

@user_passes_test(is_admin)
def risk_detail_api(request):
    risk_index = int(request.GET.get('risk_index', 0))
    risk_keys = ['low', 'medium', 'high']
    risk_names = ['Bajo Riesgo', 'Riesgo Medio', 'Alto Riesgo']

    if risk_index not in range(3):
        return JsonResponse({'error': 'Índice inválido'}, status=400)

    key = risk_keys[risk_index]
    profiles = Profile.objects.select_related('user').filter(risk_level=key)

    labels = []
    pomo_counts = []
    total_xp = 0

    for p in profiles:
        labels.append(p.user.username)
        pomo_counts.append(PomodoroSession.objects.filter(user=p.user).count())
        total_xp += p.xp

    avg_xp = round(total_xp / profiles.count(), 1) if profiles.exists() else 0

    return JsonResponse({
        'risk_name': risk_names[risk_index],
        'risk_key': key,
        'user_count': profiles.count(),
        'avg_xp': avg_xp,
        'labels': labels,
        'pomo_counts': pomo_counts
    })

@user_passes_test(is_admin)
def day_pomo_detail_api(request):
    day_index = int(request.GET.get('day_index', 0))
    day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

    if day_index not in range(7):
        return JsonResponse({'error': 'Día inválido'}, status=400)

    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)
    recent_pomos = PomodoroSession.objects.filter(completed_at__date__gte=seven_days_ago)

    duration_buckets = {}
    total_minutes = 0
    count = 0

    for s in recent_pomos:
        if s.completed_at.weekday() == day_index:
            label = f"{s.duration_minutes} min"
            duration_buckets[label] = duration_buckets.get(label, 0) + 1
            total_minutes += s.duration_minutes
            count += 1

    sorted_labels = sorted(duration_buckets.keys(), key=lambda x: int(x.split()[0]))
    sorted_counts = [duration_buckets[k] for k in sorted_labels]

    return JsonResponse({
        'day_name': day_names[day_index],
        'total_sessions': count,
        'total_hours': round(total_minutes / 60, 1),
        'labels': sorted_labels,
        'counts': sorted_counts
    })

# ==============================================================================
# MANTENEDOR DE USUARIOS (CREATE, UPDATE, DELETE)
# ==============================================================================

@user_passes_test(is_admin, login_url='login')
def create_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        role = request.POST.get('role', 'student')
        risk_level = request.POST.get('risk_level', 'low')
        xp = int(request.POST.get('xp') or 0)

        if not username or not password:
            messages.error(request, "El nombre de usuario y la contraseña son obligatorios.")
            return redirect('admin_view')

        if User.objects.filter(username=username).exists():
            messages.error(request, f"El usuario '{username}' ya existe en la base de datos.")
            return redirect('admin_view')

        new_user = User.objects.create_user(username=username, email=email, password=password)

        if role == 'superuser':
            new_user.is_staff = True
            new_user.is_superuser = True
        elif role == 'staff':
            new_user.is_staff = True
            new_user.is_superuser = False
        else:
            new_user.is_staff = False
            new_user.is_superuser = False
        new_user.save()

        profile, _ = Profile.objects.get_or_create(user=new_user)
        profile.risk_level = risk_level
        profile.xp = max(0, xp)
        profile.save()

        messages.success(request, f"Cuenta '{username}' creada correctamente en la base de datos.")
    return redirect('admin_view')

@user_passes_test(is_admin, login_url='login')
def edit_user(request, user_id):
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        new_password = request.POST.get('password', '').strip()
        role = request.POST.get('role', 'student')
        risk_level = request.POST.get('risk_level', 'low')
        xp = int(request.POST.get('xp') or 0)

        if not username:
            messages.error(request, "El nombre de usuario no puede quedar vacío.")
            return redirect('admin_view')

        if User.objects.filter(username=username).exclude(id=target_user.id).exists():
            messages.error(request, f"Ya existe otra cuenta con el nombre '{username}'.")
            return redirect('admin_view')

        target_user.username = username
        target_user.email = email

        if new_password:
            target_user.set_password(new_password)

        if target_user == request.user and role == 'student':
            messages.warning(request, "No puedes quitarte tus propios permisos de administrador en la sesión activa.")
        else:
            if role == 'superuser':
                target_user.is_staff = True
                target_user.is_superuser = True
            elif role == 'staff':
                target_user.is_staff = True
                target_user.is_superuser = False
            else:
                target_user.is_staff = False
                target_user.is_superuser = False

        target_user.save()

        profile, _ = Profile.objects.get_or_create(user=target_user)
        profile.risk_level = risk_level
        profile.xp = max(0, xp)
        profile.save()

        messages.success(request, f"Cuenta '{username}' actualizada correctamente.")
    return redirect('admin_view')

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