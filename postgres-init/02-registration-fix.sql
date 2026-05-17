-- ============================================================================
-- Registration Module Fix Migration
-- Run manually against production: psql -U <user> -d <db> -f this_file.sql
-- ============================================================================

-- Widen material_origin to hold full country names (was VARCHAR(2) for ISO codes)
ALTER TABLE supplier_registrations ALTER COLUMN material_origin TYPE VARCHAR(100);

-- Make sales contact fields nullable (they were NOT NULL)
ALTER TABLE supplier_registrations ALTER COLUMN sales_contact_name DROP NOT NULL;
ALTER TABLE supplier_registrations ALTER COLUMN sales_contact_email DROP NOT NULL;
ALTER TABLE supplier_registrations ALTER COLUMN sales_contact_phone DROP NOT NULL;
