# sns_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from bookmaker import views as bookmaker_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', bookmaker_views.top_board, name='top_page'),
    path('api/users/', bookmaker_views.get_users_json, name='get_users_json'),
    path('bookmaker/', include('bookmaker.urls')),

    # 💡「views」ではなく「bookmaker_views」に修正しました！
    path('create-chat/', bookmaker_views.create_chat, name='create_chat'),
    path('chat/<int:chat_id>/delete/', bookmaker_views.delete_chat, name='delete_chat'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)