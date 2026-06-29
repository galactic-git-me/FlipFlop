"""Welcome Guide PDF generation service."""

import os
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import json

from app.models import Order, WelcomeGuide
import structlog

log = structlog.get_logger(__name__)


class GuideService:
    """Service for generating personalized Welcome Guide PDFs."""

    def __init__(self, db: Session, output_dir: str = "/tmp/guides"):
        """Initialize guide service.

        Args:
            db: SQLAlchemy session
            output_dir: Directory to store generated PDFs
        """
        self.db = db
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.styles = self._create_styles()

    def _create_styles(self) -> dict:
        """Create ReportLab styles for PDF."""
        styles = getSampleStyleSheet()

        # Custom styles for FlipFlop branding
        heading_color = colors.HexColor('#d4af37')  # Gold
        text_color = colors.HexColor('#e8eaf0')  # Light gray
        secondary_color = colors.HexColor('#a0a8c0')  # Medium gray

        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=48,
            textColor=heading_color,
            alignment=TA_CENTER,
            spaceAfter=24,
            fontName='Helvetica-Bold',
        ))

        styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=heading_color,
            spaceAfter=16,
            fontName='Helvetica-Bold',
            borderColor=heading_color,
            borderWidth=2,
            borderPadding=12,
        ))

        styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=text_color,
            spaceAfter=8,
            fontName='Helvetica-Bold',
        ))

        styles.add(ParagraphStyle(
            name='CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=text_color,
            leading=14,
            alignment=TA_LEFT,
        ))

        styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=styles['Normal'],
            fontSize=18,
            textColor=secondary_color,
            alignment=TA_CENTER,
            spaceAfter=12,
        ))

        styles.add(ParagraphStyle(
            name='Warning',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#ef4444'),  # Red
            spaceAfter=12,
        ))

        styles.add(ParagraphStyle(
            name='BulletList',
            parent=styles['Normal'],
            fontSize=10,
            textColor=text_color,
            leading=14,
            spaceAfter=6,
            leftIndent=20,
        ))

        return styles

    def generate_welcome_guide(self, order_id: int) -> str:
        """Generate welcome guide PDF for an order.

        Args:
            order_id: Order ID to generate guide for

        Returns:
            Path to generated PDF file

        Raises:
            ValueError: If order not found
        """
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        log.info("generating_welcome_guide", order_id=order_id)

        filename = f"order_{order_id}_welcome_guide.pdf"
        filepath = os.path.join(self.output_dir, filename)

        # Create PDF document
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            title=f"Welcome Guide - Order {order_id}",
        )

        story = []

        # Build content sections
        story.extend(self._create_cover_page(order))
        story.append(PageBreak())

        story.extend(self._create_quick_start(order))
        story.append(PageBreak())

        story.extend(self._create_component_specs(order))
        story.append(PageBreak())

        story.extend(self._create_bios_guide(order))
        story.append(PageBreak())

        story.extend(self._create_os_setup(order))
        story.append(PageBreak())

        # License key page for Windows
        if order.os_component and 'windows' in order.os_component.os_type.lower():
            story.extend(self._create_license_page(order))
            story.append(PageBreak())

        story.extend(self._create_troubleshooting(order))
        story.append(PageBreak())

        story.extend(self._create_warranty(order))

        # Build PDF
        doc.build(story)
        log.info("pdf_generated", filepath=filepath)

        # Save metadata to database
        self._save_guide_metadata(order_id, filepath)

        return filepath

    def _save_guide_metadata(self, order_id: int, filepath: str) -> None:
        """Save welcome guide metadata to database."""
        # Check if guide already exists
        existing = self.db.query(WelcomeGuide).filter(
            WelcomeGuide.order_id == order_id
        ).first()

        if existing:
            existing.generated_at = datetime.utcnow()
            existing.content_json = {
                "order_id": order_id,
                "generated_at": datetime.utcnow().isoformat(),
                "file_path": filepath,
            }
        else:
            guide = WelcomeGuide(
                order_id=order_id,
                generated_at=datetime.utcnow(),
                content_json={
                    "order_id": order_id,
                    "generated_at": datetime.utcnow().isoformat(),
                    "file_path": filepath,
                },
            )
            self.db.add(guide)

        self.db.commit()

    def _create_cover_page(self, order: Order) -> list:
        """Create welcome cover page."""
        story = []

        # Logo / Title
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            "<b>FLIPFLOP</b>",
            self.styles['CustomTitle']
        ))

        story.append(Spacer(1, 0.3*inch))

        # Build info
        build_name = order.playbook.name if order.playbook else "Custom PC"
        story.append(Paragraph(
            f"Welcome, {order.customer.name}!",
            self.styles['CustomHeading2']
        ))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            f"Your {build_name}",
            self.styles['CustomSubtitle']
        ))

        story.append(Spacer(1, 0.5*inch))

        # Order information table
        warranty_end = None
        if order.actual_delivery_date:
            warranty_end = (order.actual_delivery_date + timedelta(days=365)).strftime("%B %d, %Y")
        else:
            warranty_end = "TBD"

        delivery_date = order.actual_delivery_date.strftime("%B %d, %Y") if order.actual_delivery_date else "Pending"

        order_info = [
            ['Order Number:', f"#{order.order_id}"],
            ['Delivered:', delivery_date],
            ['Warranty Until:', warranty_end],
        ]

        table = Table(order_info, colWidths=[2.0*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#e8eaf0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.5*inch))

        # Welcome message
        welcome_text = (
            f"Thank you for choosing FlipFlop. This personalized guide will help you get the most "
            f"out of your new PC. We've included detailed specifications, setup instructions, and "
            f"troubleshooting tips tailored to your build. If you have any questions, reach out to "
            f"<b>support@flipflop.com</b> or call <b>+44 (0)20 7946 0958</b>."
        )
        story.append(Paragraph(welcome_text, self.styles['CustomBody']))

        return story

    def _create_quick_start(self, order: Order) -> list:
        """Create quick start section."""
        story = []

        story.append(Paragraph("Quick Start", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.2*inch))

        # First power-on checklist
        story.append(Paragraph("First Power-On Checklist", self.styles['CustomHeading2']))

        checklist = [
            "✓ Ensure power supply switch is ON (back of PSU)",
            "✓ Verify all 24-pin motherboard and 8-pin CPU power connections",
            "✓ Check RAM is fully seated (clips on both sides locked)",
            "✓ Verify cooler is properly mounted and thermal paste applied",
            "✓ Ensure GPU is fully inserted and power cables connected (if applicable)",
            "✓ Check all case fans are spinning after power-on",
            "✓ Boot system and enter BIOS (usually DEL or F2 during startup)",
        ]

        for item in checklist:
            story.append(Paragraph(item, self.styles['BulletList']))

        story.append(Spacer(1, 0.2*inch))

        # OS-specific next steps
        if order.os_component and 'windows' in order.os_component.os_type.lower():
            story.append(Paragraph("Windows Setup Next Steps", self.styles['CustomHeading2']))
            steps = [
                "1. Complete Windows 11 initial setup (language, region, timezone)",
                "2. Go to Settings → System → Activation and activate with license key",
                "3. Download and install chipset drivers from your motherboard manufacturer",
                "4. Install GPU drivers: NVIDIA (nvidia.com) or AMD (amd.com)",
                "5. Run Windows Update to ensure all drivers and patches are current",
                "6. Install any RGB control software (MSI, ASUS, Corsair, etc.)",
            ]
        else:
            story.append(Paragraph("Linux Setup Next Steps", self.styles['CustomHeading2']))
            steps = [
                "1. Boot into Ubuntu and complete the welcome setup",
                "2. Open Terminal and run: sudo apt update && sudo apt upgrade",
                "3. Install GPU drivers: For NVIDIA use 'nvidia-driver', for AMD use 'mesa'",
                "4. Install desktop utilities and applications via apt",
                "5. Configure your desktop environment and install your preferred software",
            ]

        for step in steps:
            story.append(Paragraph(step, self.styles['BulletList']))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "We recommend running all setup steps immediately after delivery to ensure optimal performance.",
            self.styles['CustomBody']
        ))

        return story

    def _create_component_specs(self, order: Order) -> list:
        """Create component specifications section."""
        story = []

        story.append(Paragraph("Your PC Specifications", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.2*inch))

        # Extract components from order specs
        specs = order.specs if isinstance(order.specs, dict) else {}

        components_data = [
            ['Component', 'Model', 'Key Specs', 'Warranty'],
        ]

        # Add components from specs
        if 'cpu' in specs:
            components_data.append([
                'CPU',
                specs['cpu'].get('name', 'Unknown'),
                f"{specs['cpu'].get('cores', 'N/A')} cores, {specs['cpu'].get('base_clock', 'N/A')} GHz",
                '3 Years'
            ])

        if 'gpu' in specs:
            components_data.append([
                'GPU',
                specs['gpu'].get('name', 'Unknown'),
                f"{specs['gpu'].get('memory', 'N/A')}GB VRAM, {specs['gpu'].get('boost_clock', 'N/A')} MHz",
                '3 Years'
            ])

        if 'motherboard' in specs:
            components_data.append([
                'Motherboard',
                specs['motherboard'].get('name', 'Unknown'),
                f"{specs['motherboard'].get('socket', 'N/A')} Socket",
                '5 Years'
            ])

        if 'ram' in specs:
            components_data.append([
                'RAM',
                specs['ram'].get('name', 'Unknown'),
                f"{specs['ram'].get('capacity', 'N/A')}GB @ {specs['ram'].get('speed', 'N/A')}MHz",
                'Lifetime'
            ])

        if 'storage' in specs:
            components_data.append([
                'SSD/Storage',
                specs['storage'].get('name', 'Unknown'),
                f"{specs['storage'].get('capacity', 'N/A')}GB {specs['storage'].get('type', 'SSD')}",
                '5 Years'
            ])

        if 'psu' in specs:
            components_data.append([
                'Power Supply',
                specs['psu'].get('name', 'Unknown'),
                f"{specs['psu'].get('wattage', 'N/A')}W, {specs['psu'].get('rating', 'N/A')}",
                '10 Years'
            ])

        if 'case' in specs:
            components_data.append([
                'Case',
                specs['case'].get('name', 'Unknown'),
                specs['case'].get('type', 'Mid-Tower ATX'),
                'Lifetime'
            ])

        if 'cooler' in specs:
            components_data.append([
                'Cooler',
                specs['cooler'].get('name', 'Unknown'),
                specs['cooler'].get('type', 'Air/Liquid'),
                '5 Years'
            ])

        table = Table(components_data, colWidths=[1.0*inch, 1.5*inch, 1.8*inch, 0.9*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1f2b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#d4af37')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('333333')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#0f1419'), colors.HexColor('#1a1f2b')]),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.2*inch))

        # Performance summary
        story.append(Paragraph("<b>Performance Profile</b>", self.styles['CustomHeading2']))
        perf_text = (
            "<b>Gaming:</b> High-end gaming at 1440p with high/ultra settings, 100+ FPS on modern AAA titles.<br/>"
            "<b>Content Creation:</b> Fast 4K video editing, 3D rendering, and real-time streaming capability.<br/>"
            "<b>Productivity:</b> Excellent multitasking, virtualization support, and heavy workload performance."
        )
        story.append(Paragraph(perf_text, self.styles['CustomBody']))

        return story

    def _create_bios_guide(self, order: Order) -> list:
        """Create BIOS setup guide."""
        story = []

        story.append(Paragraph("BIOS Setup Guide", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.2*inch))

        specs = order.specs if isinstance(order.specs, dict) else {}
        mobo_name = specs.get('motherboard', {}).get('name', 'Unknown')

        story.append(Paragraph(f"<b>Motherboard:</b> {mobo_name}", self.styles['CustomHeading2']))
        story.append(Spacer(1, 0.1*inch))

        story.append(Paragraph(
            "BIOS (Basic Input/Output System) controls low-level hardware settings. "
            "Most systems work fine with default settings, but we recommend enabling XMP/DOCP for optimal RAM performance.",
            self.styles['CustomBody']
        ))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("<b>Step-by-Step Setup:</b>", self.styles['CustomHeading2']))

        bios_steps = [
            "1. Power on the system and watch for the boot screen",
            "2. Press DEL, F2, or F12 (depending on motherboard) to enter BIOS setup",
            "3. Navigate to 'Overclocking' or 'Advanced' menu",
            "4. Find 'XMP Profile' or 'DOCP Profile' and set to Profile 1 (auto-applies RAM rated speed)",
            "5. Navigate to 'Boot' tab and verify boot order: NVMe SSD first, Windows Boot Manager second",
            "6. (Optional) Enable 'TPM 2.0' under Security for Windows 11 full compatibility",
            "7. (Optional) Enable 'Virtualization' or 'SVM' under Advanced for VM/Docker support",
            "8. Press F10 to save and exit BIOS",
        ]

        for step in bios_steps:
            story.append(Paragraph(step, self.styles['BulletList']))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "<b>⚠️ Important:</b> Don't modify settings you don't understand. Default settings are stable and safe. "
            "Only change XMP/DOCP to improve RAM performance.",
            self.styles['Warning']
        ))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "<b>Overclocking (Advanced):</b> If you're experienced, you can safely increase CPU/GPU clocks by 5-10%. "
            "Use tools like CPU-Z (Windows) or lscpu (Linux) to monitor. Always increase voltage incrementally and monitor temperatures.",
            self.styles['CustomBody']
        ))

        return story

    def _create_os_setup(self, order: Order) -> list:
        """Create OS setup section."""
        story = []

        if order.os_component:
            os_type = order.os_component.os_type
        else:
            os_type = "Windows 11"

        story.append(Paragraph(f"Operating System Setup: {os_type}", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.2*inch))

        if order.os_component and 'windows' in order.os_component.os_type.lower():
            story.append(Paragraph(
                "Windows 11 is pre-installed. See the License Key page for activation instructions.",
                self.styles['CustomBody']
            ))
            story.append(Spacer(1, 0.2*inch))

            story.append(Paragraph("<b>Initial Setup Steps:</b>", self.styles['CustomHeading2']))
            setup_steps = [
                "1. Complete Windows 11 welcome screens (language, region, Microsoft account)",
                "2. Allow Windows Update to run (important for security and drivers)",
                "3. Go to Settings → System → Activation and activate with your license key",
                "4. Download chipset drivers from motherboard manufacturer website",
                "5. Install GPU drivers from NVIDIA (nvidia.com) or AMD (amd.com)",
                "6. Install RGB software if your cooler/case/GPU supports it",
                "7. Run Windows Update again to install any remaining patches",
            ]

            story.append(Paragraph("<b>Recommended Windows Optimizations:</b>", self.styles['CustomHeading2']))
            optimizations = [
                "• Disable unnecessary startup programs (Task Manager → Startup tab)",
                "• Enable Game Mode (Settings → Gaming → Game Mode)",
                "• Disable Cortana search if not needed (Settings → Privacy → General)",
                "• Enable High Performance power plan (Settings → System → Power)",
                "• Disable Visual Effects for pure performance (Settings → System → Advanced)",
            ]

            for step in setup_steps:
                story.append(Paragraph(step, self.styles['BulletList']))

            story.append(Spacer(1, 0.1*inch))

            for opt in optimizations:
                story.append(Paragraph(opt, self.styles['BulletList']))

        else:
            story.append(Paragraph("Ubuntu 24.04 LTS is pre-installed.", self.styles['CustomBody']))
            story.append(Spacer(1, 0.2*inch))

            story.append(Paragraph("<b>Initial Setup Steps:</b>", self.styles['CustomHeading2']))
            setup_steps = [
                "1. Boot into Ubuntu and complete the welcome setup wizard",
                "2. Open Terminal (Ctrl+Alt+T) and run: sudo apt update && sudo apt upgrade",
                "3. Install GPU drivers: NVIDIA users run 'sudo apt install nvidia-driver-{version}'",
                "4. Install essential tools: VS Code, Discord, browsers, development tools",
                "5. Configure desktop environment and shortcuts to your preference",
            ]

            for step in setup_steps:
                story.append(Paragraph(step, self.styles['BulletList']))

        return story

    def _create_license_page(self, order: Order) -> list:
        """Create Windows license key page."""
        story = []

        story.append(Paragraph("Windows License Key", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.3*inch))

        license_key = order.os_component.license_key if order.os_component else ""

        # Format key for readability
        if len(license_key) == 25:
            formatted_key = f"{license_key[0:5]}-{license_key[5:10]}-{license_key[10:15]}-{license_key[15:20]}-{license_key[20:25]}"
        else:
            formatted_key = license_key

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            f"<font size=22><b>{formatted_key}</b></font>",
            ParagraphStyle('license', alignment=TA_CENTER, textColor=colors.HexColor('#d4af37'))
        ))
        story.append(Spacer(1, 0.3*inch))

        story.append(Paragraph(
            "Keep this key safe. You'll need it to activate Windows.",
            ParagraphStyle('normal', alignment=TA_CENTER, fontSize=10)
        ))

        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("<b>How to Activate Windows 11:</b>", self.styles['CustomHeading2']))

        activation_steps = [
            "1. Go to Settings → System → Activation",
            "2. Click 'Change Product Key'",
            "3. Copy the license key above (without dashes) and paste it",
            "4. Click 'Next' and follow the activation wizard",
            "5. Once activated, you'll see 'Windows is activated' with a checkmark",
        ]

        for step in activation_steps:
            story.append(Paragraph(step, self.styles['BulletList']))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "💾 <b>Save this key in a secure location:</b> password manager, email draft, or physical backup.",
            self.styles['Warning']
        ))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "This is a retail license key and can be transferred to another PC if needed. "
            "Microsoft activation servers will validate the key automatically.",
            self.styles['CustomBody']
        ))

        return story

    def _create_troubleshooting(self, order: Order) -> list:
        """Create troubleshooting guide."""
        story = []

        story.append(Paragraph("Troubleshooting Guide", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.2*inch))

        issues = [
            {
                'title': 'PC Won\'t Boot (Black Screen)',
                'steps': [
                    '• Check power cable connections (24-pin motherboard, 8-pin CPU)',
                    '• Verify power supply switch is ON',
                    '• Ensure RAM is fully seated with clips engaged',
                    '• Try removing and reinserting CMOS battery for 30 seconds',
                    '• Check for any loose cables or bent pins',
                ]
            },
            {
                'title': 'High CPU or GPU Temperatures (>85°C)',
                'steps': [
                    '• Check that CPU cooler is properly mounted (not crooked)',
                    '• Verify thermal paste was applied between cooler and CPU',
                    '• Ensure case fans are spinning (look inside case)',
                    '• Check that radiator fans (if liquid cooled) are working',
                    '• Clean dust filters if case has intake filters',
                ]
            },
            {
                'title': 'Blue Screen of Death (BSOD)',
                'steps': [
                    '• Update all drivers (GPU, chipset, storage)',
                    '• Check Windows Event Viewer for error codes',
                    '• Try disabling XMP in BIOS if recently enabled',
                    '• Boot into Safe Mode (hold Shift during shutdown, then restart)',
                    '• Run Windows Disk Check: chkdsk /F in Command Prompt (admin)',
                ]
            },
            {
                'title': 'Game Crashes or Unexpected Shutdown',
                'steps': [
                    '• Lower GPU clock by 50MHz in driver settings (may indicate instability)',
                    '• Update GPU drivers to latest version',
                    '• Monitor temperatures with GPU-Z or HWiNFO during gaming',
                    '• Check power supply wattage is adequate for your system',
                    '• Run MemTest86 or Windows Memory Diagnostic to test RAM',
                ]
            },
            {
                'title': 'No Display Output',
                'steps': [
                    '• Ensure monitor is powered and set to correct input',
                    '• Try HDMI/DisplayPort on different GPU output ports',
                    '• Reseat GPU (fully insert into PCIe slot)',
                    '• Ensure GPU power cables are firmly connected',
                    '• Try integrated graphics (if CPU has it) by removing GPU temporarily',
                ]
            },
        ]

        for issue in issues:
            story.append(Paragraph(f"<b>{issue['title']}</b>", self.styles['CustomHeading2']))
            for step in issue['steps']:
                story.append(Paragraph(step, self.styles['BulletList']))
            story.append(Spacer(1, 0.1*inch))

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "<b>Still stuck?</b> Contact support@flipflop.com with photos and a description of the issue. "
            "We're here to help!",
            self.styles['CustomBody']
        ))

        return story

    def _create_warranty(self, order: Order) -> list:
        """Create warranty and support section."""
        story = []

        story.append(Paragraph("Warranty & Support", self.styles['CustomHeading1']))
        story.append(Spacer(1, 0.2*inch))

        warranty_end = "TBD"
        if order.actual_delivery_date:
            warranty_end = (order.actual_delivery_date + timedelta(days=365)).strftime("%B %d, %Y")

        warranty_info = (
            f"<b>FlipFlop Build Warranty:</b><br/>"
            f"Duration: 1 year from delivery date ({warranty_end})<br/>"
            f"Covers: Manufacturing defects, assembly issues, labor<br/>"
            f"Does NOT cover: Accidental damage, liquid damage, misuse<br/>"
            f"<br/>"
            f"<b>Component Warranties:</b><br/>"
            f"• CPU: 3 years (Intel/AMD manufacturer warranty)<br/>"
            f"• GPU: 3 years (NVIDIA/AMD manufacturer warranty)<br/>"
            f"• Motherboard: 5 years<br/>"
            f"• RAM: Lifetime (most manufacturers)<br/>"
            f"• SSD: 5 years<br/>"
            f"• Power Supply: 10 years<br/>"
            f"<br/>"
            f"<b>FlipFlop Support Contact:</b><br/>"
            f"Email: support@flipflop.com<br/>"
            f"Phone: +44 (0)20 7946 0958<br/>"
            f"Hours: Monday-Friday 9am-6pm GMT<br/>"
            f"<br/>"
            f"<b>RMA (Return/Repair) Process:</b><br/>"
            f"1. Contact support with photos and description of issue<br/>"
            f"2. Receive RMA authorization number and return shipping label<br/>"
            f"3. Ship the PC back to us (we cover return shipping)<br/>"
            f"4. We diagnose and repair (typically 5-7 business days)<br/>"
            f"5. We ship your repaired PC back with fresh warranty<br/>"
        )

        story.append(Paragraph(warranty_info, self.styles['CustomBody']))

        return story
