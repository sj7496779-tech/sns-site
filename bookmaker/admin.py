# Django の管理サイト機能を使うための import
from django.contrib import admin
# bookmaker アプリのモデルをインポートする
from .models import AccountProfile, Topic, Option, Bet, Chat, Reaction, Reply

# ここでは各モデルを管理画面に登録して、/admin から操作できるようにしています。
admin.site.register(AccountProfile)
admin.site.register(Topic)
admin.site.register(Option)
admin.site.register(Bet)
admin.site.register(Chat)
admin.site.register(Reaction)
admin.site.register(Reply)