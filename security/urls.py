from django.urls import path
from .views import ScanView, LogListView, OnCampusView, IncidentListView, DashboardView, NewTermView

urlpatterns = [
    path('scan/',       ScanView.as_view()),
    path('logs/',       LogListView.as_view()),
    path('on-campus/',  OnCampusView.as_view()),
    path('incidents/',  IncidentListView.as_view()),
    path('dashboard/',  DashboardView.as_view()),
    path('new-term/',   NewTermView.as_view()),
]