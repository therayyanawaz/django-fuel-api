from django.urls import path
from .views import FuelRouteAPIView

urlpatterns = [
    path('fuel-route/', FuelRouteAPIView.as_view()),
]