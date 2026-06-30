from django.db import models
from django.contrib.auth.models import User

# 1. アカウントDB（標準のUserにポイント等を統合）
class AccountProfile(models.Model):
    # Django標準のUserと1対1で紐づけ、これを uid として扱う
    uid = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='profile')
    name = models.CharField(max_length=150) # ユーザー名
    currentpoint = models.IntegerField(default=1000) # 現在の持ちポイント

    def __str__(self):
        return self.name

# 2. お題DB
class Topic(models.Model):
    topicid = models.AutoField(primary_key=True) # 主キー（自動連番）
    topictitle = models.CharField(max_length=200) # お題のタイトル
    uid = models.ForeignKey(User, on_delete=models.SET_NULL, null=True) # 外部キー：お題を作成した人
    topicdetailtext = models.TextField() # お題の詳しい説明
    status = models.CharField(max_length=20, default='open') # ステータス
    deadtime = models.DateTimeField() # 締め切り時間

    def __str__(self):
        return self.topictitle

# 3. 選択肢DB
class Option(models.Model):
    optid = models.AutoField(primary_key=True) # 主キー（自動連番）
    text = models.CharField(max_length=100) # 選択肢のテキスト
    # 外部キー：紐づくお題
    topicid = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='options') 

    def __str__(self):
        return f"{self.topicid.topictitle} - {self.text}"

    # ↓↓↓ ここに正しいオッズ計算ロジックをプロパティとして追加します ↓↓↓
    @property
    def odds(self):
        # 1. この選択肢（Option）に賭けられた総ポイントを計算
        # bet_set は Bet モデルから逆参照するための Django の仕組みです
        current_option_points = sum(bet.betpoint for bet in self.bet_set.all())

        # まだ誰もこの選択肢に賭けていない場合は、ゼロ除算を防ぐために初期値 1.0倍 にする
        if current_option_points == 0:
            return 1.0

        # 2. このお題（Topic）全体に賭けられた総ポイントを計算
        # 紐づいている topicid から全選択肢をループし、すべての Bet を合計する
        total_topic_points = 0
        for option in self.topicid.options.all():
            total_topic_points += sum(bet.betpoint for bet in option.bet_set.all())

        # お題全体にまだ1ポイントも賭けられていない場合（初期状態）
        if total_topic_points == 0:
            return 1.0

        # 3. オッズを計算（お題全体の総ポイント ÷ この選択肢のポイント）
        computed_odds = total_topic_points / current_option_points
        
        # 小数点第2位までに丸めて返す（例: 1.54）
        return round(computed_odds, 2)
    
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.topicid.topictitle} - {self.text}"

   # bookmaker/models.py の Option クラス内を以下に差し替え

    @property
    def odds(self):
        # 1. この選択肢に賭けられた合計ポイント
        current_option_points = sum(bet.betpoint for bet in self.bet_set.all())

        # 2. お題全体の合計ポイントを計算
        total_topic_points = 0
        for option in self.topicid.options.all():
            total_topic_points += sum(bet.betpoint for bet in option.bet_set.all())

        # ─── 【ここから新規オッズ判定ロジック】 ───
        
        # パターンA: まだ誰もお題全体に1ポイントも賭けていない場合 ➡ 1.0倍
        if total_topic_points == 0:
            return 1.0

        # パターンB: 全体には賭け金があるのに、この選択肢には1ptも賭けられていない場合
        # （＝もう片方にだけ賭け金が集中している状態）
        if current_option_points == 0:
            return 99.9  # 上限値としてデフォルト表示

        # パターンC: 通常のオッズ計算（全体ポイント ÷ この選択肢のポイント）
        computed_odds = total_topic_points / current_option_points
        
        # 小数点以下2桁で丸めて返す
        return round(computed_odds, 2)


# 4. ユーザーごとの賭け金DB
class Bet(models.Model):
    uid = models.ForeignKey(User, on_delete=models.CASCADE) # 複合主キーのパーツ1（外部キー）
    optid = models.ForeignKey(Option, on_delete=models.CASCADE) # 複合主キーのパーツ2（外部キー）
    betpoint = models.IntegerField(default=0) # 賭け金

    class Meta:
        # Djangoで「複合主キー（一意のペア）」を表現する設定
        unique_together = (('uid', 'optid'),)

    def __str__(self):
        return f"{self.uid.username} -> {self.optid.text} ({self.betpoint}pt)"
    

# bookmaker/models.py などの一番下に追記
from django.db import models
from django.contrib.auth.models import User # ユーザーモデルをインポート

# 1. チャット（投稿）DB
class Chat(models.Model):
    chatid = models.AutoField(primary_key=True) # 主キー（自動連番）
    uid = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats') 
    text = models.TextField() # 本文
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True) # 画像添付
    time = models.DateTimeField(auto_now_add=True) # 投稿日時を自動記録

    # 💡 ★ここに新しく列を追加！
    # お題が削除されてもチャット自体は残すため、SET_NULL（空を許容）に設定します
    shared_topic = models.ForeignKey(
        Topic, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='shared_chats'
    )

    def __str__(self):
        return f"{self.uid.username}: {self.text[:10]}"

# 2. リアクションDB
class Reaction(models.Model):
    reactionid = models.AutoField(primary_key=True) # 主キー（自動連番）
    uid = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reactions')
    chatid = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='reactions')

    # 同じ人が同じチャットに何度もリアクションできないようにする（一意制約）
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['uid', 'chatid'], name='unique_user_reaction')
        ]

    def __str__(self):
        return f"{self.uid.username} reacted to Chat {self.chatid.chatid}"
    

class Reply(models.Model):
    replyid = models.AutoField(primary_key=True)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='replies')
    uid = models.ForeignKey(User, on_delete=models.CASCADE, related_name='replies')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='child_replies')
    text = models.TextField()
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        parent_info = f" reply to {self.parent.replyid}" if self.parent else ''
        return f"{self.uid.username} -> Reply to Chat {self.chat.chatid}{parent_info}: {self.text[:12]}"
    
