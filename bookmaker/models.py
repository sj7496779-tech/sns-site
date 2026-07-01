from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# ユーザーごとのプロフィールを保持するモデル。
# AccountProfile は User と1対1で紐づき、表示名とポイント残高を持ちます。
class AccountProfile(models.Model):
    uid = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='profile')
    name = models.CharField(max_length=150)
    currentpoint = models.IntegerField(default=1000)

    def __str__(self):
        return self.name


# お題を表すモデル。
# ユーザーが作成し、複数の選択肢と賭けを持つことができます。
class Topic(models.Model):
    topicid = models.AutoField(primary_key=True)
    topictitle = models.CharField(max_length=200)
    uid = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    topicdetailtext = models.TextField()
    status = models.CharField(max_length=20, default='open')
    deadtime = models.DateTimeField()

    def __str__(self):
        return self.topictitle

    @property
    def is_active(self):
        # 受付中かつ期限が未来なら有効とみなす。
        return self.status != 'closed' and self.deadtime > timezone.now()

    @property
    def is_closed(self):
        # 結果確定済み、または期限切れなら終了とみなす。
        return self.status == 'closed' or self.deadtime <= timezone.now()


# お題の選択肢を表すモデル。
# 1つのお題に複数の Option が紐づきます。
class Option(models.Model):
    optid = models.AutoField(primary_key=True)
    text = models.CharField(max_length=100)
    topicid = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='options')
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.topicid.topictitle} - {self.text}"

    @property
    def odds(self):
        # この選択肢に賭けられたポイント合計
        current_option_points = sum(bet.betpoint for bet in self.bet_set.all())
        # お題全体の賭けポイント合計
        total_topic_points = sum(
            sum(bet.betpoint for bet in option.bet_set.all())
            for option in self.topicid.options.all()
        )

        if total_topic_points == 0:
            return 1.0

        if current_option_points == 0:
            return 99.9

        return round(total_topic_points / current_option_points, 2)


# ユーザーのベットを表すモデル。
# 1人のユーザーは1つの選択肢に対して1つの Bet を持ちます。
class Bet(models.Model):
    uid = models.ForeignKey(User, on_delete=models.CASCADE)
    optid = models.ForeignKey(Option, on_delete=models.CASCADE)
    betpoint = models.IntegerField(default=0)

    class Meta:
        unique_together = (('uid', 'optid'),)

    def __str__(self):
        return f"{self.uid.username} -> {self.optid.text} ({self.betpoint}pt)"


# 掲示板投稿を表すモデル。
# テキストと画像、関連お題、投稿時間を保持します。
class Chat(models.Model):
    chatid = models.AutoField(primary_key=True)
    uid = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats')
    text = models.TextField()
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)
    time = models.DateTimeField(auto_now_add=True)
    shared_topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shared_chats',
    )

    def __str__(self):
        return f"{self.uid.username}: {self.text[:10]}"


# 投稿に対するリアクションを表すモデル。
# 1ユーザー1投稿につき1つだけ保持されます。
class Reaction(models.Model):
    reactionid = models.AutoField(primary_key=True)
    uid = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reactions')
    chatid = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='reactions')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['uid', 'chatid'], name='unique_user_reaction')
        ]

    def __str__(self):
        return f"{self.uid.username} reacted to Chat {self.chatid.chatid}"


# 投稿への返信を表すモデル。
# parent で親返信を持てる二段階のスレッド構造です。
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

