-- Sample Target Database for Data Policy Agent Demo
-- This script creates a sample database with test data that can be scanned for compliance violations
--
-- Usage:
--   1. Create a new PostgreSQL database: createdb sample_target
--   2. Run this script: psql -d sample_target -f demo/sample_target_db.sql
--
-- The data includes intentional violations for demonstration purposes.

-- ============================================================================
-- SCHEMA SETUP
-- ============================================================================

-- Drop tables if they exist (for clean re-runs)
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- Customers table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    age INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Accounts table
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    account_number VARCHAR(50) UNIQUE NOT NULL,
    balance DECIMAL(15, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Transactions table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    transaction_type VARCHAR(50) NOT NULL,
    verified BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- SAMPLE DATA - COMPLIANT RECORDS
-- ============================================================================

-- Compliant customers
INSERT INTO customers (name, email, phone, age, status) VALUES
    ('Alice Johnson', 'alice.johnson@email.com', '5551234567', 35, 'active'),
    ('Bob Williams', 'bob.williams@company.org', '5559876543', 42, 'active'),
    ('Carol Davis', 'carol.d@example.net', '5555551234', 28, 'active'),
    ('David Miller', 'david.miller@business.com', '5558765432', 55, 'inactive'),
    ('Eva Martinez', 'eva.m@startup.io', '5552223333', 31, 'active'),
    ('Frank Brown', 'frank.brown@corp.com', '5554445555', 45, 'active'),
    ('Grace Lee', 'grace.lee@tech.co', '5556667777', 29, 'pending'),
    ('Henry Wilson', 'henry.w@enterprise.com', '5558889999', 38, 'active'),
    ('Iris Taylor', 'iris.taylor@agency.org', '5551112222', 33, 'active'),
    ('Jack Anderson', 'jack.a@consulting.com', '5553334444', 47, 'active');

-- Compliant accounts
INSERT INTO accounts (customer_id, account_number, balance, currency) VALUES
    (1, 'ACC-001-2024', 5000.00, 'USD'),
    (2, 'ACC-002-2024', 12500.50, 'USD'),
    (3, 'ACC-003-2024', 750.25, 'USD'),
    (4, 'ACC-004-2024', 0.00, 'USD'),
    (5, 'ACC-005-2024', 3200.00, 'EUR'),
    (6, 'ACC-006-2024', 8900.75, 'USD'),
    (7, 'ACC-007-2024', 1500.00, 'GBP'),
    (8, 'ACC-008-2024', 25000.00, 'USD'),
    (9, 'ACC-009-2024', 4300.50, 'USD'),
    (10, 'ACC-010-2024', 6700.00, 'USD');

-- Compliant transactions (under $10,000 or verified)
INSERT INTO transactions (account_id, amount, transaction_type, verified, description) VALUES
    (1, 500.00, 'deposit', true, 'Initial deposit'),
    (1, 150.00, 'withdrawal', true, 'ATM withdrawal'),
    (2, 2500.00, 'transfer', true, 'Wire transfer'),
    (3, 75.50, 'payment', true, 'Utility bill'),
    (4, 1000.00, 'deposit', true, 'Paycheck deposit'),
    (5, 3200.00, 'deposit', true, 'International transfer'),
    (6, 450.00, 'payment', true, 'Credit card payment'),
    (8, 15000.00, 'deposit', true, 'Large deposit - verified'),  -- Large but verified
    (8, 12000.00, 'transfer', true, 'Investment transfer - verified'),  -- Large but verified
    (9, 800.00, 'withdrawal', true, 'Cash withdrawal');

-- ============================================================================
-- SAMPLE DATA - NON-COMPLIANT RECORDS (VIOLATIONS)
-- ============================================================================

-- Violation: Invalid email format (DATA-001)
INSERT INTO customers (name, email, phone, age, status) VALUES
    ('John Doe', 'johndoe.invalid', '5551111111', 25, 'active'),  -- Missing @ and domain
    ('Jane Smith', 'jane@', '5552222222', 30, 'active'),  -- Incomplete email
    ('Mike Brown', 'mike.brown.no.at.sign', '5553333333', 40, 'active');  -- No @ symbol

-- Violation: Age under 18 (DATA-002)
INSERT INTO customers (name, email, phone, age, status) VALUES
    ('Tommy Young', 'tommy@email.com', '5554444444', 16, 'active'),  -- Age 16
    ('Sarah Teen', 'sarah.teen@school.edu', '5555555555', 15, 'pending'),  -- Age 15
    ('Billy Minor', 'billy.m@family.com', '5556666666', 17, 'active');  -- Age 17

-- Violation: Invalid phone format (DATA-003)
INSERT INTO customers (name, email, phone, age, status) VALUES
    ('Call Me Maybe', 'callme@email.com', '555-CALL-ME', 35, 'active'),  -- Letters in phone
    ('Phone Test', 'phone.test@email.com', '(555) ABC-1234', 28, 'active'),  -- Mixed format
    ('Bad Number', 'bad.number@email.com', 'not-a-phone', 42, 'active');  -- Completely invalid

-- Violation: Missing required fields (DATA-004)
INSERT INTO customers (name, email, phone, age, status) VALUES
    ('', 'empty.name@email.com', '5557777777', 30, 'active'),  -- Empty name
    (NULL, 'null.name@email.com', '5558888888', 25, 'active');  -- NULL name

INSERT INTO customers (name, email, phone, age, status) VALUES
    ('No Email User', '', '5559999999', 35, 'active'),  -- Empty email
    ('Null Email User', NULL, '5550000000', 40, 'active');  -- NULL email

-- Violation: Invalid status value (DATA-005)
INSERT INTO customers (name, email, phone, age, status) VALUES
    ('VIP Customer', 'vip@email.com', '5551010101', 50, 'vip'),  -- Invalid status
    ('Premium User', 'premium@email.com', '5552020202', 45, 'premium'),  -- Invalid status
    ('Deleted User', 'deleted@email.com', '5553030303', 38, 'deleted');  -- Invalid status

-- Create accounts for violation customers
INSERT INTO accounts (customer_id, account_number, balance, currency)
SELECT id, 'ACC-' || id || '-2024', 1000.00, 'USD'
FROM customers WHERE id > 10;

-- Violation: Negative account balance (FIN-001)
UPDATE accounts SET balance = -250.00 WHERE customer_id = 11;  -- Negative balance
UPDATE accounts SET balance = -1500.00 WHERE customer_id = 12;  -- Negative balance
UPDATE accounts SET balance = -50.75 WHERE customer_id = 13;  -- Negative balance

-- Violation: Large unverified transactions (FIN-002)
INSERT INTO transactions (account_id, amount, transaction_type, verified, description) VALUES
    (1, 15000.00, 'deposit', false, 'Large deposit - NOT verified'),
    (2, 25000.00, 'transfer', false, 'Large transfer - NOT verified'),
    (6, 12500.00, 'withdrawal', false, 'Large withdrawal - NOT verified'),
    (8, 50000.00, 'deposit', false, 'Very large deposit - NOT verified'),
    (10, 11000.00, 'payment', false, 'Large payment - NOT verified');

-- ============================================================================
-- SUMMARY QUERIES (for verification)
-- ============================================================================

-- You can run these queries to see the violations:

-- Invalid emails:
-- SELECT id, name, email FROM customers WHERE email NOT LIKE '%@%.%';

-- Underage customers:
-- SELECT id, name, age FROM customers WHERE age < 18;

-- Invalid phone numbers:
-- SELECT id, name, phone FROM customers WHERE phone ~ '[^0-9+]';

-- Negative balances:
-- SELECT a.id, c.name, a.balance FROM accounts a JOIN customers c ON a.customer_id = c.id WHERE a.balance < 0;

-- Large unverified transactions:
-- SELECT id, amount, verified FROM transactions WHERE amount > 10000 AND verified = false;

-- Missing required fields:
-- SELECT id, name, email FROM customers WHERE name IS NULL OR email IS NULL OR name = '' OR email = '';

-- Invalid status values:
-- SELECT id, name, status FROM customers WHERE status NOT IN ('active', 'inactive', 'suspended', 'pending');

-- ============================================================================
-- GRANT PERMISSIONS (if needed)
-- ============================================================================

-- If you're using a different user to connect, grant permissions:
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO your_user;
