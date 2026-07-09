# Política de Privacidade - Nano-IaaS

Versão inicial Pré-Beta.

Esta política descreve como o Nano-IaaS trata dados pessoais, credenciais cloud e logs durante a fase Pré-Beta/Beta. Este documento representa uma adequação inicial à LGPD e deve passar por revisão jurídica antes do uso comercial amplo.

## 1. O que é o Nano-IaaS

O Nano-IaaS não substitui AWS, Azure ou Google Cloud. A plataforma funciona como uma camada web, multiusuário, segura e auditável para leitura de dados em ambientes cloud.

O sistema atua em modo read-only: permite listagem e leitura de recursos, sem operações de escrita, alteração ou exclusão nas clouds conectadas.

## 2. Dados que podem ser tratados

Durante o uso da plataforma, o Nano-IaaS pode tratar:

- Dados de conta, como e-mail do usuário e plano contratado.
- Credenciais cloud fornecidas pelo usuário para conexão com AWS S3, Azure Blob Storage ou Google Cloud Storage.
- Metadados de recursos consultados, como nomes de buckets, containers, arquivos, tamanho e datas.
- Logs de auditoria, como usuário, ação realizada, provider, recurso acessado, data e hora.
- Informações técnicas necessárias para segurança, autenticação e operação do serviço.

## 3. Credenciais cloud

O usuário deve fornecer credenciais cloud com permissões mínimas e somente leitura.

As credenciais cadastradas são armazenadas criptografadas e devem ser usadas apenas para listar recursos e ler objetos/blobs autorizados pelo próprio usuário ou pela organização responsável.

Não devem ser cadastradas credenciais administrativas, credenciais com permissão de escrita, delete, alteração de políticas, criação de recursos ou gerenciamento de infraestrutura.

## 4. Logs de auditoria

O Nano-IaaS pode gerar logs de auditoria para segurança, rastreabilidade, investigação de incidentes e melhoria operacional.

Esses logs podem registrar quem acessou determinado provider, recurso ou arquivo, quando o acesso ocorreu e qual ação foi realizada.

## 5. Finalidade do tratamento

Os dados são tratados para:

- Autenticar usuários.
- Permitir acesso read-only a recursos cloud conectados.
- Exibir dados e metadados no dashboard.
- Registrar auditoria e rastreabilidade.
- Proteger a plataforma contra uso indevido.
- Apoiar suporte, diagnóstico e melhoria do produto.

## 6. Compartilhamento

O Nano-IaaS não deve vender dados pessoais ou credenciais cloud.

Dados podem ser compartilhados apenas quando necessário para operação técnica, cumprimento de obrigação legal, segurança, suporte solicitado pelo usuário ou revisão de incidentes.

## 7. Responsabilidades do usuário

O usuário é responsável por:

- Fornecer credenciais com privilégio mínimo e somente leitura.
- Garantir que possui autorização para acessar os recursos cloud conectados.
- Não cadastrar dados ou credenciais de terceiros sem autorização.
- Revogar ou rotacionar credenciais quando necessário.
- Avaliar internamente a política de acesso aos dados consultados pela plataforma.

## 8. Segurança

A plataforma adota medidas iniciais de proteção, incluindo autenticação, criptografia de credenciais e logs de auditoria.

Nenhum sistema é totalmente imune a riscos. A fase Beta deve ser usada com contas, credenciais e dados adequados ao nível de maturidade do projeto.

## 9. Direitos dos titulares

Conforme aplicável, titulares de dados podem solicitar informações, correção, exclusão, portabilidade ou revisão sobre dados pessoais tratados pela plataforma.

Como esta é uma política inicial, fluxos formais de atendimento LGPD ainda devem ser definidos antes da operação comercial ampla.

## 10. Revisão jurídica

Este documento não substitui uma política jurídica definitiva. Antes da Beta comercial ou uso por clientes externos, recomenda-se revisão por profissional jurídico especializado em proteção de dados e contratos de tecnologia.
