from __future__ import annotations
from datetime import datetime
from typing import Optional
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import AccountProfile, Bet, Option, Topic

DEFAULT_STARTING_POINTS = 1000

# ユーザーごとのプロフィールを取得または作成する。
def get_or_create_profile(user: User) -> AccountProfile:
    # すでにプロフィールがあればそれを返し、なければ新規作成する。
    return AccountProfile.objects.get_or_create(
        uid=user,
        defaults={'name': user.username, 'currentpoint': DEFAULT_STARTING_POINTS},
    )[0]


# 文字列の日時を Django の日時型に変換する。
def _coerce_datetime(value: Optional[str]) -> Optional[datetime]:
    # 空文字ならそのまま None を返す。
    if not value:
        return None

    # 文字列を datetime に変換する。
    parsed_value = parse_datetime(value)
    if parsed_value is not None:
        # naive datetime なら timezone を付けて扱いやすくする。
        if timezone.is_naive(parsed_value):
            return timezone.make_aware(parsed_value)
        return parsed_value

    # 変換できなければ現在時刻を返す。
    return timezone.now()


# POSTデータから新しいお題を作成する。
def create_topic_from_request(request) -> Topic:
    data = request.POST
    # Topic を作成する。
    topic = Topic.objects.create(
        topictitle=data.get('topictitle', '').strip(),
        topicdetailtext=data.get('topicdetailtext', '').strip(),
        uid=request.user,
        status='open',
        deadtime=_coerce_datetime(data.get('deadtime')),
    )

    # 選択肢を順番に作成する。
    for raw_text in (data.get('option1', ''), data.get('option2', ''), data.get('option3', ''), data.get('option4', '')):
        text = raw_text.strip()
        if text:
            Option.objects.create(topicid=topic, text=text)

    return topic


# 現在受付中で、期限切れでないお題を取得する。
def get_active_topics_queryset() -> QuerySet[Topic]:
    return Topic.objects.filter(status='open', deadtime__gt=timezone.now()).order_by('-deadtime')


# ポイントランキングの上位10人を取得する。
def get_ranking_list() -> QuerySet[AccountProfile]:
    return AccountProfile.objects.all().order_by('-currentpoint')[:10]


# 指定ユーザーのベット一覧を取得する。
def get_user_bets(user: User):
    return Bet.objects.filter(uid=user).select_related('optid__topicid')


# 指定ユーザーが作成したお題一覧を取得する。
def get_user_created_topics(user: User):
    return Topic.objects.filter(uid_id=user.id).prefetch_related('options').order_by('-topicid')
