import os
import shutil
from pathlib import Path
from decimal import Decimal
import datetime
from django.core.management.base import BaseCommand
from django.core.files import File
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

from invoices.models import AccountCode, Supplier, Document, Invoice, InvoiceLineItem, ValidationIssue
from invoices.utils.fixture_generator import generate_pdf_invoice, generate_png_invoice
from invoices.services.extraction_service import ExtractionService
from invoices.adapters.factory import get_accounting_adapter


class Command(BaseCommand):
    help = 'Seeds chart of accounts, suppliers, demo users, and realistic invoice documents.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding chart of accounts, suppliers, demo users and invoice fixtures..."))

        # 1. Seed Users
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@enterprise-finance.io',
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'Sarah',
                'last_name': 'Chen (Finance Director)'
            }
        )
        admin_user.set_password('admin12345')
        admin_user.save()

        reviewer_user, _ = User.objects.get_or_create(
            username='reviewer',
            defaults={
                'email': 'reviewer@enterprise-finance.io',
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Alex',
                'last_name': 'Rivera (AP Specialist)'
            }
        )
        reviewer_user.set_password('finance12345')
        reviewer_user.save()

        self.stdout.write(self.style.SUCCESS("✓ Seeded users: admin (password: admin12345) and reviewer (password: finance12345)"))

        # 2. Seed Chart of Accounts
        accounts_data = [
            ("4000", "Software & Cloud Subscriptions", "EXPENSE", "SaaS software licenses, developer tools, and operational apps"),
            ("5000", "Office Supplies & Stationery", "EXPENSE", "Physical workplace supplies, ergonomic furnishings, paper and printing"),
            ("6100", "Professional & Consulting Services", "EXPENSE", "Legal, accounting, security auditing, and technical advisory"),
            ("6200", "Cloud Hosting & IT Infrastructure", "EXPENSE", "AWS/GCP/Azure compute, managed database clusters, SLA support"),
            ("7000", "Travel & Business Meals", "EXPENSE", "Employee business travel, accommodations, client entertainment"),
            ("8000", "Utilities & Telecommunications", "EXPENSE", "Office broadband, phone systems, electricity and facilities"),
        ]

        accounts_map = {}
        for code, name, category, desc in accounts_data:
            acc, _ = AccountCode.objects.update_or_create(
                code=code,
                defaults={'name': name, 'category': category, 'description': desc, 'is_active': True}
            )
            accounts_map[code] = acc

        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(accounts_data)} Chart of Accounts entries."))

        # 3. Seed Suppliers
        suppliers_data = [
            ("Acme Cloud Services Inc.", "US-987654321", "billing@acmecloud.io", accounts_map["6200"]),
            ("Apex Global Advisors LLC", "US-123456789", "invoices@apexglobal.com", accounts_map["6100"]),
            ("Metro Office Supplies Co.", "US-554433221", "accounts@metrooffice.com", accounts_map["5000"]),
        ]

        for name, tax_id, email, default_acc in suppliers_data:
            Supplier.objects.update_or_create(
                name=name,
                defaults={
                    'tax_id': tax_id,
                    'contact_email': email,
                    'default_account_code': default_acc,
                    'is_approved': True
                }
            )

        self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(suppliers_data)} recognized suppliers."))

        # 4. Generate Synthetic Files in media/fixtures
        fixtures_dir = Path(settings.MEDIA_ROOT) / 'fixtures'
        fixtures_dir.mkdir(parents=True, exist_ok=True)

        # File 1: Acme Cloud Services (Valid SaaS)
        f1_path = str(fixtures_dir / "acme_cloud_invoice.pdf")
        generate_pdf_invoice(
            output_path=f1_path,
            supplier_name="Acme Cloud Services Inc.",
            invoice_number="INV-2026-0891",
            date_str="2026-09-15",
            due_date_str="2026-10-15",
            bill_to="Nexus Enterprise Technologies Inc.",
            items=[
                ("Enterprise Cloud Cluster (16 Nodes) - Monthly Subscription", "1", "1800.00", "1800.00"),
                ("Managed PostgreSQL Database Multi-AZ Replication", "1", "450.00", "450.00"),
                ("Premium 24/7 SLA Support Tier", "1", "200.00", "200.00"),
            ],
            subtotal="2450.00",
            tax="196.00",
            total="2646.00",
            tax_id="US-987654321"
        )

        # File 2: Apex Global Advisors (Valid Consulting)
        f2_path = str(fixtures_dir / "apex_consulting_invoice.pdf")
        generate_pdf_invoice(
            output_path=f2_path,
            supplier_name="Apex Global Advisors LLC",
            invoice_number="AGA-2026-4402",
            date_str="2026-09-20",
            due_date_str="2026-10-20",
            bill_to="Nexus Enterprise Technologies Inc.",
            items=[
                ("Senior Technical Advisory - Systems Architecture (24 hrs @ $150/hr)", "24", "150.00", "3600.00"),
                ("Security & Compliance Audit Review", "1", "1200.00", "1200.00"),
            ],
            subtotal="4800.00",
            tax="0.00",
            total="4800.00",
            tax_id="US-123456789"
        )

        # File 3: Math Error Invoice
        f3_path = str(fixtures_dir / "math_error_invoice.pdf")
        generate_pdf_invoice(
            output_path=f3_path,
            supplier_name="Metro Office Supplies Co.",
            invoice_number="MOS-99120",
            date_str="2026-09-28",
            due_date_str="2026-10-28",
            bill_to="Nexus Enterprise Technologies Inc.",
            items=[
                ("Ergonomic Executive Mesh Chairs", "3", "350.00", "1050.00"),
                ("Recycled Laser Printer Paper (10 Cartons)", "10", "45.00", "450.00"),
            ],
            subtotal="1500.00",
            tax="120.00",
            total="1850.00",  # Deliberate math error
            tax_id="US-554433221"
        )

        # File 4: Duplicate Invoice (Same supplier & invoice # as Acme)
        f4_path = str(fixtures_dir / "duplicate_invoice.pdf")
        generate_pdf_invoice(
            output_path=f4_path,
            supplier_name="Acme Cloud Services Inc.",
            invoice_number="INV-2026-0891",
            date_str="2026-09-15",
            due_date_str="2026-10-15",
            bill_to="Nexus Enterprise Technologies Inc.",
            items=[
                ("Enterprise Cloud Cluster (16 Nodes) - Monthly Subscription", "1", "1800.00", "1800.00"),
            ],
            subtotal="1800.00",
            tax="144.00",
            total="1944.00"
        )

        # File 5: Unknown Supplier Invoice
        f5_path = str(fixtures_dir / "unknown_supplier_invoice.pdf")
        generate_pdf_invoice(
            output_path=f5_path,
            supplier_name="Vanguard Quantum Robotics Ltd",
            invoice_number="VQR-88210",
            date_str="2026-10-01",
            due_date_str="2026-10-31",
            bill_to="Nexus Enterprise Technologies Inc.",
            items=[
                ("Quantum Sensor Development Kit v2", "2", "1600.00", "3200.00"),
            ],
            subtotal="3200.00",
            tax="256.00",
            total="3456.00",
            tax_id="GB-998877665"
        )

        # File 6: Missing Fields Invoice
        f6_path = str(fixtures_dir / "missing_fields_invoice.pdf")
        generate_pdf_invoice(
            output_path=f6_path,
            supplier_name="",
            invoice_number="",
            date_str="2026-10-05",
            due_date_str="",
            bill_to="Nexus Enterprise Technologies Inc.",
            items=[
                ("Miscellaneous Hardware Components", "1", "850.00", "850.00"),
            ],
            subtotal="850.00",
            tax="0.00",
            total="850.00"
        )

        # File 7: Low Confidence Scan PNG
        f7_path = str(fixtures_dir / "low_confidence_invoice.png")
        generate_png_invoice(
            output_path=f7_path,
            supplier_name="Blurry Scan Vendor Co",
            invoice_number="BLUR-001",
            date_str="2026-10-02",
            total_str="691.20"
        )

        self.stdout.write(self.style.SUCCESS("✓ Generated 7 synthetic invoice fixture documents."))

        # 5. Ingest and Process Sample Documents into Database
        samples = [
            ("acme_cloud_invoice.pdf", f1_path, "pdf"),
            ("apex_consulting_invoice.pdf", f2_path, "pdf"),
            ("math_error_invoice.pdf", f3_path, "pdf"),
            ("duplicate_invoice.pdf", f4_path, "pdf"),
            ("unknown_supplier_invoice.pdf", f5_path, "pdf"),
            ("missing_fields_invoice.pdf", f6_path, "pdf"),
            ("low_confidence_invoice.png", f7_path, "png"),
        ]

        for filename, filepath, file_type in samples:
            with open(filepath, 'rb') as f:
                file_content = f.read()
                file_size = len(file_content)
                file_hash = Document.calculate_file_hash(open(filepath, 'rb'))

                # Delete previous document with matching original_filename for clean re-seeding
                Document.objects.filter(original_filename=filename).delete()

                doc = Document.objects.create(
                    original_filename=filename,
                    file_type=file_type,
                    file_size=file_size,
                    file_hash=file_hash,
                    uploaded_by=reviewer_user,
                    status='PROCESSING'
                )
                doc.file.save(filename, File(open(filepath, 'rb')), save=True)

                # Process extraction
                try:
                    invoice = ExtractionService.process_document(doc, user=reviewer_user, force_mode='mock')
                    
                    # For Apex Consulting invoice, simulate human approval and accounting export
                    if filename == "apex_consulting_invoice.pdf":
                        invoice.approval_status = 'APPROVED'
                        invoice.approved_by = admin_user
                        invoice.approved_at = timezone.now() - datetime.timedelta(days=2)
                        invoice.save(update_fields=['approval_status', 'approved_by', 'approved_at'])
                        doc.status = 'APPROVED'
                        doc.save(update_fields=['status'])
                        
                        # Export to Mock Accounting
                        adapter = get_accounting_adapter()
                        adapter.export_invoice(invoice, user=admin_user)

                    self.stdout.write(self.style.SUCCESS(f"  • Ingested '{filename}' -> Status: {doc.get_status_display()}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  • Ingestion failed for '{filename}': {e}"))

        self.stdout.write(self.style.SUCCESS("\n🎉 Successfully seeded database with complete portfolio demo data!"))
