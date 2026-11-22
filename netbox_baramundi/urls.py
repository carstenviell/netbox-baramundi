from django.urls import path

from . import views

app_name = 'netbox_baramundi'

urlpatterns = (
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('settings/test/', views.TestConnectionView.as_view(), name='test_connection'),
    path('endpoint-sync/', views.EndpointSyncView.as_view(), name='endpoint_sync'),
)
