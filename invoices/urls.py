from django.urls import path
from . import views

app_name = 'invoices'

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Document Intake & List
    path('documents/', views.document_list_view, name='document_list'),
    path('documents/upload/', views.document_upload_view, name='document_upload'),
    path('documents/<int:document_id>/reprocess/', views.document_reprocess_view, name='document_reprocess'),
    path('documents/<int:document_id>/delete/', views.document_delete_view, name='document_delete'),

    # Human Review & Validation
    path('invoices/<int:invoice_id>/review/', views.invoice_review_view, name='invoice_review'),
    path('invoices/<int:invoice_id>/save/', views.invoice_save_view, name='invoice_save'),
    path('invoices/<int:invoice_id>/approve/', views.invoice_approve_view, name='invoice_approve'),
    path('invoices/<int:invoice_id>/reject/', views.invoice_reject_view, name='invoice_reject'),
    path('invoices/<int:invoice_id>/export/', views.invoice_export_view, name='invoice_export'),
    path('issues/<int:issue_id>/resolve/', views.issue_resolve_view, name='issue_resolve'),

    # Exception Queue
    path('exceptions/', views.exception_queue_view, name='exception_queue'),

    # Accounting Exports Ledger
    path('accounting/ledger/', views.export_ledger_view, name='export_ledger'),
    path('accounting/export-batch/', views.batch_export_view, name='batch_export'),
    path('accounting/retry/<int:export_id>/', views.retry_export_view, name='retry_export'),

    # Background Jobs Console
    path('jobs/', views.job_list_view, name='job_list'),
    path('jobs/process-now/', views.job_process_now_view, name='job_process_now'),
    path('jobs/<int:job_id>/retry/', views.job_retry_view, name='job_retry'),

    # JSON APIs
    path('api/suggest-account/', views.api_suggest_account_code, name='api_suggest_account'),
    path('api/job-status/<int:job_id>/', views.api_job_status, name='api_job_status'),
]
