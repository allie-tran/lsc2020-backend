from django.urls import path

from . import views

urlpatterns = [
    path('images/', views.images),
    path('timeline/', views.timeline),
    path('timeline/more_scene/', views.more_scenes),
    path('timeline/group/', views.timeline_group),
    path('timeline/info/', views.detailed_info),
    path('more/', views.more),
    path('gps/', views.gps),
    path('similar', views.similar),
    path('login', views.login),
    path('submit', views.export),
    path('submit_saved/', views.submit_all),
    path('restart', views.restart),
    path('query_list/', views.aaron)]
