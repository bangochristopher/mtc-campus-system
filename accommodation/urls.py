from django.urls import path
from .views import (
    HostelListCreateView, HostelDetailView,
    ApplyView, StatusView, RoomReservationsView,
    AdminAppListView, ApproveView, RejectView, ResidentListView,
    DashboardView, NewSemesterView, RecalculateBedsView,
    FloorListCreateView, FloorDetailView,
    RoomListCreateView, RoomDetailView,
)

urlpatterns = [
    path('hostels/',                              HostelListCreateView.as_view()),
    path('hostels/<int:pk>/',                     HostelDetailView.as_view()),
    path('apply/',                                ApplyView.as_view()),
    path('status/',                               StatusView.as_view()),
    path('room-reservations/',                    RoomReservationsView.as_view()),
    path('admin/dashboard/',                      DashboardView.as_view()),
    path('admin/applications/',                   AdminAppListView.as_view()),
    path('admin/applications/<int:pk>/approve/',  ApproveView.as_view()),
    path('admin/applications/<int:pk>/reject/',   RejectView.as_view()),
    path('admin/residents/',                      ResidentListView.as_view()),
    path('admin/new-semester/',                   NewSemesterView.as_view()),
    path('admin/recalculate-beds/',               RecalculateBedsView.as_view()),
    
    # Floor management
    path('admin/floors/',                         FloorListCreateView.as_view()),
    path('admin/floors/<int:pk>/',                FloorDetailView.as_view()),
    
    # Room management
    path('admin/rooms/',                          RoomListCreateView.as_view()),
    path('admin/rooms/<int:pk>/',                 RoomDetailView.as_view()),
]