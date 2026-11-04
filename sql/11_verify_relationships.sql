-- Check the assignment's final state and constraints without retaining changes.
BEGIN;
DO $$
BEGIN
    IF (SELECT count(*) FROM users) <> 2
        OR (SELECT count(*) FROM calculations) <> 2
        OR NOT EXISTS (SELECT 1 FROM calculations WHERE id = 1 AND result = 6 AND user_id = 1)
        OR NOT EXISTS (SELECT 1 FROM calculations WHERE id = 3 AND result = 20 AND user_id = 2)
        OR EXISTS (SELECT 1 FROM calculations WHERE id = 2) THEN
        RAISE EXCEPTION 'Unexpected final records';
    END IF;

    BEGIN
        INSERT INTO calculations (operation, operand_a, operand_b, result, user_id)
        VALUES ('add', 1, 1, 2, -1);
        RAISE EXCEPTION 'Foreign key did not reject an unknown user';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'Foreign key correctly rejects an unknown user';
    END;

    BEGIN
        INSERT INTO users (username, email) VALUES ('alice', 'different@example.com');
        RAISE EXCEPTION 'Duplicate username was accepted';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'Duplicate username correctly rejected';
    END;

    BEGIN
        INSERT INTO users (username, email) VALUES ('different', 'alice@example.com');
        RAISE EXCEPTION 'Duplicate email was accepted';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'Duplicate email correctly rejected';
    END;

    DELETE FROM users WHERE id = 1;
    IF EXISTS (SELECT 1 FROM calculations WHERE user_id = 1)
        OR NOT EXISTS (SELECT 1 FROM calculations WHERE id = 3 AND user_id = 2) THEN
        RAISE EXCEPTION 'Cascade did not preserve the expected relationship';
    END IF;
    RAISE NOTICE 'Cascade removes Alice calculations and preserves Bob calculations';
END
$$;
ROLLBACK;
-- ROLLBACK restores rows. PostgreSQL sequences may still advance during checks.
