# admin.py の中身
from django.contrib import admin
from .models import AccountProfile, Topic, Option, Bet,Chat, Reaction

# 管理画面からデータをいじれるように登録する
admin.site.register(AccountProfile)
admin.site.register(Topic)
admin.site.register(Option)
admin.site.register(Bet)
admin.site.register(Chat)
admin.site.register(Reaction)