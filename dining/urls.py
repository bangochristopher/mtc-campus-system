from django.urls import path
from .views import ScanView, RegisterListView, DashboardView, EligibleView, NewTermView

urlpatterns = [
    path('scan/',       ScanView.as_view()),
    path('register/',   RegisterListView.as_view()),
    path('dashboard/',  DashboardView.as_view()),
    path('eligible/',   EligibleView.as_view()),
    path('new-term/',   NewTermView.as_view()),
]