# bookmaker/urls.py
from django.urls import path
from . import views

# ここが {% url 'bookmaker:...' %} の「bookmaker」に対応します
app_name = 'bookmaker'

urlpatterns = [
    # お題一覧（ここが topic_list になっているか確認！）
    path('', views.topic_list, name='topic_list'),
    # お題詳細・賭ける処理（既存のものがあれば残してください）
    path('topic/<int:topic_id>/', views.topic_detail, name='topic_detail'),
    # 先ほど追加したチャットリアクション用
    path('chat/<int:chat_id>/reaction/', views.toggle_reaction, name='toggle_reaction'),
    path('topic/<int:topic_id>/result/', views.set_topic_result, name='set_topic_result'),
]