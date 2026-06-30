import re
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Topic, Option, Bet, AccountProfile, Chat, Reaction, Reply
from django.db.models import Q, Prefetch
from django.contrib.auth.models import User
from django.urls import reverse

# ==========================================
# 1. お題の一覧画面 ＆ 新規投稿処理
# ==========================================
def topic_list(request):
    # 【投稿処理】もし画面から「お題の投稿」フォームが送信されてきたら
    if request.method == 'POST' and 'topictitle' in request.POST:
            
        topictitle = request.POST.get('topictitle')
        topicdetailtext = request.POST.get('topicdetailtext')
        option1_text = request.POST.get('option1')
        option2_text = request.POST.get('option2')
        option3_text = request.POST.get('option3')
        option4_text = request.POST.get('option4')
        deadtime_raw = request.POST.get('deadtime')

        topic = Topic.objects.create(
            topictitle=topictitle,
            topicdetailtext=topicdetailtext,
            uid=request.user,  # 投稿者としてUserオブジェクトを紐付け
            status='open',
            deadtime=deadtime_raw
        )

        Option.objects.create(topicid=topic, text=option1_text)
        Option.objects.create(topicid=topic, text=option2_text)

        if option3_text and option3_text.strip():
            Option.objects.create(topicid=topic, text=option3_text.strip())

        if option4_text and option4_text.strip():
            Option.objects.create(topicid=topic, text=option4_text.strip())

        messages.success(request, '新しいお題を公開しました！')
        return redirect('bookmaker:topic_list')

    # 【表示処理】通常アクセス時
    topics = Topic.objects.all().order_by('-deadtime')
    
    my_bets = None
    profile = None
    my_created_topics = None
    
    # 持ちポイントの高い順に全ユーザーのプロファイルを上位10名取得
    ranking_list = AccountProfile.objects.all().order_by('-currentpoint')[:10]
    
    if request.user.is_authenticated:
        my_bets = Bet.objects.filter(uid=request.user).select_related('optid__topicid')
        my_created_topics = Topic.objects.filter(uid_id=request.user.id).prefetch_related('options').order_by('-topicid')
        profile, created = AccountProfile.objects.get_or_create(
            uid=request.user, 
            defaults={'name': request.user.username, 'currentpoint': 1000}
        )

    # テンプレートに送るデータをまとめる
    context = {
        'topics': topics,
        'my_bets': my_bets,
        'profile': profile,
        'my_created_topics': my_created_topics,
        'ranking_list': ranking_list, 
        'now': timezone.now(), 
    }
    return render(request, 'bookmaker/index.html', context)


# ==========================================
# 2. お題の詳細 ＆ 投票（ベット）処理画面
# ==========================================
@login_required
def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, topicid=topic_id)
    options = topic.options.all()
    
    # ログイン中のユーザーのプロフィールを取得
    profile, created = AccountProfile.objects.get_or_create(
        uid=request.user, 
        defaults={'name': request.user.username, 'currentpoint': 3000}
    )

    if request.method == 'POST':
        opt_id = request.POST.get('option_id')
        try:
            bet_point = int(request.POST.get('bet_point', 0))
        except ValueError:
            bet_point = 0

        if not opt_id or bet_point <= 0:
            messages.error(request, '正しい選択肢と1ポイント以上の賭け金を入力してください。')
            return redirect('bookmaker:topic_list')

        if profile.currentpoint < bet_point:
            messages.error(request, f'ポイントが足りません！（現在の持ちポイント: {profile.currentpoint}pt）')
            return redirect('bookmaker:topic_list')

        option = get_object_or_404(Option, optid=opt_id, topicid=topic)

        # 賭け金DB（Bet）に保存
        bet, bet_created = Bet.objects.get_or_create(
            uid=request.user,
            optid=option,
            defaults={'betpoint': 0}
        )
        
        profile.currentpoint -= bet_point
        bet.betpoint += bet_point
        
        profile.save()
        bet.save()

        # ─── 🚨 【追加】高額ベット時の掲示板自動投稿ロジック ───
        HIGH_BET_THRESHOLD = 3000  # 💡 何ポイント以上を高額とするか設定（例: 500pt）
        
        if bet_point >= HIGH_BET_THRESHOLD:
            try:
                system_user = User.objects.get(username='公式ディーラー')
            except User.DoesNotExist:
                system_user = request.user

            auto_message = f"【高額ベット】{request.user.username}さんが「{option.text}」に {bet_point}ポイント 賭けました！"
            
            Chat.objects.create(
                uid=system_user,      
                text=auto_message,
                shared_topic=topic
            )

        messages.success(request, f'「{option.text}」に {bet_point}pt 賭けました！')
        return redirect('bookmaker:topic_list')

    return render(request, 'bookmaker/index.html', {
        'topic': topic,
        'options': options,
        'profile': profile
    })


# ==========================================
# 3-A. 掲示板：新しく投稿する処理（POST専用）
# ==========================================
@login_required
def create_chat(request):
    if request.method == 'POST':
        chat_text = request.POST.get('chat_text')
        topic_id = request.POST.get('topic_id')  # 💡画面から送られてきた「引用お題のID」を取得

        if chat_text:
            # データベースにチャットを保存
            chat = Chat(
                uid=request.user, 
                text=chat_text
            )
            
            if topic_id:
                try:
                    chat.shared_topic = Topic.objects.get(topicid=topic_id)
                except Topic.DoesNotExist:
                    pass 

            if request.FILES.get('chat_image'):
                chat.image = request.FILES['chat_image']

            chat.save()
            
    return redirect('top_page')


# ==========================================
# 3-A-3. 掲示板：投稿への返信処理
# ==========================================
@login_required
def create_reply(request, chat_id):
    if request.method == 'POST':
        text = request.POST.get('reply_text', '').strip()
        if text:
            chat = get_object_or_404(Chat, pk=chat_id)
            Reply.objects.create(uid=request.user, chat=chat, text=text)

    return redirect('top_page')


# ==========================================
# 3-A-2. 掲示板：投稿削除処理
# ==========================================
@login_required
def delete_chat(request, chat_id):
    if request.method == 'POST':
        chat = get_object_or_404(Chat, pk=chat_id)
        if chat.uid != request.user:
            messages.error(request, 'この投稿は削除できません。')
            return redirect('top_page')

        chat.delete()
        messages.success(request, '投稿を削除しました。')

    return redirect('top_page')


# ==========================================
# 3-B. 掲示板：画面を表示する処理（表示 ＆ %検索% 専用）
# ==========================================
@login_required
def top_board(request):
    search_query = request.GET.get('q', '').strip()  # 前後の余計な空白を消す

    # 💡「.select_related('shared_topic', 'uid')」でユーザーとお題データを一括取得して高速化
    replies_prefetch = Prefetch(
        'replies',
        queryset=Reply.objects.select_related('uid', 'parent').prefetch_related('child_replies__uid'),
    )
    chats_queryset = Chat.objects.all().select_related('shared_topic', 'uid').prefetch_related(replies_prefetch).order_by('-time')

    # 🔍 検索ワードがある場合、Python側で「含まれているか」をチェック
    if search_query:
        query_lower = search_query.lower()
        filtered_chats = []
        for chat in chats_queryset:
            # 1. 本文に含まれるか
            in_text = query_lower in chat.text.lower()
            
            # 2. ユーザー名に含まれるか
            in_username = query_lower in str(chat.uid.username).lower()
            
            # 3. 引用お題のタイトルに含まれるか（お題がある場合のみ）
            in_topic = False
            if chat.shared_topic and chat.shared_topic.topictitle:
                in_topic = query_lower in chat.shared_topic.topictitle.lower()
            
            # いずれかに「含まれていれば」リストに残す
            if in_text or in_username or in_topic:
                filtered_chats.append(chat)
        
        # 絞り込んだ結果をテンプレートに渡す
        chats = filtered_chats
    else:
        # 検索キーワードがない（通常アクセス）の時は、全件をそのまま使う
        chats = chats_queryset
    
    for chat in chats:
        chat.top_replies = sorted(
            [reply for reply in chat.replies.all() if reply.parent_id is None],
            key=lambda r: r.time
        )
        chat.reply_count = len(chat.top_replies)
    
    # 💡投稿フォームのドロップダウンに表示するため、現在受付中のお題リストを取得
    active_topics = Topic.objects.filter(
        status='open', 
        deadtime__gt=timezone.now()
    ).order_by('-deadtime')

    return render(request, 'top_board.html', {
        'chats': chats, 
        'active_topics': active_topics,
        'search_query': search_query,
    })


# ==========================================
# 4. 掲示板のリアクション機能（いいね等）
# ==========================================
@login_required
def toggle_reaction(request, chat_id):
    if request.method == 'POST':
        # 該当するチャットを取得
        chat = Chat.objects.get(pk=chat_id)
        
        # 自分がすでにこのチャットにリアクションしているか探す
        existing_reaction = Reaction.objects.filter(uid=request.user, chatid=chat)
        
        if existing_reaction.exists():
            # すでにリアクションがあれば、クリックで「解除（削除）」する
            existing_reaction.delete()
        else:
            # なければ、新しくリアクションを「登録（保存）」する
            Reaction.objects.create(uid=request.user, chatid=chat)
        
        redirect_url = reverse('top_page') + f'#chat-{chat.chatid}'
        return redirect(redirect_url)
            
    # 処理が終わったら元の掲示板トップに戻る
    return redirect('top_page')


# ==========================================
# 5. お題の結果（答え）を確定させる処理 ＆ 強制終了処理
# ==========================================
@login_required
def set_topic_result(request, topic_id):
    if request.method == 'POST':
        # 自分が作ったお題を「uid_id」形式で安全・確実に取得
        topic = get_object_or_404(Topic, topicid=topic_id, uid_id=request.user.id)
        
        # すでにクローズされているお題なら処理をしない（二重配当の防止）
        if topic.status == 'closed':
            messages.error(request, 'このお題はすでに結果が確定しています。')
            return redirect('bookmaker:topic_list')

        # ─── 📥 【受付の強制終了（切り上げ）処理】 ───
        if 'force_close' in request.POST:
            topic.deadtime = timezone.now()  # 期限を現在のシステム時刻に上書き
            topic.save()
            messages.success(request, f'お題「{topic.topictitle}」の受付を強制終了しました。結果を確定させてください。')
            return redirect('bookmaker:topic_list')

        # ─── 🏆 【通常の結果確定処理】 ───
        winning_opt_id = request.POST.get('winning_option')

        if winning_opt_id:
            # 1. まずこのお題に紐づくすべての選択肢の正解フラグを一度 False にリセット
            topic.options.all().update(is_correct=False)
            
            # 2. 選ばれた正解の選択肢だけを True にする
            winning_option = get_object_or_404(Option, optid=winning_opt_id, topicid=topic)
            winning_option.is_correct = True
            winning_option.save()

            # ─── 💰 【自動配当（ポイント返却）ロジック】 ───
            
            # A. お題全体の総プールポイントを計算
            total_pool = 0
            for opt in topic.options.all():
                total_pool += sum(b.betpoint for b in opt.bet_set.all())

            # B. 正解の選択肢に賭けられた総ポイントを計算
            winning_pool = sum(b.betpoint for b in winning_option.bet_set.all())

            # C. 正解者にポイントを分配
            if total_pool > 0 and winning_pool > 0:
                # 正解の選択肢へのすべての賭け（Bet）データを取得
                winning_bets = winning_option.bet_set.all()
                
                for bet in winning_bets:
                    # プレイヤーごとの配当を計算（傾斜配当：自分の賭け金 × オッズ）
                    # 小数点以下でポイントがブレないよう、四捨五入（round）して整数にします
                    payout = round((total_pool / winning_pool) * bet.betpoint)
                    
                    if payout > 0:
                        # 賭けたユーザーのプロフィールを取得してポイントを加算
                        user_profile, created = AccountProfile.objects.get_or_create(
                            uid=bet.uid,
                            defaults={'name': bet.uid.username, 'currentpoint': 1000}
                        )
                        user_profile.currentpoint += payout
                        user_profile.save()
            
            # ─── 💰 【配当処理ここまで】 ───

            # 3. お題のステータスを「クローズ（終了）」にする
            topic.status = 'closed'
            topic.save()
            
            messages.success(request, f'お題「{topic.topictitle}」の結果を【{winning_option.text}】に確定し、正解者へポイントを配当しました！')
            
    return redirect('bookmaker:topic_list')


@login_required
def get_users_json(request):
    users = User.objects.exclude(id=request.user.id).values_list('username', flat=True)
    return JsonResponse({'users': list(users)})