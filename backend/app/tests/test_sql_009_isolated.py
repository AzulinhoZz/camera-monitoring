import unittest
import os
import re

class TestSQLMigration009SyntaxAndStructure(unittest.TestCase):

    def setUp(self):
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", "migrations", "009_roles_and_organizations.sql"),
            os.path.join(os.path.dirname(__file__), "..", "migrations", "009_roles_and_organizations.sql"),
            os.path.join(os.path.dirname(__file__), "009_roles_and_organizations.sql"),
            "/code/migrations/009_roles_and_organizations.sql",
            "/Users/alexisreyes/Developer/camera-monitoring/backend/migrations/009_roles_and_organizations.sql"
        ]
        self.migration_path = None
        for p in possible_paths:
            if os.path.exists(p):
                self.migration_path = p
                break

        if not self.migration_path:
            raise FileNotFoundError("Could not locate 009_roles_and_organizations.sql migration file")

        with open(self.migration_path, "r", encoding="utf-8") as f:
            self.sql_content = f.read()

    def test_file_exists_and_not_empty(self):
        self.assertIsNotNone(self.migration_path)
        self.assertTrue(os.path.exists(self.migration_path))
        self.assertGreater(len(self.sql_content), 500)

    def test_transaction_block(self):
        """Verify that migration is wrapped in BEGIN; and COMMIT;"""
        self.assertTrue(self.sql_content.strip().startswith("BEGIN;"))
        self.assertTrue(self.sql_content.strip().endswith("COMMIT;"))

    def test_no_old_or_new_in_rls_check(self):
        """CRITICAL SECURITY TEST: Ensure NO 'OLD.' or 'NEW.' references exist in RLS WITH CHECK or USING clauses."""
        policies = re.findall(r"CREATE\s+POLICY[\s\S]+?;", self.sql_content, re.IGNORECASE)
        self.assertGreater(len(policies), 5)

        for policy in policies:
            # RLS policy expressions must not contain OLD. or NEW. variables
            self.assertNotIn("OLD.", policy, f"Forbidden 'OLD.' reference found in RLS policy: {policy}")
            self.assertNotIn("NEW.", policy, f"Forbidden 'NEW.' reference found in RLS policy: {policy}")

    def test_recursion_free_helpers(self):
        """Verify that RLS helper functions use SECURITY DEFINER and search_path hardening."""
        self.assertIn("get_auth_user_organization_id()", self.sql_content)
        self.assertIn("get_auth_user_role()", self.sql_content)
        self.assertIn("has_camera_grant_access(p_camera_id UUID)", self.sql_content)
        self.assertIn("get_camera_organization_id(p_camera_id UUID)", self.sql_content)

        # Hardening check
        self.assertIn("SET search_path = public, pg_temp", self.sql_content)
        self.assertIn("SECURITY DEFINER", self.sql_content)

    def test_trigger_ownership_and_transport_unit_checks(self):
        """Verify trigger function prevent_camera_ownership_tampering exists for OLD/NEW checks."""
        self.assertIn("prevent_camera_ownership_tampering()", self.sql_content)
        self.assertIn("transport_unit_id IS NOT NULL", self.sql_content)
        self.assertIn("prevent_profile_role_escalation()", self.sql_content)

    def test_non_destructive_backfill(self):
        """Verify profiles backfill for existing auth.users without dropping profiles or cameras."""
        self.assertNotIn("DROP TABLE public.profiles", self.sql_content)
        self.assertNotIn("DROP TABLE public.cameras", self.sql_content)
        self.assertIn("INSERT INTO public.profiles (id, full_name, role)", self.sql_content)
        self.assertIn("FROM auth.users", self.sql_content)


if __name__ == "__main__":
    unittest.main()
