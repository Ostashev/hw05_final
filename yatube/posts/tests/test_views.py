import shutil
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django import forms

from posts.forms import PostForm
from ..models import Post, Group, Comment, Follow

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)

User = get_user_model()


class PostPagesTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='NoName')
        cls.user_2 = User.objects.create_user(username='2')
        cls.small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.small_gif,
            content_type='image/gif'
        )
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.group_new = Group.objects.create(
            title='Тестовая группа2',
            slug='test-slug2',
            description='Тестовое описание2',
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=cls.user,
            group=cls.group,
            image=cls.uploaded,
        )
        cls.comment = Comment.objects.create(
            text='Тестовый комментарий',
            author=cls.user,
            post=cls.post
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.authorized_client_2 = Client()
        self.authorized_client_2.force_login(self.user_2)

    def test_pages_uses_correct_template(self):
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse(
                'posts:group_list', kwargs={'slug': 'test-slug'}
            ): 'posts/group_list.html',
            reverse(
                'posts:profile', kwargs={'username': 'NoName'}
            ): 'posts/profile.html',
            reverse(
                'posts:post_detail', kwargs={'post_id': 1}
            ): 'posts/post_detail.html',
            reverse(
                'posts:post_edit', kwargs={'post_id': 1}
            ): 'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
        }
        for template, reverse_name in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(template)
                self.assertTemplateUsed(response, reverse_name)

    def test_index_page_show_correct_context(self):
        response = self.authorized_client.get(reverse('posts:index'))
        expected = list(Post.objects.all()[:10])
        self.assertEqual(list(response.context['page_obj']), expected)

    def test_group_page_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:group_list',
            kwargs={'slug': 'test-slug'}
        ))
        expected = list(Post.objects.filter(group=self.group)[:10])
        self.assertEqual(list(response.context['page_obj']), expected)

    def test_profile_page_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:profile',
            kwargs={'username': 'NoName'}
        ))
        expected = list(Post.objects.filter(author=self.user)[:10])
        self.assertEqual(list(response.context['page_obj']), expected)

    def test_post_detail_page_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:post_detail',
            kwargs={'post_id': self.post.id}
        ))
        field_context = {
            response.context.get('post').text: self.post.text,
            response.context.get('post').author: self.post.author,
            response.context.get('post').group: self.post.group,
            response.context.get('post').image: self.post.image,
        }
        for field, expected_value in field_context.items():
            with self.subTest(field=field):
                self.assertEqual(field, expected_value)

    def test_post_edit_page_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:post_edit',
            kwargs={'post_id': self.post.id},
        ))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.models.ModelChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        self.assertIn('is_edit', response.context)
        self.assertIs(response.context['is_edit'], True)
        self.assertIsInstance(response.context['form'], PostForm)

    def test_post_create_page_show_correct_context(self):
        response = self.authorized_client.get(reverse('posts:post_create'))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.models.ModelChoiceField,
            'image': forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        self.assertIsInstance(response.context['form'], PostForm)

    def test_create_post_in_self_group(self):
        """Проверяем создание поста на страницах с выбранной группой"""
        post_group = {
            reverse('posts:index'): self.post,
            reverse(
                'posts:group_list', kwargs={'slug': self.group.slug}
            ): self.post,
            reverse(
                'posts:profile',
                kwargs={'username': self.post.author}
            ): self.post,
        }
        for value, expected in post_group.items():
            with self.subTest(value=value):
                response = self.authorized_client.get(value)
                form_field = response.context['page_obj']
                self.assertIn(expected, form_field)

    def test_check_group_not_in_mistake_group_list_page(self):
        """Проверяем чтобы созданный Пост с группой не попап в чужую группу."""
        post_new = self.authorized_client.post(
            reverse('posts:post_create'),
            data={'text': 'Тестовый пост2', 'group': self.group.id},
            follow=True
        )
        self.assertEqual(Post.objects.filter(group=self.group_new).count(), 0)
        self.assertEqual(Post.objects.filter(group=self.group).count(), 2)
        self.assertNotIn(post_new, Post.objects.filter(group=self.group_new))

    def test_comment_on_post_page(self):
        """Комментариq создаетcя к Post и перенаправляет на post_detail"""
        comment_count = Comment.objects.count()
        form_data = {'text': 'Тестовый комментарий 2'}
        response = self.authorized_client.post(reverse(
            'posts:add_comment',
            kwargs={'post_id': self.post.id}),
            data=form_data, follow=True,
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail',
            kwargs={'post_id': self.post.id}
        ))
        self.assertEqual(Comment.objects.count(), comment_count + 1)
        self.assertTrue(
            Comment.objects.filter(text='Тестовый комментарий 2').exists()
        )

    def test_check_cache(self):
        """Проверка кеша."""
        response = self.authorized_client.get(reverse('posts:index'))
        cache_1 = response.content
        Post.objects.get(id=1).delete()
        response2 = self.authorized_client.get(reverse('posts:index'))
        cache_2 = response2.content
        self.assertEqual(cache_1, cache_2)
        cache.clear()
        response3 = self.authorized_client.get(reverse('posts:index'))
        cache_3 = response3.content
        self.assertNotEqual(cache_1, cache_3)

    def test_follow_authorized_page_index(self):
        """Проверка подписки авторизованного пользователя и вывод поста"""
        self.authorized_client_2.get(reverse(
            'posts:profile_follow',
            kwargs={'username': self.user.username}
        ))
        self.assertEqual(Follow.objects.count(), 1)
        response_follower = self.authorized_client_2.get(reverse(
            'posts:follow_index'
        ))
        self.assertIn(self.post, response_follower.context["page_obj"])

    def test_not_follow_authorized_page_index(self):
        """Проверка подписки автора поста на автора поста"""
        response_not_follower = self.authorized_client.get(reverse(
            'posts:follow_index'
        ))
        self.assertNotIn(self.post, response_not_follower.context["page_obj"])

    def test_unfollow_authorized(self):
        """Проверка отписки авторизованного пользователя"""
        self.authorized_client_2.get(reverse(
            'posts:profile_follow',
            kwargs={'username': self.user.username}
        ))
        self.authorized_client_2.get(reverse(
            'posts:profile_unfollow',
            kwargs={'username': self.user.username}
        ))
        self.assertEqual(Follow.objects.count(), 0)

    def test_image_context_index(self):
        """Картинка передается на страницу index"""
        response = self.authorized_client.get(reverse('posts:index'))
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_image_context_profile(self):
        """Картинка передается на страницу profile"""
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.user.username})
        )
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_image_context_group_list(self):
        """Картинка передается на страницу group_list"""
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group.slug})
        )
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_image_context_post_detail(self):
        """Картинка передается на страницу post_detail"""
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id})
        )
        obj = response.context['post']
        self.assertEqual(obj.image, self.post.image)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='NoName')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        objs = [
            Post(
                text=f'Тестовый пост {str(e)}',
                author=cls.user,
                group=cls.group,
            )
            for e in range(1, 14)
        ]
        cls.post = Post.objects.bulk_create(objs)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_first_page_contains_ten_records_index(self):
        """Проверка index: на первой странице должно быть 10 постов."""
        response = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_contains_three_records_index(self):
        """Проверка index: на второй странице должно быть три поста."""
        response = self.authorized_client.get(
            reverse('posts:index'), {'page': 2}
        )
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_first_page_contains_ten_records_group_list(self):
        """Проверка group_list: на первой странице должно быть 10 постов."""
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': 'test-slug'})
        )
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_contains_three_records_group_list(self):
        """Проверка group_list: на второй странице должно быть три поста."""
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}),
            {'page': 2}
        )
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_first_page_contains_ten_records_profile(self):
        """Проверка profile: на первой странице должно быть 10 постов."""
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.user.username})
        )
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_contains_three_records_profile(self):
        """Проверка profile: на второй странице должно быть три поста."""
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.user.username}),
            {'page': 2}
        )
        self.assertEqual(len(response.context['page_obj']), 3)
