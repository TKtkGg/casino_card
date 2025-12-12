import random
from django.shortcuts import render
from .trump import TRUMP

# Create your views here.
def top(request):
    return render(request, 'casino/top.html')

def bacarrat(request):
    cards = random.sample(TRUMP, 4)  # 4枚まとめて取得
    player_cards = cards[:2]
    banker_cards = cards[2:]
    
    return render(request, 'casino/bacarrat.html', {
        'player_cards': player_cards,
        'banker_cards': banker_cards,
    })