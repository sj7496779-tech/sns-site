# bookmaker/urls.py
from django.urls import path
from . import views

# ここが {% url 'bookmaker:...' %} の「bookmaker」に対応します
app_name = 'bookmaker'

urlpatterns = [
    path('', views.topic_list, name='topic_list'),
    path('topic/<int:topic_id>/', views.topic_detail, name='topic_detail'),
    path('chat/<int:chat_id>/reaction/', views.toggle_reaction, name='toggle_reaction'),
    path('topic/<int:topic_id>/result/', views.set_topic_result, name='set_topic_result'),
    path('api/users/', views.get_users_json, name='get_users_json'),
]