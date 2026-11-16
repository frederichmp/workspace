BEGIN
    INSERT INTO startupadmin.tb_teste_executor (id, nome) VALUES (:id, :nome);
    RAISE_APPLICATION_ERROR(-20001, 'Falha intencional de DML para teste de rollback');
END;