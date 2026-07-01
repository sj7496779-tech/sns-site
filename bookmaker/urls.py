# bookmaker/urls.py
from django.urls import path
from . import views

# ここが {% url 'bookmaker:...' %} の「bookmaker」に対応します
app_name = 'bookmaker'

# urlpatterns はこのアプリ内で定義する URL パターンのリストです。
# path() の第1引数は URL のパターン、第2引数は呼び出すビュー関数、第3引数は URL の名前です。
urlpatterns = [
    # ルート URL /bookmaker/ にアクセスすると topic_list() が呼ばれ、
    # お題の一覧を表示します。
    path('', views.topic_list, name='topic_list'),

    # topic/<int:topic_id>/ は整数の topic_id を受け取る URL パターンです。
    # たとえば /bookmaker/topic/5/ にアクセスすると topic_id=5 が渡されます。
    path('topic/<int:topic_id>/', views.topic_detail, name='topic_detail'),

    # chat/<int:chat_id>/reaction/ は投稿 ID を受け取り、その投稿へのリアクションを切り替えます。
    path('chat/<int:chat_id>/reaction/', views.toggle_reaction, name='toggle_reaction'),

    # chat/<int:chat_id>/reply/ は投稿 ID を受け取り、その投稿に返信を追加します。
    path('chat/<int:chat_id>/reply/', views.create_reply, name='create_reply'),

    # topic/<int:topic_id>/result/ はお題の結果を確定する操作を行う URL です。
    path('topic/<int:topic_id>/result/', views.set_topic_result, name='set_topic_result'),

    # api/users/ はユーザー一覧を JSON で返す API エンドポイントです。
    path('api/users/', views.get_users_json, name='get_users_json'),
]