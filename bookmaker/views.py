from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AccountProfile, Bet, Chat, Option, Reaction, Reply, Topic
from .services import (
    create_topic_from_request,
    get_active_topics_queryset,
    get_or_create_profile,
    get_ranking_list,
    get_user_bets,
    get_user_created_topics,
)
from django.urls import reverse


def get_display_name(user: User) -> str:
    if not user:
        return ''

    try:
        return user.profile.name
    except Exception:
        return user.username

# ==========================================
# 1. お題の一覧画面 ＆ 新規投稿処理
# ==========================================
def topic_list(request):
    if request.method == 'POST' and 'topictitle' in request.POST:
        if not request.user.is_authenticated:
            messages.error(request, '投稿にはログインが必要です。')
            return redirect('login')

        create_topic_from_request(request)
        messages.success(request, '新しいお題を公開しました！')
        return redirect('bookmaker:topic_list')

    topics = Topic.objects.all().order_by('-deadtime')
    for topic in topics:
        if topic.uid:
            topic.display_author_name = get_display_name(topic.uid)

    my_bets = None
    profile = None
    my_created_topics = None

    if request.user.is_authenticated:
        my_bets = get_user_bets(request.user)
        my_created_topics = get_user_created_topics(request.user)
        profile = get_or_create_profile(request.user)

    context = {
        'topics': topics,
        'my_bets': my_bets,
        'profile': profile,
        'my_created_topics': my_created_topics,
        'ranking_list': get_ranking_list(),
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
    profile = get_or_create_profile(request.user)

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
            system_user, created = User.objects.get_or_create(
                username='公式ディーラー',
                defaults={'is_active': False},
            )

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
        chat_text = request.POST.get('chat_text', '').strip()
        topic_id = request.POST.get('topic_id')

        if chat_text:
            chat = Chat(uid=request.user, text=chat_text)

            if topic_id:
                try:
                    chat.shared_topic = Topic.objects.get(topicid=topic_id)
                except Topic.DoesNotExist:
                    pass

            chat_image = request.FILES.get('chat_image')
            if chat_image:
                chat.image = chat_image

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
def _filter_chats_by_query(chats_queryset, search_query):
    if not search_query:
        return list(chats_queryset)

    query_lower = search_query.lower()
    filtered_chats = []
    for chat in chats_queryset:
        in_text = query_lower in chat.text.lower()
        in_username = query_lower in str(chat.uid.username).lower()
        in_display_name = query_lower in get_display_name(chat.uid).lower()
        in_topic = bool(chat.shared_topic and chat.shared_topic.topictitle and query_lower in chat.shared_topic.topictitle.lower())

        if in_text or in_username or in_display_name or in_topic:
            filtered_chats.append(chat)

    return filtered_chats


@login_required
def top_board(request):
    search_query = request.GET.get('q', '').strip()

    replies_prefetch = Prefetch(
        'replies',
        queryset=Reply.objects.select_related('uid', 'parent').prefetch_related('child_replies__uid'),
    )
    chats_queryset = Chat.objects.all().select_related('shared_topic', 'uid__profile').prefetch_related(replies_prefetch).order_by('-time')
    chats = _filter_chats_by_query(chats_queryset, search_query)

    for chat in chats:
        chat.display_user_name = get_display_name(chat.uid)
        chat.top_replies = sorted(
            [reply for reply in chat.replies.all() if reply.parent_id is None],
            key=lambda reply: reply.time,
        )
        chat.reply_count = len(chat.top_replies)

        for reply in chat.top_replies:
            reply.display_user_name = get_display_name(reply.uid)
            for child in reply.child_replies.all():
                child.display_user_name = get_display_name(child.uid)

    active_topics = get_active_topics_queryset()

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
        chat = get_object_or_404(Chat, pk=chat_id)
        existing_reaction = Reaction.objects.filter(uid=request.user, chatid=chat).first()

        if existing_reaction:
            existing_reaction.delete()
        else:
            Reaction.objects.create(uid=request.user, chatid=chat)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            usernames = [r.uid.username for r in chat.reactions.select_related('uid').all()]
            return JsonResponse({
                'status': 'success',
                'new_count': chat.reactions.count(), 
                'usernames': usernames,
                })

        
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