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


# ユーザーに紐づく表示名を取得する。
def get_display_name(user: User) -> str:
    # 受け取ったユーザーが空なら空文字を返す。
    if not user:
        return ''
    # もしプロフィールの name があればそれを使う。
    try:
        return user.profile.name
    # プロフィールが存在しなければ username を表示名として使う。
    except Exception:
        return user.username


# ブックメーカー画面の一覧を表示する。
@login_required
def topic_list(request):
    # POSTでお題タイトルが送られてきたら新規投稿として処理する。
    if request.method == 'POST' and 'topictitle' in request.POST:
        # services.pyの関数でお題を作る。
        create_topic_from_request(request)
        # 成功メッセージを表示して一覧へ戻る。
        messages.success(request, '新しいお題を公開しました！')
        return redirect('bookmaker:topic_list')

    # すべてのお題を期限の新しい順に取得する。
    topics = Topic.objects.all().order_by('-deadtime')
    # 取得した各お題に、作成者名の表示用文字列を付ける。
    for topic in topics:
        if topic.uid:
            topic.display_author_name = get_display_name(topic.uid)

    # 画面に渡す変数を初期化する。
    my_bets = None
    profile = None
    my_created_topics = None

    # 自分のベット・作成済みお題・プロフィールを取得する。
    my_bets = get_user_bets(request.user)
    my_created_topics = get_user_created_topics(request.user)
    profile = get_or_create_profile(request.user)

    # テンプレートへ渡すコンテキストを作る。
    context = {
        'topics': topics,
        'my_bets': my_bets,
        'profile': profile,
        'my_created_topics': my_created_topics,
        'ranking_list': get_ranking_list(),
        'now': timezone.now(),
    }
    # HTMLテンプレートを描画して返す。
    return render(request, 'bookmaker/index.html', context)



# 指定のお題に対してベットを行う。
@login_required
def topic_detail(request, topic_id):
    # topic_id から対象のお題を取得する。
    topic = get_object_or_404(Topic, topicid=topic_id)
    # お題に紐づく選択肢を取得する。
    options = topic.options.all()
    # 現在のユーザーのプロフィールを取得する。
    profile = get_or_create_profile(request.user)

    # POSTで送られてきた場合だけベット処理を行う。
    if request.method == 'POST':
        # POSTデータから選択肢IDを取り出す。
        opt_id = request.POST.get('option_id')
        # ベットポイントを整数に変換する。
        try:
            bet_point = int(request.POST.get('bet_point', 0))
        except ValueError:
            bet_point = 0

        # 選択肢がないか、ポイントが0以下ならエラーにする。
        if not opt_id or bet_point <= 0:
            messages.error(request, '正しい選択肢と1ポイント以上の賭け金を入力してください。')
            return redirect('bookmaker:topic_list')

        # 所持ポイントが不足していればベットさせない。
        if profile.currentpoint < bet_point:
            messages.error(request, f'ポイントが足りません！（現在の持ちポイント: {profile.currentpoint}pt）')
            return redirect('bookmaker:topic_list')

        # 対象の選択肢を取得する。
        option = get_object_or_404(Option, optid=opt_id, topicid=topic)

        # 既存のベットがあれば更新し、なければ新規作成する。
        bet, _ = Bet.objects.get_or_create(
            uid=request.user,
            optid=option,
            defaults={'betpoint': 0}
        )

        # ユーザーの所持ポイントを減らし、ベット金額を加算する。
        profile.currentpoint -= bet_point
        bet.betpoint += bet_point

        # 変更内容を保存する。
        profile.save()
        bet.save()

        # 高額ベットなら自動投稿を作る。
        HIGH_BET_THRESHOLD = 3000
        if bet_point >= HIGH_BET_THRESHOLD:
            # 公式ディーラー用のユーザーを取得または作成する。
            system_user, _ = User.objects.get_or_create(
                username='公式ディーラー',
                defaults={'is_active': False},
            )

            # 自動投稿の本文を作る。
            auto_message = f"【高額ベット】{request.user.username}さんが「{option.text}」に {bet_point}ポイント 賭けました！"

            # 投稿としてチャットを作成する。
            Chat.objects.create(
                uid=system_user,
                text=auto_message,
                shared_topic=topic
            )

        # 成功メッセージを出して一覧画面へ戻る。
        messages.success(request, f'「{option.text}」に {bet_point}pt 賭けました！')
        return redirect('bookmaker:topic_list')

    # GETアクセスならお題詳細画面を表示する。
    return render(request, 'bookmaker/index.html', {
        'topic': topic,
        'options': options,
        'profile': profile
    })




# 掲示板に新しい投稿を作成する。
@login_required
def create_chat(request):
    # POSTで送られてきたときだけ処理する。
    if request.method == 'POST':
        # 投稿本文を取り出す。
        chat_text = request.POST.get('chat_text', '').strip()
        # 付けられたお題IDを取り出す。
        topic_id = request.POST.get('topic_id')

        # 本文が空でなければ投稿を作る。
        if chat_text:
            # 新しい Chat オブジェクトを作成する。
            chat = Chat(uid=request.user, text=chat_text)

            # お題が選ばれていれば関連付ける。
            if topic_id:
                try:
                    chat.shared_topic = Topic.objects.get(topicid=topic_id)
                except Topic.DoesNotExist:
                    pass

            # 画像ファイルがあれば保存する。
            chat_image = request.FILES.get('chat_image')
            if chat_image:
                chat.image = chat_image

            # データベースに保存する。
            chat.save()

    # 投稿後は掲示板画面へ戻る。
    return redirect('top_page')




# 投稿に対して返信を作成する。
@login_required
def create_reply(request, chat_id):
    # POSTで送られてきたときだけ処理する。
    if request.method == 'POST':
        # 返信本文を取り出す。
        text = request.POST.get('reply_text', '').strip()
        # 本文が空でなければ返信を作る。
        if text:
            # 対象の投稿を取得する。
            chat = get_object_or_404(Chat, pk=chat_id)
            # Reply を作成して保存する。
            Reply.objects.create(uid=request.user, chat=chat, text=text)

    # 返信後は掲示板へ戻る。
    return redirect('top_page')




# 自分が作成した投稿だけを削除する。
@login_required
def delete_chat(request, chat_id):
    # POSTで送られてきたときだけ削除処理を行う。
    if request.method == 'POST':
        # 対象の投稿を取得する。
        chat = get_object_or_404(Chat, pk=chat_id)
        # 投稿者本人でなければ削除できないようにする。
        if chat.uid != request.user:
            messages.error(request, 'この投稿は削除できません。')
            return redirect('top_page')

        # 投稿を削除する。
        chat.delete()
        # 成功メッセージを出す。
        messages.success(request, '投稿を削除しました。')

    # 処理後は掲示板へ戻る。
    return redirect('top_page')




# 検索条件に応じて投稿を絞り込む。
def _filter_chats_by_query(chats_queryset, search_query):
    # 検索ワードが空ならそのまま返す。
    if not search_query:
        return list(chats_queryset)

    # 検索語を小文字に統一する。
    query_lower = search_query.lower()
    filtered_chats = []
    # 各投稿について、本文・投稿者名・表示名・引用お題に一致するか確認する。
    for chat in chats_queryset:
        in_text = query_lower in chat.text.lower()
        in_username = query_lower in str(chat.uid.username).lower()
        in_display_name = query_lower in get_display_name(chat.uid).lower()
        in_topic = bool(chat.shared_topic and chat.shared_topic.topictitle and query_lower in chat.shared_topic.topictitle.lower())

        # いずれかに一致すれば結果に追加する。
        if in_text or in_username or in_display_name or in_topic:
            filtered_chats.append(chat)

    return filtered_chats


# 掲示板の画面全体を組み立てる。
@login_required
def top_board(request):
    # 検索クエリを取り出す。
    search_query = request.GET.get('q', '').strip()

    # 返信をまとめて取りたいのでプリフェッチを設定する。
    replies_prefetch = Prefetch(
        'replies',
        queryset=Reply.objects.select_related('uid', 'parent').prefetch_related('child_replies__uid'),
    )
    # 投稿一覧を時系列の新しい順で取得する。
    chats_queryset = Chat.objects.all().select_related('shared_topic', 'uid__profile').prefetch_related(replies_prefetch).order_by('-time')
    # 検索条件に応じて投稿を絞り込む。
    chats = _filter_chats_by_query(chats_queryset, search_query)

    # 各投稿に表示用の情報を付ける。
    for chat in chats:
        # 投稿者の表示名を設定する。
        chat.display_user_name = get_display_name(chat.uid)
        # 返信のうち親返信だけを取り出して時系列順に並べる。
        chat.top_replies = sorted(
            [reply for reply in chat.replies.all() if reply.parent_id is None],
            key=lambda reply: reply.time,
        )
        # 親返信の数を保存する。
        chat.reply_count = len(chat.top_replies)

        # 各返信・子返信にも表示名を付ける。
        for reply in chat.top_replies:
            reply.display_user_name = get_display_name(reply.uid)
            for child in reply.child_replies.all():
                child.display_user_name = get_display_name(child.uid)

    # 有効なお題一覧を取得する。
    active_topics = get_active_topics_queryset()

    # テンプレートへ表示用データを渡す。
    return render(request, 'top_board.html', {
        'chats': chats,
        'active_topics': active_topics,
        'search_query': search_query,
    })




# 投稿に対するリアクションを付けたり外したりする。
@login_required
def toggle_reaction(request, chat_id):
    # POSTで送られてきたときだけ処理する。
    if request.method == 'POST':
        # 対象の投稿を取得する。
        chat = get_object_or_404(Chat, pk=chat_id)
        # すでにリアクションしているか確認する。
        existing_reaction = Reaction.objects.filter(uid=request.user, chatid=chat).first()

        # すでにあれば削除し、なければ新規作成する。
        if existing_reaction:
            existing_reaction.delete()
        else:
            Reaction.objects.create(uid=request.user, chatid=chat)

        # XMLHttpRequest なら JSON を返す。
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            usernames = [r.uid.username for r in chat.reactions.select_related('uid').all()]
            return JsonResponse({
                'status': 'success',
                'new_count': chat.reactions.count(),
                'usernames': usernames,
            })

        # 通常のリクエストなら掲示板へ戻る。
        redirect_url = reverse('top_page') + f'#chat-{chat.chatid}'
        return redirect(redirect_url)

    # POST以外なら掲示板トップへ戻る。
    return redirect('top_page')




# お題の結果を確定して、配当処理を行う。
@login_required
def set_topic_result(request, topic_id):
    # POSTで送られてきたときだけ処理する。
    if request.method == 'POST':
        # そのユーザーが作成したお題だけを安全に取得する。
        topic = get_object_or_404(Topic, topicid=topic_id, uid_id=request.user.id)

        # すでに終了済みなら処理しない。
        if topic.status == 'closed':
            messages.error(request, 'このお題はすでに結果が確定しています。')
            return redirect('bookmaker:topic_list')

        # 強制終了のリクエストなら締め切り時間を今にして終了扱いにする。
        if 'force_close' in request.POST:
            topic.deadtime = timezone.now()
            topic.save()
            messages.success(request, f'お題「{topic.topictitle}」の受付を強制終了しました。結果を確定させてください。')
            return redirect('bookmaker:topic_list')

        # 結果を確定する選択肢IDを取得する。
        winning_opt_id = request.POST.get('winning_option')

        # 選択肢があれば結果確定処理を行う。
        if winning_opt_id:
            # まず全選択肢の正解フラグを外す。
            topic.options.all().update(is_correct=False)

            # 正解となる選択肢だけを正解にする。
            winning_option = get_object_or_404(Option, optid=winning_opt_id, topicid=topic)
            winning_option.is_correct = True
            winning_option.save()

            # お題全体の賭け金総額を計算する。
            total_pool = 0
            for opt in topic.options.all():
                total_pool += sum(b.betpoint for b in opt.bet_set.all())

            # 正解選択肢に賭けられた金額を計算する。
            winning_pool = sum(b.betpoint for b in winning_option.bet_set.all())

            # 正解者に配当ポイントを振り込む。
            if total_pool > 0 and winning_pool > 0:
                winning_bets = winning_option.bet_set.all()

                for bet in winning_bets:
                    # そのベットに対する配当額を計算する。
                    payout = round((total_pool / winning_pool) * bet.betpoint)

                    if payout > 0:
                        # ベットしたユーザーのプロフィールを取得または作成する。
                        user_profile, _ = AccountProfile.objects.get_or_create(
                            uid=bet.uid,
                            defaults={'name': bet.uid.username, 'currentpoint': 1000}
                        )
                        user_profile.currentpoint += payout
                        user_profile.save()

            # お題の状態を終了済みに変更する。
            topic.status = 'closed'
            topic.save()

            # 完了メッセージを出す。
            messages.success(request, f'お題「{topic.topictitle}」の結果を【{winning_option.text}】に確定し、正解者へポイントを配当しました！')

    return redirect('bookmaker:topic_list')


# メンション候補として使えるユーザー一覧をJSONで返します。
@login_required
def get_users_json(request):
    users = User.objects.exclude(id=request.user.id).values_list('username', flat=True)
    return JsonResponse({'users': list(users)})