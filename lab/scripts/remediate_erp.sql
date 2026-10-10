-- Management's remediation of ERP / database access findings.
UPDATE app.users SET is_active = false, deactivated_at = now() WHERE username IN ('klee', 'framirez', 'frontdesk');
DELETE FROM app.user_roles WHERE (username, role) IN
  (('apatel', 'ERP_ADMIN'), ('brivera', 'AP_APPROVER'), ('bnguyen', 'GL_POSTER'), ('cadams', 'GL_APPROVER'),
   ('amartinez', 'AP_APPROVER'));
ALTER ROLE ahaddad NOSUPERUSER;
