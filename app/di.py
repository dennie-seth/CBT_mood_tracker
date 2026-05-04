from __future__ import annotations

from dataclasses import dataclass

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.infrastructure.ai_client import make_anthropic_client
from app.infrastructure.crypto import FernetCipher
from app.infrastructure.db import make_engine, make_sessionmaker
from app.infrastructure.fsm_storage import PgFsmStorage
from app.services.ai_service import AiService
from app.services.analysis_service import AnalysisService
from app.services.chart_service import ChartService
from app.services.pdf_service import PdfService


@dataclass
class Container:
    """Process-wide singletons. Per-request services are built in handlers
    using the request's AsyncSession."""

    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    cipher: FernetCipher
    ai_client: AsyncAnthropic
    ai_service: AiService
    analysis_service_factory: type[AnalysisService]  # built per-request with a repo
    chart_service: ChartService
    pdf_service: PdfService
    fsm_storage: PgFsmStorage

    async def aclose(self) -> None:
        await self.fsm_storage.close()
        await self.engine.dispose()


def build_container(settings: Settings) -> Container:
    engine = make_engine(settings.db_url)
    sm = make_sessionmaker(engine)
    cipher = FernetCipher(settings.fernet_keys)
    ai_client = make_anthropic_client(settings.anthropic_api_key)
    ai_service = AiService(
        client=ai_client,
        model=settings.anthropic_model,
        max_iterations=settings.ai_max_tool_iterations,
    )
    fsm_storage = PgFsmStorage(sm, cipher)
    return Container(
        settings=settings,
        engine=engine,
        sessionmaker=sm,
        cipher=cipher,
        ai_client=ai_client,
        ai_service=ai_service,
        analysis_service_factory=AnalysisService,
        chart_service=ChartService(),
        pdf_service=PdfService(),
        fsm_storage=fsm_storage,
    )
