from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from invoices.models import ProcessingJob
from invoices.services.job_service import JobService


@login_required
def job_list_view(request):
    """Background processing jobs inspection console."""
    jobs = ProcessingJob.objects.select_related('document').order_by('-created_at')[:50]
    
    pending_count = ProcessingJob.objects.filter(status='PENDING').count()
    running_count = ProcessingJob.objects.filter(status='RUNNING').count()
    completed_count = ProcessingJob.objects.filter(status='COMPLETED').count()
    failed_count = ProcessingJob.objects.filter(status='FAILED').count()

    context = {
        'jobs': jobs,
        'pending_count': pending_count,
        'running_count': running_count,
        'completed_count': completed_count,
        'failed_count': failed_count,
    }
    return render(request, 'invoices/jobs/job_list.html', context)


@login_required
def job_process_now_view(request):
    """Triggers immediate processing of all pending jobs from the web UI."""
    count = JobService.process_pending_batch(limit=20)
    if count > 0:
        messages.success(request, f"Successfully executed {count} pending background job(s).")
    else:
        messages.info(request, "No pending background jobs to process.")
    return redirect('invoices:job_list')


@login_required
def job_retry_view(request, job_id):
    """Retries an individual failed processing job."""
    job = get_object_or_404(ProcessingJob, id=job_id)
    job.status = 'PENDING'
    job.attempts = 0
    job.save(update_fields=['status', 'attempts'])
    
    JobService.execute_job(job)
    messages.success(request, f"Re-executed Job #{job.id}. Current status: {job.get_status_display()}")
    return redirect('invoices:job_list')
