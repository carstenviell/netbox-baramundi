from django.urls import path

from . import views

app_name = 'netbox_baramundi'

urlpatterns = (
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('settings/test/', views.TestConnectionView.as_view(), name='test_connection'),
    path('endpoint-sync/', views.EndpointSyncView.as_view(), name='endpoint_sync'),

    path('sync/devices/', views.DeviceSyncOverviewView.as_view(), name='sync_devices'),
    path('sync/vms/', views.VMSyncOverviewView.as_view(), name='sync_vms'),
    path('sync/<str:kind>/bulk/', views.BulkEndpointSyncView.as_view(), name='bulk_sync'),

    path('orphans/', views.OrphanListView.as_view(), name='orphan_list'),
    path('orphans/refresh/', views.RefreshOrphansView.as_view(), name='orphan_refresh'),
    path('orphans/bulk-import/', views.BulkImportOrphansView.as_view(), name='orphan_bulk_import'),
    path('orphans/<int:pk>/assign/', views.AssignOrphanView.as_view(), name='orphan_assign'),
    path('orphans/<int:pk>/import/', views.ImportOrphanView.as_view(), name='orphan_import'),
    path('orphans/<int:pk>/ignore/', views.IgnoreOrphanView.as_view(), name='orphan_ignore'),
)
