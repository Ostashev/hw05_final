from django.contrib.auth import get_user_model
from django import forms

from .models import Post, Comment

User = get_user_model()


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('text', 'group', 'image')
        help_text = {
            'text': 'Содержание поста',
            'group': 'Группа',
            'image': 'Картинка'
        }
        labels = {'text': 'Текст', 'group': 'Группа', 'image': 'Картинка'}


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text',)
        help_text = {'text': 'Введите текст комментария'}
        labels = {'text': 'Комментарий'}
