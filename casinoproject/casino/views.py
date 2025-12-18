import random
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .trump import TRUMP
from accounts.models import CustomUser
from .models import GameHistory

# Create your views here.
@login_required
def top(request):
    player = request.user
    return render(request, 'casino/top.html',{'money': player.money})

def get_card_value(rank):
    """バカラでのカードの値を取得"""
    if rank >= 10:
        return 0
    return rank

def calculate_score(cards):
    """カードのスコアを計算（下一桁）"""
    total = sum(get_card_value(card['rank']) for card in cards)
    return total % 10

def should_draw_third_card(player_score, banker_score, player_third_value=None):
    """3枚目を引くべきか判定"""
    # 8-9はナチュラル、引かない
    if player_score >= 8 or banker_score >= 8:
        return False, False
    
    # プレイヤーの判定
    player_draws = player_score <= 5
    
    # バンカーの判定
    if not player_draws:
        # プレイヤーが引かない場合
        banker_draws = banker_score <= 5
    else:
        # プレイヤーが3枚目を引いた場合のバンカーのルール
        if banker_score <= 2:
            banker_draws = True
        elif banker_score == 3:
            banker_draws = player_third_value != 8
        elif banker_score == 4:
            banker_draws = player_third_value in [2, 3, 4, 5, 6, 7]
        elif banker_score == 5:
            banker_draws = player_third_value in [4, 5, 6, 7]
        elif banker_score == 6:
            banker_draws = player_third_value in [6, 7]
        else:
            banker_draws = False
    
    return player_draws, banker_draws

def result(player_score, banker_score, player, bet_amount, bet_type):
    # 勝敗判定
    if player_score > banker_score:
        winner = 'player'
        player.money += bet_amount if bet_type == 'player' else -bet_amount
    elif banker_score > player_score:
        winner = 'banker'
        player.money += bet_amount if bet_type == 'banker' else -bet_amount
    else:
        winner = 'draw'
        if bet_type == 'draw':
            player.money += bet_amount * 8  # 引き分けの配当
        else:
            player.money -= bet_amount
    player.save()

    GameHistory.objects.create(
        user=player,
        winner=winner,
        player_score=player_score,
        banker_score=banker_score
    )

    return winner

@login_required
def bacarrat(request):
    player = request.user

    if request.method == 'POST':
        # 3枚目を引く処理
        action = request.POST.get('action')
        if action == 'draw':
            # セッションからカード情報を取得
            player_cards = request.session.get('player_cards')
            banker_cards = request.session.get('banker_cards')
            used_cards = request.session.get('used_cards', [])
            
            # 3枚目を引くカードを取得
            remaining_cards = [card for card in TRUMP if card['name'] not in used_cards]
            new_cards = random.sample(remaining_cards, 2)
            
            player_draws = request.session.get('player_draws')
            banker_draws = request.session.get('banker_draws')
            
            if player_draws:
                player_cards.append(new_cards[0])
                used_cards.append(new_cards[0]['name'])
            
            if banker_draws:
                banker_cards.append(new_cards[1] if player_draws else new_cards[0])
            
            player_score = calculate_score(player_cards)
            banker_score = calculate_score(banker_cards)

            origin_money = player.money
            bet_amount = request.session.get('bet_amount', 0)
            bet_type = request.session.get('bet_type')
            
            winner = result(player_score, banker_score, player, bet_amount, bet_type)
            
            return render(request, 'casino/bacarrat.html', {
                'player_cards': player_cards,
                'banker_cards': banker_cards,
                'player_score': player_score,
                'banker_score': banker_score,
                'winner': winner,
                'game_over': True,
                'origin_money':origin_money,
                'money': player.money,
            })
    
    # 初回表示：2枚ずつ配る
    cards = random.sample(TRUMP, 4)
    player_cards = cards[:2]
    banker_cards = cards[2:]
    
    player_score = calculate_score(player_cards)
    banker_score = calculate_score(banker_cards)
    
    # 3枚目を引くか判定
    player_draws, banker_draws = should_draw_third_card(player_score, banker_score)
    bet_amount = request.session.get('bet_amount', 0)
    bet_type = request.session.get('bet_type')
    origin_money = player.money
    # 3枚目を引く場合はセッションに保存
    if player_draws or banker_draws:
        request.session['player_cards'] = player_cards
        request.session['banker_cards'] = banker_cards
        request.session['used_cards'] = [card['name'] for card in cards]
        request.session['player_draws'] = player_draws
        request.session['banker_draws'] = banker_draws
        
        return render(request, 'casino/bacarrat.html', {
            'player_cards': player_cards,
            'banker_cards': banker_cards,
            'player_score': player_score,
            'banker_score': banker_score,
            'need_third_card': True,
        })
    else:
        winner = result(player_score, banker_score, player, bet_amount, bet_type)

        return render(request, 'casino/bacarrat.html', {
            'player_cards': player_cards,
            'banker_cards': banker_cards,
            'player_score': player_score,
            'banker_score': banker_score,
            'winner': winner,
            'game_over': True,
            'origin_money':origin_money,
            'money': player.money,
        })
    
@login_required
def bacara_bet(request):
    player = request.user
    
    # セッションから罫線の状態を取得（なければ初期化）
    histList = request.session.get('histList', [[]])
    last_winner = request.session.get('last_winner', None)
    last_processed_id = request.session.get('last_processed_id', None)
    
    # 最新の1件だけ取得
    latest_history = GameHistory.objects.filter(user=player).order_by('-played_at').first()
    
    # 最新の履歴があり、かつ未処理の場合のみ処理
    if latest_history and latest_history.id != last_processed_id:
        if latest_history.winner == 'player':
            # 直前の勝者（引き分け除く）がbankerなら新しい列へ
            if last_winner == 'b':
                newLine = ["p"]
                histList.append(newLine)
            else:
                if not histList or not histList[-1]:
                    histList = [["p"]]
                else:
                    histList[-1].append('p')
            last_winner = 'p'
        elif latest_history.winner == 'banker':
            # 直前の勝者（引き分け除く）がplayerなら新しい列へ
            if last_winner == 'p':
                newLine = ['b']
                histList.append(newLine)
            else:
                if not histList or not histList[-1]:
                    histList = [['b']]
                else:
                    histList[-1].append('b')
            last_winner = 'b'
        else:
            # 引き分けは現在の列に追加、last_winnerは更新しない
            if not histList or not histList[-1]:
                histList = [['d']]
            else:
                histList[-1].append('d')
        
        # 処理済みIDを更新
        last_processed_id = latest_history.id
    
    # 空のリストを削除
    if histList and not histList[0]:
        histList = histList[1:]
    
    # 7列を超えたら、一番古い列（先頭）を削除
    while len(histList) > 7:
        histList.pop(0)
    
    # セッションに保存
    request.session['histList'] = histList
    request.session['last_winner'] = last_winner
    request.session['last_processed_id'] = last_processed_id

    max_length = max(len(column) for column in histList) if histList else 5
    max_length = max(max_length, 5)
    max_length_value = max_length  # 数値を保持
    max_length = range(max_length)

    if request.method == 'POST':
        # ベット金額と種類を取得
        bet_amount = int(request.POST.get('bet_amount', 0))
        bet_type = request.POST.get('bet_type')
        
        # セッションにベット情報を保存
        request.session['bet_amount'] = bet_amount
        request.session['bet_type'] = bet_type
        
        return redirect('bacarrat')
    return render(request, 'casino/bacara_bet.html', {
        'money': player.money, 
        'histList': histList, 
        'max_length': max_length,
        'max_length_value': max_length_value
    })