TRUMP = [
    {'suit': suit, 'rank': rank, 'name': f"{suit}{rank}"} 
    for suit in ['spade', 'heart', 'diamond', 'club'] 
    for rank in range(1, 14)
]