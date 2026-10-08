--------------------------------------------------------
--  DDL for Table LOG_EXPURGO
--------------------------------------------------------


CREATE SEQUENCE SEQ_EXPURGO INCREMENT BY 1 MAXVALUE 9999999999999999999999999999 MINVALUE 1 CACHE 100;



CREATE TABLE LOG_EXPURGO 
(
  ID NUMBER NOT NULL 
, TABELA VARCHAR2(200 BYTE) NOT NULL 
, DATA_REGISTRO DATE NOT NULL 
, DATA_FILTRO_EXPURGO DATE NOT NULL 
, QTD_ITEM_EXCLUIDO NUMBER NOT NULL 
, MENSAGEM_SITUACAO VARCHAR2(4000 BYTE) NOT NULL 
, CONSTRAINT LOG_EXPURGO_PK PRIMARY KEY 
  (
    ID 
  )
);






CREATE OR REPLACE PROCEDURE SISTEMA_EXPURGO AS
-- Startup Dados e Sistemas
--
-- Sistema de Expurgo Solicitado pelo Cliente - Chamado #1222-000025
--
-- Pelo chamado #0000-000000 foi realizado a aprovacao da implementacao deste SCRIPT no ambiente de Producao
--
-- Informacoes da tabela que sofre o expurgo
-- Tabela: NOME_DA_TABELA
-- Coluna filtro: NOME_COLUNA_FILTRO_EXPURGO
-- Objetivo expurgo: Manter apenas os Ultimos SEIS meses de informacoes
--
-- Informacoes de LOG do Expurgo
-- Tabela Log: LOG_EXPURGO
--
--
-- Autor: Wesley David Santos
-- Skype: wesleydavidsantos		
-- https://www.linkedin.com/in/wesleydavidsantos
--


	v_QTD_MESES_MANTER_DADOS CONSTANT NUMBER := -6;

    v_STMT_REGISTRA_LOG CONSTANT VARCHAR(4000) := 'INSERT INTO LOG_EXPURGO ( ID, TABELA, DATA_REGISTRO, DATA_FILTRO_EXPURGO, QTD_ITEM_EXCLUIDO, MENSAGEM_SITUACAO ) VALUES ( :ID, :TABELA, :DATA_REGISTRO, :DATA_FILTRO_EXPURGO, :QTD_ITEM_EXCLUIDO, :MENSAGEM_SITUACAO )';

    v_STMT_DELETE CONSTANT VARCHAR(4000) := 'DELETE FROM TESTE_EXPURGO WHERE ROWID = :ROWID_ITEM AND TO_CHAR( TRUNC( DATA_CADASTRO ), ''YYYY-MM-DD'' ) = :DATA_DELETE';

    CURSOR c_LISTA_DATAS_PARA_EXPURGO( p_QTD_MESES_MANTER_DADOS NUMBER ) IS
        SELECT 
            DISTINCT 
            TO_CHAR( TRUNC( DATA_CADASTRO ), 'YYYY-MM-DD' ) DATA_DELETE
        FROM
            TESTE_EXPURGO
        WHERE
            DATA_CADASTRO < ADD_MONTHS( SYSDATE, p_QTD_MESES_MANTER_DADOS )
        ORDER BY DATA_DELETE;
    

	CURSOR c_TABELA_SOFRE_EXPURGO( p_DATA_DELETE DATE ) IS 
		SELECT
			  ROWID ROWID_ITEM
             ,DATA_CADASTRO
		FROM
			TESTE_EXPURGO
		WHERE
			TO_CHAR( TRUNC( DATA_CADASTRO ), 'YYYY-MM-DD' ) = p_DATA_DELETE;
		
    
    
    v_QTD_ITEM_DELETE NUMBER;
    
    v_ROWID_ITEM VARCHAR(150);
    
    v_DATA_FILTRO_EXPURGO DATE;
    
    v_MSG_EXPURGO VARCHAR(4000);
    
    v_NOME_TABELA_EXPURGO CONSTANT VARCHAR(100) := 'TESTE_EXPURGO';
    
BEGIN


    FOR v_DATA_EXPURGO IN c_LISTA_DATAS_PARA_EXPURGO( v_QTD_MESES_MANTER_DADOS )
    LOOP
    
        BEGIN
        
            v_QTD_ITEM_DELETE := 0;
            
            v_DATA_FILTRO_EXPURGO := v_DATA_EXPURGO.DATA_DELETE;
            
            --DBMS_OUTPUT.PUT_LINE( 'Data Delete: ' || v_DATA_FILTRO_EXPURGO );
            
            BEGIN
            
                
            
                FOR v_ITEM_EXPURGO IN c_TABELA_SOFRE_EXPURGO( v_DATA_FILTRO_EXPURGO )
                LOOP
                    
                    v_ROWID_ITEM := v_ITEM_EXPURGO.ROWID_ITEM;
                    
                    v_QTD_ITEM_DELETE := v_QTD_ITEM_DELETE + 1;
                
                    --EXECUTE IMMEDIATE v_STMT_DELETE USING v_ROWID_ITEM, v_DATA_FILTRO_EXPURGO;
                    
                    -BMS_OUTPUT.PUT_LINE( 'Delete ROWID: ' || v_ROWID_ITEM || ' / DATA: ' || v_DATA_FILTRO_EXPURGO );
                
                
                END LOOP;
                
                            
                v_MSG_EXPURGO := 'Expurgo realizado com sucesso';
                
                IF v_QTD_ITEM_DELETE = 0 THEN
                    
                    v_MSG_EXPURGO := 'Nenhum item foi excluído';
                    
                END IF;
                            
            
            EXCEPTION
            
                WHEN OTHERS THEN
                    
                    ROLLBACK;
                    
                    v_MSG_EXPURGO := 'ROLLBACK realizado. Falha expurgo. ROWID: ' || v_ROWID_ITEM || '. Erro: ' || SUBSTR( SQLERRM, 1, 3000 );
                    
                    --DBMS_OUTPUT.PUT_LINE( v_MSG_EXPURGO );
                    
            END;
            
        
            EXECUTE IMMEDIATE v_STMT_REGISTRA_LOG USING SEQ_EXPURGO.NEXTVAL, v_NOME_TABELA_EXPURGO, SYSDATE, v_DATA_FILTRO_EXPURGO, v_QTD_ITEM_DELETE, v_MSG_EXPURGO;
        
            COMMIT;
            
            
        EXCEPTION
            
            WHEN OTHERS THEN
            
                ROLLBACK;
                
                v_MSG_EXPURGO := 'ROLLBACK realizado. Falha expurgo. Erro: ' || SUBSTR( SQLERRM, 1, 3000 );
                
                --DBMS_OUTPUT.PUT_LINE( v_MSG_EXPURGO );
                
                EXECUTE IMMEDIATE v_STMT_REGISTRA_LOG USING SEQ_EXPURGO.NEXTVAL, v_NOME_TABELA_EXPURGO, SYSDATE, v_DATA_FILTRO_EXPURGO, v_QTD_ITEM_DELETE, v_MSG_EXPURGO;
        
                COMMIT;
                
        END;
        
    
    END LOOP;


END;
/





















