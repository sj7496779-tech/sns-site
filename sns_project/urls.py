# sns_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from bookmaker import views as bookmaker_views



urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. ログインページ（Django標準の機能を使用）
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    # ログアウト用URLも作っておくと便利です
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # 2. トップページ（普通の掲示板 / ここでは仮の汎用ビューでトップを構築）
    # ※もしすでに掲示板アプリがある場合は、そちらのincludeに変更してください
    path('', bookmaker_views.top_board, name='top_page'),
    
    # 3. ブックメーカーページ
    path('bookmaker/', include('bookmaker.urls')),
]