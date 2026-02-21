"""Generate an AML Compliance Policy PDF tailored to the IBM AML dataset schema."""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import os

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IBM_AML_Compliance_Policy.pdf")

def build_pdf():
    doc = SimpleDocTemplate(OUTPUT, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=18, spaceAfter=12)
    h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=14, spaceAfter=8, spaceBefore=14)
    h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, spaceAfter=6, spaceBefore=10)
    body = styles['BodyText']
    body.spaceAfter = 6

    story = []
    def add(text, style=body):
        story.append(Paragraph(text, style))

    add("Anti-Money Laundering (AML) Compliance Policy", title_style)
    add("Global Financial Services Inc. — Version 3.0 — Effective February 2026")
    story.append(Spacer(1, 12))

    add("1. Purpose", h1)
    add("This policy defines mandatory rules for detecting and preventing money laundering "
        "in the transactions database. The database contains fields: Timestamp, From Bank, "
        "From Account, To Bank, To Account, Amount Received, Receiving Currency, Amount Paid, "
        "Payment Currency, Payment Format, and Is Laundering flag.")

    add("2. Transaction Amount Rules", h1)

    add("Rule 2.1: Large Transaction Reporting", h2)
    add("Any transaction where Amount Paid exceeds 10,000 (in any currency) must be flagged "
        "for mandatory review. This is a regulatory requirement under AML laws.")

    add("Rule 2.2: Very High Value Transactions", h2)
    add("Any transaction where Amount Paid exceeds 50,000 must be classified as critical "
        "severity and escalated immediately to the compliance team.")

    add("Rule 2.3: Round Amount Detection", h2)
    add("Transactions where Amount Paid is a perfectly round number (divisible by 1000) "
        "and exceeds 5,000 must be flagged. Round amounts are a common laundering indicator.")

    add("Rule 2.4: Currency Mismatch", h2)
    add("Any transaction where Payment Currency differs from Receiving Currency must be "
        "flagged for review. Cross-currency transactions require enhanced due diligence.")

    add("Rule 2.5: Amount Discrepancy", h2)
    add("Any transaction where Amount Paid differs from Amount Received by more than 5% "
        "must be flagged. Significant discrepancies may indicate fee manipulation or layering.")

    add("3. Payment Format Rules", h1)

    add("Rule 3.1: High-Risk Payment Formats", h2)
    add("All transactions using Bitcoin or Cash as Payment Format must be flagged for "
        "enhanced monitoring. These formats are commonly used in money laundering.")

    add("Rule 3.2: Wire Transfer Threshold", h2)
    add("Wire transfer transactions exceeding 5,000 in Amount Paid must undergo "
        "additional compliance review.")

    add("4. Account Behavior Rules", h1)

    add("Rule 4.1: Self-Transfer Detection", h2)
    add("Any transaction where From Account equals To Account (self-transfer) must be "
        "flagged as suspicious. Self-transfers are a known structuring technique.")

    add("Rule 4.2: Same Bank Large Transfers", h2)
    add("Transactions where From Bank equals To Bank and Amount Paid exceeds 20,000 "
        "must be reviewed. Internal large transfers may indicate layering.")

    add("5. Known Laundering Flag", h1)

    add("Rule 5.1: Flagged Transactions", h2)
    add("Any transaction where the Is Laundering field equals 1 must be immediately "
        "escalated as a critical violation. This represents confirmed or suspected "
        "laundering activity identified by the detection system.")

    add("6. Severity Classification", h1)
    add("Critical: Is Laundering = 1, or Amount Paid > 50,000<br/>"
        "High: Amount Paid > 10,000, or Bitcoin/Cash payment format<br/>"
        "Medium: Currency mismatch, round amounts, or self-transfers<br/>"
        "Low: Wire transfers > 5,000, same-bank large transfers")

    add("7. Compliance", h1)
    add("All flagged transactions must be logged, assigned severity, and reviewed within "
        "48 hours. Failure to enforce these rules may result in regulatory penalties.")

    story.append(Spacer(1, 20))
    add("Approved by: Chief Compliance Officer — Review Date: February 2027")

    doc.build(story)
    print(f"PDF generated: {OUTPUT}")

if __name__ == "__main__":
    build_pdf()
