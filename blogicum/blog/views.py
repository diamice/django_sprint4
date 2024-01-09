from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.db.models import Count
from django.http import Http404

from .models import Post, Category, Comment
from .forms import ProfileForm, PostForm, CommentForm

POSTS_ON_PAGE = 10


class PostListView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = POSTS_ON_PAGE

    def get_queryset(self):
        return (
            Post.objects.select_related(
                'author',
                'category',
                'location')
            .filter(
                is_published=True,
                category__is_published=True,
                pub_date__lte=timezone.now())
            .annotate(comment_count=Count('comments'))
            .order_by('-pub_date'))


class PostMixin:
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'


class DispatchPostMixin:
    def dispatch(self, request, *args, **kwargs):
        instance = get_object_or_404(Post, pk=kwargs['pk'])
        if instance.author != request.user:
            return redirect('blog:post_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)


class PostCreateView(LoginRequiredMixin, PostMixin, CreateView):
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', args=(self.request.user,))


class PostUpdateView(LoginRequiredMixin, PostMixin,
                     DispatchPostMixin, UpdateView):
    def get_success_url(self):
        return reverse('blog:post_detail', args=(self.object.id,))


class PostDeleteView(LoginRequiredMixin, PostMixin,
                     DispatchPostMixin, DeleteView):
    def get_success_url(self):
        return reverse('blog:profile', args=(self.request.user,))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = PostForm(instance=self.object)
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'

    def get_object(self, queryset=None):
        post_object = get_object_or_404(Post, pk=self.kwargs['pk'])
        if post_object.author != self.request.user:
            if (post_object.category.is_published
                    and post_object.pub_date <= timezone.now()
                    and post_object.is_published):
                return post_object
            raise Http404()
        return post_object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        context['comments'] = (
            Comment.objects.select_related('author')
            .filter(post_id=self.kwargs['pk'])
            .order_by('created_at'))
        return context


class CategoryPostListView(ListView):
    model = Category
    template_name = 'blog/category.html'
    paginate_by = POSTS_ON_PAGE

    def get_queryset(self):
        category = get_object_or_404(Category,
                                     slug=self.kwargs['category_slug'],
                                     is_published=True)
        return (
            Post.objects
            .filter(is_published=True,
                    category=category,
                    pub_date__lte=timezone.now())
            .annotate(comment_count=Count('comments'))
            .order_by('-pub_date'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = Category.objects.get(
            slug=self.kwargs['category_slug']
        )
        return context


class ProfileListView(ListView):
    model = User
    paginate_by = POSTS_ON_PAGE
    template_name = 'blog/profile.html'

    def get_queryset(self):
        return (
            Post.objects
            .select_related('author')
            .filter(author__username=self.kwargs['username'])
            .annotate(comment_count=Count('comments'))
            .order_by('-pub_date', ))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_object_or_404(
            User, username=self.kwargs['username']
        )
        return context


class EditProfileUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'blog/user.html'
    form_class = ProfileForm

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile', args=(self.request.user,))


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    template_name = 'blog/comment.html'
    form_class = CommentForm
    post_object = None

    def dispatch(self, request, *args, **kwargs):
        self.post_object = get_object_or_404(Post, pk=kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = self.post_object
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'pk': self.kwargs['post_id']})


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', pk=post_id)


@login_required
def edit_comment(request, post_id, comment_id):
    instance = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    if request.user != instance.author:
        return redirect('blog:post_detail', pk=post_id)
    form = CommentForm(request.POST or None, instance=instance)
    context = {
        'form': form,
        'comment': instance,
    }
    if form.is_valid():
        comment = form.save(commit=False)
        comment.save()
        return redirect('blog:post_detail', pk=post_id)
    return render(request, 'blog/comment.html', context)


@login_required
def delete_comment(request, post_id, comment_id):
    instance = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    if request.user != instance.author:
        return redirect('blog:post_detail', pk=post_id)
    context = {
        'comment': instance,
    }
    if request.method == 'POST':
        instance.delete()
        return redirect('blog:post_detail', pk=post_id)
    return render(request, 'blog/comment.html', context)
