from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class TipoUsuario(str, Enum):
    ADMIN = "ADMIN"
    PROFESSOR = "PROFESSOR"
    ALUNO = "ALUNO"


class DificuldadeQuestao(str, Enum):
    FACIL = "FACIL"
    MEDIO = "MEDIO"
    DIFICIL = "DIFICIL"


class StatusResultado(str, Enum):
    EM_ANDAMENTO = "EM_ANDAMENTO"
    FINALIZADO = "FINALIZADO"
    EXPIRADO = "EXPIRADO"


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr | None = None
    cpf: str = Field(pattern=r"^\d{11}$")
    senha: str
    tipo: TipoUsuario = TipoUsuario.ALUNO


class UsuarioUpdate(BaseModel):
    nome: str | None = None
    email: EmailStr | None = None
    cpf: str | None = Field(default=None, pattern=r"^\d{11}$")
    senha: str | None = None
    tipo: TipoUsuario | None = None
    ativo: bool | None = None


class UsuarioResponse(BaseModel):
    id: str
    nome: str
    email: str | None = None
    cpf: str
    tipo: str
    ativo: bool
    senhaProvisoria: bool
    criadoEm: datetime
    atualizadoEm: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    cpf: str = Field(pattern=r"^\d{11}$")
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requer_troca_senha: bool = False


class TrocarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=1)
    senha_nova: str = Field(min_length=8, max_length=128)

    @field_validator("senha_nova")
    @classmethod
    def validar_senha_forte(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("A nova senha deve conter ao menos uma letra")
        if not any(c.isdigit() for c in v):
            raise ValueError("A nova senha deve conter ao menos um número")
        return v


class TrocarSenhaResponse(BaseModel):
    sucesso: bool = True
    mensagem: str = "Senha alterada com sucesso"


class TurmaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=50)
    anoLetivo: int = Field(ge=2024, le=2030)
    escolaId: str = Field(min_length=1)
    modalidadeId: str = Field(min_length=1)


class EscolaResumo(BaseModel):
    id: str
    nome: str

    class Config:
        from_attributes = True


class ModalidadeResumo(BaseModel):
    id: str
    nome: str

    class Config:
        from_attributes = True


class ComponenteResumo(BaseModel):
    id: str
    nome: str
    modalidade: ModalidadeResumo

    class Config:
        from_attributes = True


class TurmaResponse(BaseModel):
    id: str
    nome: str
    anoLetivo: int
    escola: EscolaResumo
    modalidade: ModalidadeResumo
    totalAlunos: int = 0


class TurmaResumoSimples(BaseModel):
    id: str
    nome: str
    escolaNome: str


class AlunoCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    cpf: str = Field(pattern=r"^\d{11}$")
    dataNascimento: date
    necessidadeEspecial: bool = False
    turmaId: str | None = None

    @field_validator("dataNascimento")
    @classmethod
    def validar_data_nao_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Data de nascimento não pode estar no futuro")
        return v


class AlunoCreateResponse(BaseModel):
    id: str
    usuarioId: str
    nome: str
    cpf: str
    email: str | None = None
    senhaProvisoria: str
    dataNascimento: date
    turmaId: str | None = None


class AlunoListItem(BaseModel):
    id: str
    nome: str
    cpf: str
    email: str | None = None
    dataNascimento: date
    necessidadeEspecial: bool
    turmaNome: str | None = None
    escolaNome: str | None = None


class SimuladoCreate(BaseModel):
    titulo: str = Field(min_length=3, max_length=200)
    descricao: str | None = Field(default=None, max_length=2000)
    componenteId: str = Field(min_length=1)
    qtdFacil: int = Field(ge=0, le=100)
    qtdMedio: int = Field(ge=0, le=100)
    qtdDificil: int = Field(ge=0, le=100)
    vagas: int = Field(ge=1, le=10000)
    duracaoMinutos: int = Field(ge=15, le=240)
    janelaInicio: datetime
    janelaFim: datetime
    turmaIds: list[str] = []
    embaralharAlternativas: bool = False

    @model_validator(mode="after")
    def validar_regras_compostas(self):
        if self.qtdFacil + self.qtdMedio + self.qtdDificil < 1:
            raise ValueError("Total de questões deve ser pelo menos 1")
        if self.janelaInicio >= self.janelaFim:
            raise ValueError("Início da janela deve ser anterior ao fim")
        agora = datetime.now(self.janelaInicio.tzinfo)
        if self.janelaInicio <= agora:
            raise ValueError("Início da janela deve estar no futuro")
        return self


class GeracaoRapidaCreate(BaseModel):
    componenteId: str = Field(min_length=1)
    duracaoMinutos: int = Field(ge=15, le=240, default=90)
    turmaIds: list[str] = []
    vagas: int = Field(ge=1, le=10000, default=100)


class SimuladoResponse(BaseModel):
    id: str
    titulo: str
    descricao: str | None
    componente: ComponenteResumo
    qtdFacil: int
    qtdMedio: int
    qtdDificil: int
    totalQuestoes: int
    vagas: int
    duracaoMinutos: int
    janelaInicio: datetime
    janelaFim: datetime
    status: str
    criadoEm: datetime
    turmas: list[TurmaResumoSimples] = []
    embaralharAlternativas: bool = False


class DisponibilidadeQuestoes(BaseModel):
    componenteId: str
    facil: int
    medio: int
    dificil: int


class AlternativaParaAluno(BaseModel):
    letra: str
    texto: str


class QuestaoParaAluno(BaseModel):
    ordem: int
    questaoId: str
    enunciado: str
    alternativas: list[AlternativaParaAluno]
    respostaSalva: str | None = None


class IniciarProvaResponse(BaseModel):
    resultadoId: str
    iniciadoEm: datetime
    expiraEm: datetime
    duracaoMinutos: int
    totalQuestoes: int
    questoes: list[QuestaoParaAluno]


class RespostaItem(BaseModel):
    questaoId: str
    resposta: str = Field(pattern=r"^[ABCDabcd]$")


class AutoSaveRequest(BaseModel):
    respostas: list[RespostaItem] = Field(min_length=1)


class AutoSaveResponse(BaseModel):
    salvo: bool
    totalSalvas: int
    salvoEm: datetime


class SimuladoResumoResultado(BaseModel):
    titulo: str
    componente: str
    duracaoMinutos: int


class GabaritoItemDetalhado(BaseModel):
    ordem: int
    questaoId: str
    enunciado: str
    alternativaMarcada: str | None
    alternativaCorreta: str
    correta: bool


class ResultadoResponse(BaseModel):
    resultadoId: str
    pontuacao: float
    acertos: int
    total: int
    statusResultado: StatusResultado
    finalizadoEm: datetime
    simulado: SimuladoResumoResultado
    gabaritoDisponivel: bool
    gabaritoDisponivelEm: datetime
    gabarito: list[GabaritoItemDetalhado] | None = None


class HistoricoItem(BaseModel):
    resultadoId: str
    simuladoId: str
    titulo: str
    componente: str
    pontuacao: float | None
    acertos: int | None
    total: int
    statusResultado: StatusResultado
    finalizadoEm: datetime | None
    gabaritoDisponivel: bool
    gabaritoDisponivelEm: datetime


class ComponenteEtapaResumo(BaseModel):
    id: str
    nome: str
    modalidade: str


class EtapaDisponivelResponse(BaseModel):
    id: str
    titulo: str
    descricao: str | None = None
    componente: ComponenteEtapaResumo
    duracaoMinutos: int
    totalQuestoes: int
    vagas: int | None = None
    janelaInicio: datetime
    janelaFim: datetime
    ativa: bool
    jaIniciada: bool
    statusResultado: str | None = None
    resultadoId: str | None = None


class ImportacaoLinha(BaseModel):
    numero: int
    nome: str | None = None
    email: str | None = None
    cpf: str | None = None
    dataNascimento: str | None = None
    turmaId: str | None = None


class ImportacaoCreateResponse(BaseModel):
    id: str
    status: str
    totalLinhas: int


class ImportacaoStatusResponse(BaseModel):
    id: str
    arquivoNome: str
    status: str
    totalLinhas: int
    processadas: int
    importados: int
    ignorados: int
    erros: list[str]
    concluida: bool


class ProcessarLoteResponse(BaseModel):
    id: str
    status: str
    processadas: int
    totalLinhas: int
    importados: int
    ignorados: int
    concluida: bool
