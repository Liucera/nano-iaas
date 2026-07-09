# Termos de Uso - Nano-IaaS

Versão inicial Pré-Beta.

Estes Termos de Uso definem regras iniciais para uso do Nano-IaaS durante a fase Pré-Beta/Beta. O texto representa uma base operacional e deve passar por revisão jurídica antes do uso comercial amplo.

## 1. Aceitação dos termos

Ao usar o Nano-IaaS, o usuário declara que leu e concorda com estes Termos de Uso e com a Política de Privacidade.

A tela de cadastro possui checkbox explícito de aceite dos Termos de Uso e da Política de Privacidade.

## 2. Natureza do produto

O Nano-IaaS não substitui AWS, Azure ou Google Cloud.

A plataforma oferece uma camada web, multiusuário, segura e auditável para leitura de dados em ambientes cloud.

O produto atua em modo read-only, permitindo listagem e leitura de recursos sem escrita, alteração ou exclusão.

## 3. Uso permitido

O usuário pode usar o Nano-IaaS para:

- Cadastrar credenciais cloud de leitura.
- Listar buckets, containers e recursos autorizados.
- Abrir arquivos e objetos permitidos pelas credenciais fornecidas.
- Consultar logs de auditoria.
- Avaliar o produto em ambiente Beta.

## 4. Uso proibido

O usuário não deve:

- Cadastrar credenciais administrativas ou com permissão ampla desnecessária.
- Usar a plataforma para acessar dados sem autorização.
- Tentar burlar autenticação, auditoria ou controles de segurança.
- Usar a plataforma para escrita, alteração, exclusão ou administração de recursos cloud.
- Compartilhar credenciais de forma insegura.

## 5. Credenciais e permissões mínimas

O usuário deve fornecer credenciais cloud com privilégio mínimo e somente leitura.

A responsabilidade por criar, limitar, revogar e rotacionar credenciais cloud permanece com o usuário ou com a organização responsável pela conta cloud.

As credenciais cadastradas na plataforma são armazenadas criptografadas.

## 6. Auditoria e rastreabilidade

O Nano-IaaS pode registrar logs de auditoria para segurança e rastreabilidade, incluindo usuário, provider, recurso acessado, ação executada, data e hora.

Esses registros ajudam na investigação de incidentes, conformidade interna e controle de acesso.

## 7. Limitações da fase Beta

Durante a fase Beta, algumas funcionalidades podem estar incompletas, em validação ou sujeitas a alteração.

Na Beta atual, o Dashboard/API usa providers reais para AWS S3, Azure Blob Storage e Google Cloud Storage. O CLI usa AWS real, enquanto GCP e Azure ainda podem estar em modo mock/dev.

## 8. Disponibilidade e suporte

A plataforma pode passar por instabilidades, manutenções ou alterações durante a fase Beta.

O suporte e os prazos de resposta devem ser combinados conforme o plano ou acordo aplicável.

## 9. Responsabilidade

O usuário é responsável por garantir que possui autorização para conectar as contas cloud, consultar recursos e visualizar dados pela plataforma.

O Nano-IaaS não se responsabiliza por credenciais fornecidas com permissões excessivas, dados cadastrados indevidamente ou uso em desacordo com estes termos.

## 10. Revisão futura

Estes termos são uma versão inicial. Antes da Beta comercial ou contratação por clientes externos, recomenda-se revisão jurídica para adequar responsabilidades, suporte, SLA, privacidade, segurança e limites comerciais.
