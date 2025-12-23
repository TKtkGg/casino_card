import random
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from .trump import TRUMP

class Blackjack:
    """ブラックジャックゲームのロジッククラス"""

    SPLIT_COMPLETE_STATES = {'standing', 'bust', 'blackjack'}

    @staticmethod
    def draw_unique_card(used_cards):
        """未使用のカードを1枚取得"""
        remaining_cards = [card for card in TRUMP if card['name'] not in used_cards]
        if not remaining_cards:
            raise ValueError("No cards remaining to draw.")
        new_card = random.choice(remaining_cards)
        used_cards.append(new_card['name'])
        return new_card

    @staticmethod
    def can_split(player_cards, bet_amount, player_money):
        """スプリット可能か判定"""
        return (
            len(player_cards) == 2
            and player_cards[0]['rank'] == player_cards[1]['rank']
            and bet_amount > 0
            and player_money >= bet_amount * 2
        )

    @staticmethod
    def get_split_context(request):
        """テンプレート用スプリット情報"""
        return {
            'split_available': request.session.get('split_available', False),
            'split_prompt': request.session.get('split_prompt', False),
            'split_active': request.session.get('split_active', False),
            'split_hands': request.session.get('split_hands', []),
            'split_complete': request.session.get('split_complete', False),
        }

    def split_round_ready(self, hands):
        """全ハンドの入力が完了したか"""
        if not hands:
            return False
        return all(hand.get('status') in self.SPLIT_COMPLETE_STATES for hand in hands)

    def resolve_split_round(self, request, player, dealer_cards, used_cards, bet_amount, bet_type, hands):
        """スプリット後の勝敗をまとめて判定"""
        dealer_score = self.calculate_score(dealer_cards)
        while dealer_score < 17:
            new_card = self.draw_unique_card(used_cards)
            dealer_cards.append(new_card)
            dealer_score = self.calculate_score(dealer_cards)

        for hand in hands:
            hand_score = self.calculate_score(hand['cards'])
            hand['score'] = hand_score
            hand['result'] = self.handle_result(hand_score, dealer_score, player, bet_amount, bet_type, hand['cards'])

        request.session['dealer_cards'] = dealer_cards
        request.session['dealer_score'] = dealer_score
        request.session['split_hands'] = hands
        request.session['split_complete'] = True
        request.session['split_prompt'] = False
        request.session['split_available'] = False
        request.session['game_over'] = True
        request.session['game_result_saved'] = True
        request.session['winner'] = 'split'
        request.session['used_cards'] = used_cards
        if hands:
            request.session['player_score'] = hands[0]['score']
    @staticmethod
    def calculate_score(cards):
        """カードのスコアを計算"""
        score = 0
        ace_count = 0
        
        for card in cards:
            rank = card['rank']
            if rank >= 10:
                score += 10
            elif rank == 1:
                ace_count += 1
                score += 11  # 最初はエースを11としてカウント
            else:
                score += rank
        
        # エースの調整
        while score > 21 and ace_count:
            score -= 10
            ace_count -= 1
        
        return score

    @staticmethod
    def handle_result(player_score, dealer_score, player, bet_amount, bet_type, player_cards):
        """勝敗判定とDB保存"""
        # ブラックジャック判定（最初の2枚で21）
        is_blackjack = len(player_cards) == 2 and player_score == 21
        
        # 勝敗判定
        if player_score > 21:
            winner = 'dealer'
            player.money -= bet_amount
        elif dealer_score > 21 or player_score > dealer_score:
            if is_blackjack:
                winner = 'blackjack'
                # ブラックジャックは1.5倍の配当
                player.money += int(bet_amount * 1.5)
            else:
                winner = 'player'
                player.money += bet_amount
        elif dealer_score > player_score:
            winner = 'dealer'
            player.money -= bet_amount
        else:
            winner = 'draw'
            # 引き分けの場合、ベット金額は変わらない
        
        player.save()

        return winner
    
    def start_game(self, request):
        """ブラックジャックゲームの開始（GETリクエスト処理）"""
        player = request.user
        
        # セッションにゲーム結果が既に保存されているか確認（リロード対策）
        if request.session.get('game_result_saved', False):
            # 既にゲームが終了している場合は、保存されたデータを使用
            player_cards = request.session.get('player_cards')
            dealer_cards = request.session.get('dealer_cards')
            player_score = request.session.get('player_score')
            dealer_score = request.session.get('dealer_score')
            winner = request.session.get('winner')
            origin_money = request.session.get('origin_money')
            game_over = request.session.get('game_over', False)
            context = {
                'player_cards': player_cards,
                'dealer_cards': dealer_cards,
                'player_score': player_score,
                'dealer_score': dealer_score,
                'winner': winner,
                'game_over': game_over,
                'origin_money': origin_money,
                'money': player.money,
            }
            context.update(self.get_split_context(request))
            
            return render(request, 'casino/blackjack.html', context)
        
        # 新しいゲームの開始：デバッグ用で必ずプレイヤーに10を2枚配る
        tens = [card for card in TRUMP if card['rank'] == 1]
        player_cards = [tens[0], tens[1]]
        rest = [card for card in TRUMP if card not in player_cards]
        dealer_cards = random.sample(rest, 2)
        used_cards = [card['name'] for card in player_cards + dealer_cards]
        
        player_score = self.calculate_score(player_cards)
        dealer_score = self.calculate_score(dealer_cards)

        origin_money = player.money
        bet_amount = request.session.get('bet_amount', 0)
        bet_type = request.session.get('bet_type')

        split_available = self.can_split(player_cards, bet_amount, player.money)
        request.session['split_available'] = split_available
        request.session['split_prompt'] = split_available
        request.session['split_active'] = False
        request.session['split_complete'] = False
        request.session['split_hands'] = []

        # プレイヤーが最初の2枚でブラックジャック（21）の場合、即座に勝利
        if player_score == 21:
            # ディーラーのカードを全て引く
            while dealer_score < 17:
                new_card = self.draw_unique_card(used_cards)
                dealer_cards.append(new_card)
                dealer_score = self.calculate_score(dealer_cards)
            
            # ブラックジャックで勝利（問答無用）
            winner = 'blackjack'
            player.money += int(bet_amount * 1.5)
            player.save()
            
            # セッションに結果を保存
            request.session['player_cards'] = player_cards
            request.session['dealer_cards'] = dealer_cards
            request.session['player_score'] = player_score
            request.session['dealer_score'] = dealer_score
            request.session['winner'] = winner
            request.session['game_over'] = True
            request.session['game_result_saved'] = True
            request.session['origin_money'] = origin_money
            
            context = {
                'player_cards': player_cards,
                'dealer_cards': dealer_cards,
                'player_score': player_score,
                'dealer_score': dealer_score,
                'winner': winner,
                'game_over': True,
                'origin_money': origin_money,
                'money': player.money,
            }
            context.update(self.get_split_context(request))

            return render(request, 'casino/blackjack.html', context)

        # セッションにカード情報を保存
        request.session['player_cards'] = player_cards
        request.session['dealer_cards'] = dealer_cards
        request.session['used_cards'] = used_cards
        request.session['origin_money'] = origin_money
        request.session['game_result_saved'] = False  # まだゲーム終了していない
        
        context = {
            'player_cards': player_cards,
            'dealer_cards': dealer_cards,
            'player_score': player_score,
            'dealer_score': dealer_score,
            'origin_money': origin_money,
            'money': player.money,
        }
        context.update(self.get_split_context(request))

        return render(request, 'casino/blackjack.html', context)
    
    def play_game(self, request):
        """ブラックジャックゲームの実行（POSTリクエスト処理）"""
        player = request.user
        action = request.POST.get('action')
        # セッションからカード情報を取得
        player_cards = request.session.get('player_cards') or []
        dealer_cards = request.session.get('dealer_cards') or []
        used_cards = request.session.get('used_cards', [])
        origin_money = request.session.get('origin_money', player.money)
        bet_amount = request.session.get('bet_amount', 0)
        bet_type = request.session.get('bet_type')
        split_context = self.get_split_context(request)
        split_active = split_context['split_active']
        split_hands = split_context['split_hands']

        if action == 'split_no' and request.session.get('split_prompt', False):
            request.session['split_prompt'] = False
            request.session['split_available'] = False
            player_score = self.calculate_score(player_cards)
            dealer_score = self.calculate_score(dealer_cards)
            context = {
                'player_cards': player_cards,
                'dealer_cards': dealer_cards,
                'player_score': player_score,
                'dealer_score': dealer_score,
                'origin_money': origin_money,
                'money': player.money,
            }
            context.update(self.get_split_context(request))
            return render(request, 'casino/blackjack.html', context)

        if action == 'split_yes' and request.session.get('split_available') and not split_active:
            hands = []
            for idx in range(2):
                hand_cards = [player_cards[idx]]
                new_card = self.draw_unique_card(used_cards)
                hand_cards.append(new_card)
                score = self.calculate_score(hand_cards)
                status = 'blackjack' if score == 21 else 'playing'
                hands.append({
                    'cards': hand_cards,
                    'score': score,
                    'status': status,
                    'result': None,
                })
            request.session['split_active'] = True
            request.session['split_hands'] = hands
            request.session['split_prompt'] = False
            request.session['split_available'] = False
            request.session['split_complete'] = False
            request.session['used_cards'] = used_cards

            if self.split_round_ready(hands):
                self.resolve_split_round(request, player, dealer_cards, used_cards, bet_amount, bet_type, hands)

            context = {
                'player_cards': player_cards,
                'dealer_cards': dealer_cards,
                'player_score': self.calculate_score(player_cards),
                'dealer_score': self.calculate_score(dealer_cards),
                'origin_money': origin_money,
                'money': player.money,
            }
            context.update(self.get_split_context(request))
            return render(request, 'casino/blackjack.html', context)

        if split_active and action in ('split_hit', 'split_stand'):
            hand_index = int(request.POST.get('hand_index', -1))
            if 0 <= hand_index < len(split_hands):
                hand = split_hands[hand_index]
                if hand.get('status') == 'playing':
                    # Aのスプリットは1回だけヒット可能
                    if action == 'split_hit':
                        new_card = self.draw_unique_card(used_cards)
                        hand['cards'].append(new_card)
                        hand['score'] = self.calculate_score(hand['cards'])
                        # Aのスプリットなら1回ヒットしたら自動でSTANDING
                        if hand['cards'][0]['rank'] == 1:
                            hand['status'] = 'standing'
                        elif hand['score'] > 21:
                            hand['status'] = 'bust'
                        elif hand['score'] == 21:
                            hand['status'] = 'standing'
                    else:
                        hand['status'] = 'standing'
                    split_hands[hand_index] = hand
                    request.session['split_hands'] = split_hands
                    request.session['used_cards'] = used_cards
                    if self.split_round_ready(split_hands) and not request.session.get('split_complete', False):
                        self.resolve_split_round(request, player, dealer_cards, used_cards, bet_amount, bet_type, split_hands)
            context = {
                'player_cards': player_cards,
                'dealer_cards': dealer_cards,
                'player_score': self.calculate_score(player_cards),
                'dealer_score': self.calculate_score(dealer_cards),
                'origin_money': origin_money,
                'money': player.money,
            }
            context.update(self.get_split_context(request))
            return render(request, 'casino/blackjack.html', context)

        if action == 'hit' and not split_active:
            # プレイヤーがヒットを選択
            request.session['split_prompt'] = False
            request.session['split_available'] = False
            new_card = self.draw_unique_card(used_cards)
            player_cards.append(new_card)
            
            player_score = self.calculate_score(player_cards)
            dealer_score = self.calculate_score(dealer_cards)

            # セッションに更新したカード情報を保存
            request.session['player_cards'] = player_cards
            request.session['used_cards'] = used_cards

            if player_score >= 21:
                # プレイヤーがバースト、ブラックジャック
                while dealer_score < 17:
                    new_card = self.draw_unique_card(used_cards)
                    dealer_cards.append(new_card)
                    dealer_score = self.calculate_score(dealer_cards)

                winner = self.handle_result(player_score, dealer_score, player, bet_amount, bet_type, player_cards)

                # ゲーム終了時にセッションに結果を保存
                request.session['player_score'] = player_score
                request.session['dealer_score'] = dealer_score
                request.session['winner'] = winner
                request.session['game_over'] = True
                request.session['game_result_saved'] = True

                context = {
                    'player_cards': player_cards,
                    'dealer_cards': dealer_cards,
                    'player_score': player_score,
                    'dealer_score': dealer_score,
                    'winner': winner,
                    'game_over': True,
                    'origin_money': origin_money,
                    'money': player.money,
                }
                context.update(self.get_split_context(request))
                return render(request, 'casino/blackjack.html', context)
            else:
                context = {
                    'player_cards': player_cards,
                    'dealer_cards': dealer_cards,
                    'player_score': player_score,
                    'dealer_score': dealer_score,
                    'origin_money': origin_money,
                    'money': player.money,
                }
                context.update(self.get_split_context(request))
                return render(request, 'casino/blackjack.html', context)
            
        elif action == 'stand' and not split_active:
            # プレイヤーがスタンドを選択
            request.session['split_prompt'] = False
            request.session['split_available'] = False
            player_score = self.calculate_score(player_cards)
            dealer_score = self.calculate_score(dealer_cards)
            
            # ディーラーのターン
            while dealer_score < 17:
                new_card = self.draw_unique_card(used_cards)
                dealer_cards.append(new_card)
                dealer_score = self.calculate_score(dealer_cards)
            
            winner = self.handle_result(player_score, dealer_score, player, bet_amount, bet_type, player_cards)
            
            # ゲーム終了時にセッションに結果を保存
            request.session['player_score'] = player_score
            request.session['dealer_score'] = dealer_score
            request.session['winner'] = winner
            request.session['game_over'] = True
            request.session['game_result_saved'] = True
            
            context = {
                'player_cards': player_cards,
                'dealer_cards': dealer_cards,
                'player_score': player_score,
                'dealer_score': dealer_score,
                'winner': winner,
                'game_over': True,
                'origin_money': origin_money,
                'money': player.money,
            }
            context.update(self.get_split_context(request))
            return render(request, 'casino/blackjack.html', context)
        
        # どのアクションにも該当しない場合（フォールバック）
        return redirect('top')