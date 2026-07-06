from dataclasses import dataclass, field
from datetime import timedelta

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from aisa.identity.application.actor import ResolveActor
from aisa.identity.application.auth_use_cases import (
    GetCurrentUser,
    LoginUser,
    RegisterUser,
    VerifyEmail,
)
from aisa.identity.application.ports import AccessTokenCodec
from aisa.identity.application.tokens import TokenService
from aisa.identity.application.workspace_use_cases import (
    ChangeMemberRole,
    CreateWorkspace,
    InviteMember,
    ListMembers,
    ListMyWorkspaces,
    RemoveMember,
)
from aisa.identity.infrastructure.repositories import (
    SqlMembershipRepository,
    SqlRefreshTokenRepository,
    SqlUserRepository,
    SqlVerificationTokenRepository,
    SqlWorkspaceRepository,
)
from aisa.identity.infrastructure.security import (
    Argon2PasswordHasher,
    JwtAccessTokenCodec,
    LoggingEmailSender,
)
from aisa.intake.application.agent import RequirementsAnalyst
from aisa.intake.application.executor import INTAKE_KIND, IntakeExecutor
from aisa.intake.application.use_cases import (
    ConfirmRequirements,
    GetRequirements,
    ListMessages,
    PostMessage,
)
from aisa.intake.infrastructure.repositories import (
    SqlMessageRepository,
    SqlRequirementRepository,
    SqlThreadRepository,
)
from aisa.llm.application.ports import LLMProvider, UsageRecorder
from aisa.llm.application.service import StructuredLLM
from aisa.llm.domain.messages import ModelTier
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.llm.infrastructure.usage import SqlUsageRecorder
from aisa.orchestration.application.ports import (
    JobQueue,
    RunEventSink,
    RunEventStream,
    RunExecutor,
    RunRepository,
)
from aisa.orchestration.application.use_cases import (
    CreateRun,
    EnqueueRunContinuation,
    ExecutePingRun,
    GetRun,
)
from aisa.orchestration.infrastructure.redis_events import (
    PgRedisRunEventSink,
    PgRedisRunEventStream,
)
from aisa.orchestration.infrastructure.redis_queue import RedisStreamJobQueue
from aisa.orchestration.infrastructure.repository import SqlAlchemyRunRepository
from aisa.platform.audit import SqlAuditLogger
from aisa.projects.application.use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    RestoreProject,
    UpdateProject,
)
from aisa.projects.infrastructure.repository import SqlProjectRepository
from aisa.shared.audit import AuditLogger
from aisa.shared.clock import Clock, SystemClock
from aisa.shared.config import Settings
from aisa.shared.ids import new_id

logger = structlog.get_logger(__name__)

KNOWN_RUN_KINDS = frozenset({"ping", INTAKE_KIND})


def _build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        # Key-less provider: auto-generates schema-valid minimal output so the
        # whole app runs locally without Gemini. Tests inject scripted fakes.
        return FakeLLMProvider()
    if not settings.gemini_api_key:
        logger.warning("llm.no_api_key", detail="AISA_GEMINI_API_KEY unset; intake will fail")
    from google import genai  # imported lazily so tooling without creds still loads

    from aisa.llm.infrastructure.gemini import GeminiProvider

    client = genai.Client(api_key=settings.gemini_api_key)
    return GeminiProvider(
        client,
        models={
            ModelTier.QUALITY: settings.llm_model_quality,
            ModelTier.FAST: settings.llm_model_fast,
        },
        max_output_tokens=settings.llm_max_output_tokens,
    )


@dataclass
class Container:
    """Composition root: wires ports to adapters. Constructor injection only."""

    settings: Settings
    engine: AsyncEngine | None
    redis: Redis | None
    clock: Clock

    # orchestration
    run_repository: RunRepository
    job_queue: JobQueue
    run_event_sink: RunEventSink
    run_event_stream: RunEventStream
    create_run: CreateRun
    get_run: GetRun
    execute_ping_run: ExecutePingRun
    run_executors: dict[str, RunExecutor]

    # identity / auth
    access_codec: AccessTokenCodec
    token_service: TokenService
    register_user: RegisterUser
    verify_email: VerifyEmail
    login_user: LoginUser
    get_current_user: GetCurrentUser
    resolve_actor: ResolveActor
    list_my_workspaces: ListMyWorkspaces
    create_workspace: CreateWorkspace
    list_members: ListMembers
    invite_member: InviteMember
    change_member_role: ChangeMemberRole
    remove_member: RemoveMember

    # projects
    create_project: CreateProject
    list_projects: ListProjects
    get_project: GetProject
    update_project: UpdateProject
    delete_project: DeleteProject
    restore_project: RestoreProject

    # intake
    llm: StructuredLLM
    post_message: PostMessage
    list_messages: ListMessages
    get_requirements: GetRequirements
    confirm_requirements: ConfirmRequirements

    audit: AuditLogger = field(kw_only=True)

    @classmethod
    def build(cls, settings: Settings, *, llm_provider: LLMProvider | None = None) -> "Container":
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        clock = SystemClock()

        # orchestration
        run_repository = SqlAlchemyRunRepository(session_factory)
        job_queue = RedisStreamJobQueue(redis)
        run_event_sink = PgRedisRunEventSink(session_factory, redis, clock)
        run_event_stream = PgRedisRunEventStream(session_factory, redis)
        create_run = CreateRun(run_repository, job_queue, clock, new_id, KNOWN_RUN_KINDS)
        continue_run = EnqueueRunContinuation(run_repository, job_queue)
        ping_executor = ExecutePingRun(run_repository, run_event_sink, clock)

        # identity
        users = SqlUserRepository(session_factory)
        workspaces = SqlWorkspaceRepository(session_factory)
        memberships = SqlMembershipRepository(session_factory)
        refresh_tokens = SqlRefreshTokenRepository(session_factory)
        verification_tokens = SqlVerificationTokenRepository(session_factory)
        hasher = Argon2PasswordHasher()
        access_codec = JwtAccessTokenCodec(
            settings.secret_key, timedelta(seconds=settings.access_token_ttl_seconds)
        )
        email_sender = LoggingEmailSender()
        audit = SqlAuditLogger(session_factory, clock)
        token_service = TokenService(
            refresh_tokens,
            access_codec,
            clock,
            new_id,
            refresh_ttl=timedelta(days=settings.refresh_token_ttl_days),
        )

        # projects
        projects = SqlProjectRepository(session_factory)

        # llm + intake
        provider = llm_provider or _build_llm_provider(settings)
        usage_recorder: UsageRecorder = SqlUsageRecorder(session_factory, clock)
        llm = StructuredLLM(provider, usage_recorder)
        threads = SqlThreadRepository(session_factory, clock)
        messages = SqlMessageRepository(session_factory)
        requirements = SqlRequirementRepository(session_factory)
        analyst = RequirementsAnalyst(llm)
        intake_executor = IntakeExecutor(
            run_repository,
            run_event_sink,
            threads,
            messages,
            requirements,
            projects,
            analyst,
            clock,
            max_rounds=settings.intake_max_rounds,
        )

        return cls(
            settings=settings,
            engine=engine,
            redis=redis,
            clock=clock,
            run_repository=run_repository,
            job_queue=job_queue,
            run_event_sink=run_event_sink,
            run_event_stream=run_event_stream,
            create_run=create_run,
            get_run=GetRun(run_repository),
            execute_ping_run=ping_executor,
            run_executors={"ping": ping_executor, INTAKE_KIND: intake_executor},
            access_codec=access_codec,
            token_service=token_service,
            register_user=RegisterUser(
                users,
                workspaces,
                memberships,
                verification_tokens,
                hasher,
                email_sender,
                audit,
                clock,
                new_id,
                verification_ttl=timedelta(hours=settings.verification_token_ttl_hours),
            ),
            verify_email=VerifyEmail(users, verification_tokens, audit, clock),
            login_user=LoginUser(users, hasher, token_service, audit),
            get_current_user=GetCurrentUser(users),
            resolve_actor=ResolveActor(memberships, users),
            list_my_workspaces=ListMyWorkspaces(workspaces),
            create_workspace=CreateWorkspace(workspaces, memberships, audit, clock, new_id),
            list_members=ListMembers(memberships),
            invite_member=InviteMember(workspaces, memberships, users, audit, new_id),
            change_member_role=ChangeMemberRole(memberships, audit),
            remove_member=RemoveMember(memberships, audit),
            create_project=CreateProject(projects, audit, clock, new_id),
            list_projects=ListProjects(projects),
            get_project=GetProject(projects),
            update_project=UpdateProject(projects, clock),
            delete_project=DeleteProject(projects, audit, clock),
            restore_project=RestoreProject(projects, audit, clock),
            llm=llm,
            post_message=PostMessage(
                threads, messages, run_repository, create_run, continue_run, clock
            ),
            list_messages=ListMessages(threads, messages),
            get_requirements=GetRequirements(requirements),
            confirm_requirements=ConfirmRequirements(requirements, audit),
            audit=audit,
        )

    async def aclose(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
        if self.engine is not None:
            await self.engine.dispose()
