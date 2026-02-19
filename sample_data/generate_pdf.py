from fpdf import FPDF

class PolicyPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 8, 'Global Financial Services Inc. - AML Compliance Policy', 0, 1, 'C')
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Confidential - Internal Use Only', 0, 0, 'C')

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 13)
        self.set_fill_color(230, 230, 250)
        self.cell(0, 9, title, 0, 1, 'L', True)
        self.ln(3)

    def rule_title(self, title):
        self.set_font('Helvetica', 'B', 11)
        self.cell(0, 7, title, 0, 1)
        self.ln(1)

    def body_text(self, text):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

pdf = PolicyPDF()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

# Title
pdf.set_font('Helvetica', 'B', 20)
pdf.cell(0, 12, 'Anti-Money Laundering (AML)', 0, 1, 'C')
pdf.cell(0, 12, 'Compliance Policy', 0, 1, 'C')
pdf.ln(4)
pdf.set_font('Helvetica', '', 11)
pdf.cell(0, 7, 'Document Version: 2.0  |  Effective Date: January 1, 2026', 0, 1, 'C')
pdf.cell(0, 7, 'Classification: Internal - Mandatory Compliance', 0, 1, 'C')
pdf.ln(8)

# Section 1
pdf.section_title('1. Purpose')
pdf.body_text('This policy establishes the rules and procedures for detecting, preventing, and reporting money laundering activities across all financial transactions processed by Global Financial Services Inc. All employees, systems, and automated agents must enforce these rules without exception.')

# Section 2
pdf.section_title('2. Transaction Monitoring Rules')

pdf.rule_title('Rule 2.1: Large Transaction Threshold')
pdf.body_text('Any single transaction with an amount exceeding $10,000 USD must be flagged for review. This applies to all transaction types including wire transfers, cash deposits, cash withdrawals, and electronic payments.')

pdf.rule_title('Rule 2.2: Structuring Detection')
pdf.body_text('If a single account initiates more than 3 transactions within a 24-hour period where each transaction is between $8,000 and $10,000, this pattern must be flagged as potential structuring (smurfing) to avoid the $10,000 reporting threshold.')

pdf.rule_title('Rule 2.3: Rapid Successive Transfers')
pdf.body_text('Any account that sends more than 5 transfers to the same beneficiary within a 7-day period must be flagged for review, regardless of individual transaction amounts.')

pdf.rule_title('Rule 2.4: High-Risk Transaction Types')
pdf.body_text('All transactions categorized as "cash-out" or "wire transfer" exceeding $5,000 must undergo enhanced due diligence review.')

# Section 3
pdf.section_title('3. Account Behavior Rules')

pdf.rule_title('Rule 3.1: Unusual Volume Spike')
pdf.body_text('If an account\'s total transaction volume in any single day exceeds 200% of its average daily volume over the past 30 days, the account must be flagged for suspicious activity.')

pdf.rule_title('Rule 3.2: Round Amount Transactions')
pdf.body_text('Transactions with perfectly round amounts (e.g., $10,000.00, $50,000.00, $100,000.00) exceeding $5,000 must be flagged, as round amounts are a common indicator of laundering activity.')

pdf.rule_title('Rule 3.3: New Account High Activity')
pdf.body_text('Any account less than 30 days old that processes transactions totaling more than $50,000 must be flagged for enhanced review.')

# Section 4
pdf.section_title('4. Cross-Border Transaction Rules')

pdf.rule_title('Rule 4.1: International Transfer Limits')
pdf.body_text('Any international wire transfer exceeding $3,000 must be reported and reviewed within 24 hours.')

pdf.rule_title('Rule 4.2: Multiple Currency Transactions')
pdf.body_text('If a single account transacts in more than 3 different currencies within a 48-hour window, the account must be flagged for review.')

# Section 5
pdf.section_title('5. Known Fraud Indicators')

pdf.rule_title('Rule 5.1: Labeled Suspicious Transactions')
pdf.body_text('Any transaction that has been labeled or flagged as suspicious, fraudulent, or related to laundering by any internal or external system must be immediately escalated for human review. Zero tolerance policy applies.')

pdf.rule_title('Rule 5.2: Layering Detection')
pdf.body_text('Sequential transactions where funds are received and then immediately transferred out (within 1 hour) to a different account, with the outgoing amount being 90-100% of the incoming amount, must be flagged as potential layering.')

# Section 6
pdf.section_title('6. Reporting and Escalation')
pdf.body_text('All flagged transactions must be:\n- Logged in the compliance monitoring system with full transaction details\n- Assigned a severity level (Critical, High, Medium, Low)\n- Reviewed by a compliance officer within 48 hours\n- Reported to relevant authorities if confirmed as suspicious')

pdf.rule_title('Severity Classification:')
pdf.body_text('Critical: Transactions exceeding $100,000 or confirmed laundering patterns\nHigh: Transactions between $50,000-$100,000 or multiple rule violations\nMedium: Transactions between $10,000-$50,000 or single rule violations\nLow: Transactions flagged by pattern detection requiring routine review')

# Section 7
pdf.section_title('7. Compliance')
pdf.body_text('Failure to enforce these rules may result in regulatory penalties, fines up to $1,000,000 per violation, and criminal prosecution under applicable anti-money laundering laws. This policy is reviewed and updated annually. All automated compliance systems must be configured to enforce these rules continuously.')

pdf.ln(10)
pdf.set_font('Helvetica', 'B', 10)
pdf.cell(0, 7, 'Approved by: Chief Compliance Officer', 0, 1)
pdf.cell(0, 7, 'Review Date: January 1, 2027', 0, 1)

pdf.output('sample_data/AML_Compliance_Policy.pdf')
print("PDF created: sample_data/AML_Compliance_Policy.pdf")
