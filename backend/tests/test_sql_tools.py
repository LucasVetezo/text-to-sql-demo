"""
Tests for SQL tool safety (query validator).
Ensures write operations are always blocked regardless of LLM output.
"""

import pytest
from app.tools.sql_tools import _validate_sql


class TestSQLQueryValidator:
    """
    Critical security tests — these must NEVER fail in CI.
    The validator is the main defence against LLM-generated write operations.
    """

    # -- Should PASS (SELECT queries) ----------------------------------------

    def test_simple_select_passes(self):
        _validate_sql("SELECT * FROM credit_applications LIMIT 10")

    def test_select_with_where_passes(self):
        _validate_sql("SELECT name, credit_score FROM credit_applications WHERE application_status = 'rejected'")

    def test_select_with_join_passes(self):
        _validate_sql("SELECT a.name, f.fraud_flag FROM accounts a JOIN fraud_cases f ON a.id = f.account_id")

    def test_select_with_group_by_passes(self):
        _validate_sql("SELECT province, COUNT(*) FROM credit_applications GROUP BY province")

    def test_select_with_subquery_passes(self):
        _validate_sql("SELECT * FROM (SELECT * FROM credit_applications WHERE credit_score > 700) AS q LIMIT 5")

    def test_select_case_insensitive_passes(self):
        _validate_sql("select * from fraud_cases where risk_score > 0.8")

    # -- Should FAIL (write operations) --------------------------------------

    def test_insert_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("INSERT INTO credit_applications (name) VALUES ('hacker')")

    def test_update_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("UPDATE fraud_cases SET fraud_flag = 'cleared' WHERE 1=1")

    def test_delete_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("DELETE FROM credit_applications WHERE id > 0")

    def test_drop_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("DROP TABLE credit_applications")

    def test_truncate_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("TRUNCATE TABLE fraud_cases")

    def test_alter_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("ALTER TABLE credit_applications ADD COLUMN hacked TEXT")

    def test_create_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("CREATE TABLE evil AS SELECT * FROM credit_applications")

    def test_mixed_case_insert_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("InSeRt INTO credit_applications VALUES (1, 'test')")

    def test_exec_blocked(self):
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql("EXEC sp_addrolemember 'db_owner', 'hacker'")

    def test_union_with_insert_blocked(self):
        """Injection attempt: valid SELECT followed by INSERT via UNION"""
        with pytest.raises(ValueError, match="Write operations"):
            _validate_sql(
                "SELECT * FROM credit_applications UNION ALL "
                "INSERT INTO credit_applications (name) SELECT 'pwned'"
            )
