--CONSULTA TODAS AS POLITICAS
select * from all_policies;

--CONSULTA TODAS AS FUNCOES DE POLITICAS
select * from dba_objects where object_type = 'FUNCTION' and OBJECT_NAME like '%VIP%';

--CRIA FUNCAO PARA MULTIPLOS PACIENTES 
create or replace function DBAMV.ACESSO_VIP_MULTI_PACIENTE (schema varchar2, tab varchar2) 
--Alterar o campo varchar se for passar de 200 caracteres
return varchar2 as con varchar2(200);
begin
--Regra para excluir do predicado o codigo dos pacientes
con := 'CD_PACIENTE NOT IN (266481,520506)'; 
return (con);
end ACESSO_VIP_MULTI_PACIENTE;
/

--DROPA FUNCAO PARA MULTIPLOS PACIENTES 
drop function dbamv.ACESSOP_VIP_MULTI_PACIENTE;

--CRIA A POLITICA DE EXCLUSAO DESATIVADA 
begin
dbms_rls.add_policy
(object_schema => 'DBAMV',
object_name => 'PACIENTE',
policy_name => 'ACESSO_VIP_MULTI_PACIENTE',
function_schema => 'DBAMV',
policy_function => 'ACESSO_VIP_MULTI_PACIENTE',
enable => FALSE,
update_check => TRUE);
end;
/

--REMOVE A POLITICA DE EXCLUSAO DESATIVADA 
begin
dbms_rls.drop_policy
(object_schema => 'DBAMV',
object_name => 'PACIENTE',
policy_name => 'ACESSO_VIP_MULTI_PACIENTE');
end;
/

--ATIVA A POLITICA
begin
DBMS_RLS.ENABLE_POLICY (
object_schema=>'DBAMV',
object_name=>'PACIENTE',
policy_name=>'ACESSO_VIP_MULTI_PACIENTE',
enable=>TRUE);
end;
/

--DESATIVA A POLITICA
begin
DBMS_RLS.ENABLE_POLICY (
object_schema=>'DBAMV',
object_name=>'PACIENTE',
policy_name=>'ACESSO_VIP_MULTI_PACIENTE',
enable=>FALSE);
end;
/
