from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

# 1. Perfil extendido del usuario
class Profile(models.Model):
    RISK_CHOICES = [
        ('low', 'Bajo Riesgo'),
        ('medium', 'Riesgo Medio'),
        ('high', 'Alto Riesgo'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default='low')
    xp = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Perfil de {self.user.username}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    # Evita crear perfiles duplicados al ejecutar loaddata / fixtures
    if kwargs.get('raw', False):
        return
    if created:
        Profile.objects.create(user=instance)

# 2. Registro histórico de sesiones Pomodoro
class PomodoroSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pomodoros')
    completed_at = models.DateTimeField(default=timezone.now)
    duration_minutes = models.PositiveIntegerField(default=25)

    def __str__(self):
        return f"Pomodoro de {self.user.username} el {self.completed_at.strftime('%Y-%m-%d %H:%M')}"

# 3. Registro histórico de recompensas canjeadas
class RewardRedemption(models.Model):
    REWARD_CHOICES = [
        ('pausas', 'Pausas Activas'),
        ('apuntes', 'Descarga de Apuntes'),
        ('puntos', 'Puntos Extra'),
        ('libre', 'Horario Libre'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='redemptions')
    reward_type = models.CharField(max_length=20, choices=REWARD_CHOICES)
    redeemed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} canjeó {self.get_reward_type_display()}"