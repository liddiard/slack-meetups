"""meetups URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

from matcher import views


urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("admin/", admin.site.urls, name="admin"),
    path("slack/action/", views.handle_slack_action, name="slack_action"),
    path("slack/message/", views.handle_slack_message, name="slack_message"),
    path("api/stats/<channel_name>/", views.get_pool_stats,
        name="pool_stats"),
    path("stats/<channel_name>/",
        TemplateView.as_view(template_name="pool_stats.html"),
        name="pool_stats"),
    path("utils/members/<channel_id>/", views.get_channel_members,
        name="channel_members")
]
