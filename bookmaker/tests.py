from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

# ログイン済みでトップページを開いたとき、レスポンスにユーザー名が含まれるかを確認するテスト
class TopBoardHeaderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='secret1234')

    def test_header_shows_authenticated_username(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('top_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tester')
