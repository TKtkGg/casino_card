from django.db import models
from accounts.models import CustomUser

class GameHistory(models.Model):
    RESULT_CHOICES = [
        ('player', 'Player'),
        ('banker', 'Banker'),
        ('draw', 'Draw'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='game_histories')
    winner = models.CharField(max_length=10, choices=RESULT_CHOICES)
    player_score = models.IntegerField()
    banker_score = models.IntegerField()
    played_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-played_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.winner} ({self.player_score} vs {self.banker_score})"