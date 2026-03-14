from django.urls import path
from .views import (
    HostelListCreateView, HostelDetailView,
    ApplyView, StatusView,
    AdminAppListView, ApproveView, RejectView, ResidentListView,
    DashboardView, NewSemesterView,
)

urlpatterns = [
    path('hostels/',                              HostelListCreateView.as_view()),
    path('hostels/<int:pk>/',                     HostelDetailView.as_view()),
    path('apply/',                                ApplyView.as_view()),
    path('status/',                               StatusView.as_view()),
    path('admin/dashboard/',                      DashboardView.as_view()),
    path('admin/applications/',                   AdminAppListView.as_view()),
    path('admin/applications/<int:pk>/approve/',  ApproveView.as_view()),
    path('admin/applications/<int:pk>/reject/',   RejectView.as_view()),
    path('admin/residents/',                      ResidentListView.as_view()),
    path('admin/new-semester/',                   NewSemesterView.as_view()),
]