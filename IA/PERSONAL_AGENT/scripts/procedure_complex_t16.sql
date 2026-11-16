CREATE OR REPLACE PROCEDURE startupadmin.pr_teste_t16 AS
    v_a NUMBER := 1;
BEGIN
    IF v_a = 1 THEN
        v_a := 2;
    END IF;
    LOOP
        EXIT;
    END LOOP;
    CASE
        WHEN v_a = 2 THEN NULL;
    END CASE;
END pr_teste_t16;