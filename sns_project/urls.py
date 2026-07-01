from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from bookmaker import views as bookmaker_views

urlpatterns = [
    # 管理者用管理画面
    path('admin/', admin.site.urls),

    # ログイン / ログアウト用の Django 標準ビュー
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # トップページ（掲示板）
    path('', bookmaker_views.top_board, name='top_page'),

    # ユーザー一覧を JSON で返す API
    path('api/users/', bookmaker_views.get_users_json, name='get_users_json'),

    # bookmaker アプリ側の URL を /bookmaker/ 以下にまとめる
    path('bookmaker/', include('bookmaker.urls')),

    # チャット投稿生成と削除処理
    path('create-chat/', bookmaker_views.create_chat, name='create_chat'),
    path('chat/<int:chat_id>/delete/', bookmaker_views.delete_chat, name='delete_chat'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)