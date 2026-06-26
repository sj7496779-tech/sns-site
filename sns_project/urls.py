# sns_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from bookmaker import views as bookmaker_views



urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', bookmaker_views.top_board, name='top_page'),
    path('bookmaker/', include('bookmaker.urls')),
]