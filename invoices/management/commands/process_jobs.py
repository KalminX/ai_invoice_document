import time
import signal
import sys
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from invoices.services.job_service import JobService

logger = logging.getLogger('invoices')


class Command(BaseCommand):
    help = 'Processes pending database-backed invoice background processing jobs.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True

    def handle_shutdown(self, signum, frame):
        self.stdout.write(self.style.WARNING("\nShutting down job processor gracefully..."))
        self.running = False

    def add_arguments(self, parser):
        parser.add_argument(
            '--watch',
            action='store_true',
            help='Run continuously in a worker loop polling for pending jobs.',
        )
        parser.add_argument(
            '--interval',
            type=float,
            default=2.0,
            help='Polling sleep interval in seconds when --watch is active (default 2.0s).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of jobs to process per batch (default 10).',
        )

    def handle(self, *args, **options):
        watch = options['watch']
        interval = options['interval']
        limit = options['limit']

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        self.stdout.write(self.style.SUCCESS(
            f"Starting Invoice Job Processor (Mode: {'Continuous Worker' if watch else 'Single Batch'})..."
        ))

        if not watch:
            processed = JobService.process_pending_batch(limit=limit)
            self.stdout.write(self.style.SUCCESS(f"Processed {processed} pending job(s)."))
            return

        self.stdout.write(self.style.NOTICE(f"Listening for pending jobs (poll interval: {interval}s)... Press Ctrl+C to stop."))
        
        while self.running:
            try:
                processed = JobService.process_pending_batch(limit=limit)
                if processed > 0:
                    self.stdout.write(self.style.SUCCESS(f"[{timezone.now().strftime('%H:%M:%S')}] Processed {processed} job(s)."))
                time.sleep(interval)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in job worker loop: {e}"))
                time.sleep(interval)

        self.stdout.write(self.style.SUCCESS("Job worker stopped cleanly."))
