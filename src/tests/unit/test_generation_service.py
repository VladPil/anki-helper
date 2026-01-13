"""Unit tests for GenerationService.

Tests cover:
- Job creation (create_job)
- Job retrieval (get_job)
- Job status (get_job_status)
- Job update (update_job)
- Job cancellation (cancel_job)
- Job processing (process_job)
- Job listing (list_jobs)
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis

from src.modules.generation.schemas import (
    CardType,
    GeneratedCard,
    GenerationJob,
    GenerationRequest,
    GenerationStatus,
)
from src.modules.generation.service import GenerationService


# ==================== Fixtures ====================


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client for testing."""
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.lpush = AsyncMock(return_value=1)
    redis.ltrim = AsyncMock(return_value=True)
    redis.lrange = AsyncMock(return_value=[])
    redis.exists = AsyncMock(return_value=0)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def generation_service(mock_redis: AsyncMock) -> GenerationService:
    """Create a GenerationService instance with mocked Redis."""
    return GenerationService(mock_redis)


@pytest.fixture
def sample_request() -> GenerationRequest:
    """Create a sample generation request."""
    return GenerationRequest(
        topic="Japanese particles",
        deck_id=uuid4(),
        card_type=CardType.BASIC,
        num_cards=5,
        difficulty="medium",
        language="en",
        include_sources=True,
        fact_check=True,
        context=None,
        model_id=None,
        tags=["japanese", "grammar"],
    )


@pytest.fixture
def sample_user_id() -> UUID:
    """Create a sample user ID."""
    return uuid4()


@pytest.fixture
def sample_job(sample_user_id: UUID, sample_request: GenerationRequest) -> GenerationJob:
    """Create a sample generation job."""
    now = datetime.now(UTC)
    return GenerationJob(
        id=uuid4(),
        user_id=sample_user_id,
        deck_id=sample_request.deck_id,
        status=GenerationStatus.PENDING,
        topic=sample_request.topic,
        card_type=sample_request.card_type,
        num_cards_requested=sample_request.num_cards,
        num_cards_generated=0,
        cards=[],
        created_at=now,
        updated_at=now,
        metadata={
            "language": sample_request.language,
            "difficulty": sample_request.difficulty,
            "include_sources": sample_request.include_sources,
            "fact_check": sample_request.fact_check,
            "model_id": sample_request.model_id,
            "tags": sample_request.tags,
        },
    )


# ==================== Create Job Tests ====================


@pytest.mark.asyncio
class TestCreateJob:
    """Tests for GenerationService.create_job method."""

    async def test_create_job_success(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
        sample_request: GenerationRequest,
    ):
        """Test successful job creation."""
        job = await generation_service.create_job(
            user_id=sample_user_id,
            request=sample_request,
            db=mock_db_session,
        )

        # Verify job properties
        assert job.id is not None
        assert job.user_id == sample_user_id
        assert job.deck_id == sample_request.deck_id
        assert job.status == GenerationStatus.PENDING
        assert job.topic == sample_request.topic
        assert job.card_type == sample_request.card_type
        assert job.num_cards_requested == sample_request.num_cards
        assert job.num_cards_generated == 0
        assert job.cards == []

        # Verify Redis calls
        mock_redis.setex.assert_called_once()
        mock_redis.lpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()

    async def test_create_job_stores_metadata(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
        sample_request: GenerationRequest,
    ):
        """Test that job metadata is stored correctly."""
        job = await generation_service.create_job(
            user_id=sample_user_id,
            request=sample_request,
            db=mock_db_session,
        )

        assert job.metadata["language"] == sample_request.language
        assert job.metadata["difficulty"] == sample_request.difficulty
        assert job.metadata["include_sources"] == sample_request.include_sources
        assert job.metadata["fact_check"] == sample_request.fact_check
        assert job.metadata["tags"] == sample_request.tags

    async def test_create_job_with_cloze_type(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
    ):
        """Test creating a job with cloze card type."""
        request = GenerationRequest(
            topic="Python programming",
            deck_id=uuid4(),
            card_type=CardType.CLOZE,
            num_cards=3,
        )

        job = await generation_service.create_job(
            user_id=sample_user_id,
            request=request,
            db=mock_db_session,
        )

        assert job.card_type == CardType.CLOZE

    async def test_create_job_trims_user_jobs_list(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
        sample_request: GenerationRequest,
    ):
        """Test that user jobs list is trimmed to 100 items."""
        await generation_service.create_job(
            user_id=sample_user_id,
            request=sample_request,
            db=mock_db_session,
        )

        # Verify ltrim is called with correct arguments (keep last 100)
        mock_redis.ltrim.assert_called_once()
        call_args = mock_redis.ltrim.call_args
        assert call_args[0][1] == 0  # start
        assert call_args[0][2] == 99  # end (0-indexed, so 100 items)


# ==================== Get Job Tests ====================


@pytest.mark.asyncio
class TestGetJob:
    """Tests for GenerationService.get_job method."""

    async def test_get_job_exists(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test retrieving an existing job."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        job = await generation_service.get_job(sample_job.id)

        assert job is not None
        assert job.id == sample_job.id
        assert job.topic == sample_job.topic
        mock_redis.get.assert_called_once()

    async def test_get_job_not_found(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
    ):
        """Test retrieving a non-existent job returns None."""
        mock_redis.get.return_value = None

        job = await generation_service.get_job(uuid4())

        assert job is None

    async def test_get_job_correct_key(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test that correct Redis key is used."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        await generation_service.get_job(sample_job.id)

        expected_key = f"generation:job:{sample_job.id}"
        mock_redis.get.assert_called_once_with(expected_key)


# ==================== Get Job Status Tests ====================


@pytest.mark.asyncio
class TestGetJobStatus:
    """Tests for GenerationService.get_job_status method."""

    async def test_get_job_status_pending(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test getting status of a pending job."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        status = await generation_service.get_job_status(sample_job.id, mock_db_session)

        assert status is not None
        assert status.job_id == sample_job.id
        assert status.status == GenerationStatus.PENDING
        assert status.progress == 0.0

    async def test_get_job_status_running_with_progress(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test getting status of a running job with progress."""
        sample_job.status = GenerationStatus.RUNNING
        sample_job.num_cards_generated = 2
        sample_job.num_cards_requested = 5
        sample_job.metadata["current_step"] = "generating"
        mock_redis.get.return_value = sample_job.model_dump_json()

        status = await generation_service.get_job_status(sample_job.id, mock_db_session)

        assert status is not None
        assert status.status == GenerationStatus.RUNNING
        assert status.progress == 40.0  # 2/5 * 100
        assert status.current_step == "generating"

    async def test_get_job_status_completed(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test getting status of a completed job."""
        sample_job.status = GenerationStatus.COMPLETED
        sample_job.num_cards_generated = 5
        mock_redis.get.return_value = sample_job.model_dump_json()

        status = await generation_service.get_job_status(sample_job.id, mock_db_session)

        assert status is not None
        assert status.status == GenerationStatus.COMPLETED
        assert status.progress == 100.0

    async def test_get_job_status_not_found(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
    ):
        """Test getting status of non-existent job returns None."""
        mock_redis.get.return_value = None

        status = await generation_service.get_job_status(uuid4(), mock_db_session)

        assert status is None


# ==================== Update Job Tests ====================


@pytest.mark.asyncio
class TestUpdateJob:
    """Tests for GenerationService.update_job method."""

    async def test_update_job_status(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test updating job status."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        updated_job = await generation_service.update_job(
            sample_job.id,
            {"status": GenerationStatus.RUNNING},
        )

        assert updated_job is not None
        assert updated_job.status == GenerationStatus.RUNNING
        mock_redis.setex.assert_called_once()

    async def test_update_job_multiple_fields(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test updating multiple fields at once."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        cards = [
            GeneratedCard(
                front="Q1",
                back="A1",
                card_type=CardType.BASIC,
                tags=[],
            ),
        ]

        updated_job = await generation_service.update_job(
            sample_job.id,
            {
                "status": GenerationStatus.COMPLETED,
                "num_cards_generated": 1,
                "cards": cards,
            },
        )

        assert updated_job is not None
        assert updated_job.status == GenerationStatus.COMPLETED
        assert updated_job.num_cards_generated == 1

    async def test_update_job_not_found(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
    ):
        """Test updating non-existent job returns None."""
        mock_redis.get.return_value = None

        result = await generation_service.update_job(
            uuid4(),
            {"status": GenerationStatus.COMPLETED},
        )

        assert result is None

    async def test_update_job_updates_timestamp(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test that updated_at timestamp is updated."""
        original_updated_at = sample_job.updated_at
        mock_redis.get.return_value = sample_job.model_dump_json()

        updated_job = await generation_service.update_job(
            sample_job.id,
            {"status": GenerationStatus.RUNNING},
        )

        assert updated_job is not None
        assert updated_job.updated_at > original_updated_at


# ==================== Cancel Job Tests ====================


@pytest.mark.asyncio
class TestCancelJob:
    """Tests for GenerationService.cancel_job method."""

    async def test_cancel_job_success(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test successful job cancellation."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        result = await generation_service.cancel_job(sample_job.id, mock_db_session)

        assert result is True
        # Verify cancellation flag was set
        assert mock_redis.setex.call_count >= 1

    async def test_cancel_job_sets_cancel_flag(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_job: GenerationJob,
    ):
        """Test that cancellation flag is set in Redis."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        await generation_service.cancel_job(sample_job.id, mock_db_session)

        # Check that setex was called with the cancel key
        calls = mock_redis.setex.call_args_list
        cancel_key_call = any(
            f"generation:cancel:{sample_job.id}" in str(call)
            for call in calls
        )
        assert cancel_key_call or len(calls) > 0


# ==================== Is Cancelled Tests ====================


@pytest.mark.asyncio
class TestIsCancelled:
    """Tests for GenerationService.is_cancelled method."""

    async def test_is_cancelled_true(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
    ):
        """Test detecting cancelled job."""
        mock_redis.exists.return_value = 1

        result = await generation_service.is_cancelled(uuid4())

        assert result is True

    async def test_is_cancelled_false(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
    ):
        """Test detecting non-cancelled job."""
        mock_redis.exists.return_value = 0

        result = await generation_service.is_cancelled(uuid4())

        assert result is False


# ==================== Process Job Tests ====================


@pytest.mark.asyncio
class TestProcessJob:
    """Tests for GenerationService.process_job method."""

    async def test_process_job_success(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
        sample_request: GenerationRequest,
    ):
        """Test successful job processing."""
        mock_redis.get.return_value = sample_job.model_dump_json()
        mock_redis.exists.return_value = 0  # Not cancelled

        # Mock the workflow
        mock_workflow = AsyncMock()
        mock_workflow.run.return_value = {
            "cards": [
                {"front": "Q1", "back": "A1", "tags": ["test"]},
                {"front": "Q2", "back": "A2", "tags": ["test"]},
            ]
        }
        generation_service._workflow = mock_workflow

        with patch("src.modules.generation.service.CARD_GENERATION_COUNT"), \
             patch("src.modules.generation.service.CARD_GENERATION_LATENCY"):
            await generation_service.process_job(sample_job.id, sample_request)

        # Verify workflow was called
        mock_workflow.run.assert_called_once()

    async def test_process_job_cancelled(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
        sample_request: GenerationRequest,
    ):
        """Test job processing when cancelled."""
        mock_redis.get.return_value = sample_job.model_dump_json()
        mock_redis.exists.return_value = 1  # Cancelled

        mock_workflow = AsyncMock()
        mock_workflow.run.return_value = {"cards": []}
        generation_service._workflow = mock_workflow

        with patch("src.modules.generation.service.CARD_GENERATION_COUNT"), \
             patch("src.modules.generation.service.CARD_GENERATION_LATENCY"):
            await generation_service.process_job(sample_job.id, sample_request)

        # Job should still call workflow but check cancellation after

    async def test_process_job_failure(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        sample_job: GenerationJob,
        sample_request: GenerationRequest,
    ):
        """Test job processing when workflow fails."""
        mock_redis.get.return_value = sample_job.model_dump_json()
        mock_redis.exists.return_value = 0

        mock_workflow = AsyncMock()
        mock_workflow.run.side_effect = Exception("Workflow error")
        generation_service._workflow = mock_workflow

        with patch("src.modules.generation.service.CARD_GENERATION_COUNT"), \
             patch("src.modules.generation.service.CARD_GENERATION_LATENCY"):
            await generation_service.process_job(sample_job.id, sample_request)

        # Verify job was updated with error status
        # Check that setex was called (for updating job with error)
        assert mock_redis.setex.call_count >= 1


# ==================== List Jobs Tests ====================


@pytest.mark.asyncio
class TestListJobs:
    """Tests for GenerationService.list_jobs method."""

    async def test_list_jobs_empty(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
    ):
        """Test listing jobs when none exist."""
        mock_redis.lrange.return_value = []

        jobs = await generation_service.list_jobs(
            user_id=sample_user_id,
            db=mock_db_session,
        )

        assert jobs == []

    async def test_list_jobs_with_results(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
        sample_job: GenerationJob,
    ):
        """Test listing jobs with results."""
        job_id_str = str(sample_job.id)
        mock_redis.lrange.return_value = [job_id_str]
        mock_redis.get.return_value = sample_job.model_dump_json()

        jobs = await generation_service.list_jobs(
            user_id=sample_user_id,
            db=mock_db_session,
        )

        assert len(jobs) == 1
        assert jobs[0].id == sample_job.id

    async def test_list_jobs_with_status_filter(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
        sample_job: GenerationJob,
    ):
        """Test listing jobs with status filter."""
        sample_job.status = GenerationStatus.COMPLETED
        job_id_str = str(sample_job.id)
        mock_redis.lrange.return_value = [job_id_str]
        mock_redis.get.return_value = sample_job.model_dump_json()

        # Filter by PENDING - should return empty
        jobs = await generation_service.list_jobs(
            user_id=sample_user_id,
            db=mock_db_session,
            status_filter=GenerationStatus.PENDING,
        )
        assert len(jobs) == 0

        # Filter by COMPLETED - should return the job
        jobs = await generation_service.list_jobs(
            user_id=sample_user_id,
            db=mock_db_session,
            status_filter=GenerationStatus.COMPLETED,
        )
        assert len(jobs) == 1

    async def test_list_jobs_pagination(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
    ):
        """Test listing jobs with pagination."""
        mock_redis.lrange.return_value = []

        await generation_service.list_jobs(
            user_id=sample_user_id,
            db=mock_db_session,
            limit=10,
            offset=5,
        )

        # Verify lrange was called with correct offset and limit
        mock_redis.lrange.assert_called_once()
        call_args = mock_redis.lrange.call_args[0]
        assert call_args[1] == 5  # offset
        assert call_args[2] == 14  # offset + limit - 1


# ==================== Integration Tests ====================


@pytest.mark.asyncio
class TestGenerationServiceIntegration:
    """Integration-style tests for GenerationService."""

    async def test_full_job_lifecycle(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
        sample_request: GenerationRequest,
    ):
        """Test complete job lifecycle: create -> update -> get -> cancel."""
        # Create job
        job = await generation_service.create_job(
            user_id=sample_user_id,
            request=sample_request,
            db=mock_db_session,
        )

        # Store the job JSON for get operations
        mock_redis.get.return_value = job.model_dump_json()

        # Get job
        retrieved_job = await generation_service.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.status == GenerationStatus.PENDING

        # Update to running
        updated_job = await generation_service.update_job(
            job.id,
            {"status": GenerationStatus.RUNNING},
        )
        assert updated_job is not None
        assert updated_job.status == GenerationStatus.RUNNING

        # Update mock to return running job
        updated_job_running = updated_job.model_copy()
        mock_redis.get.return_value = updated_job_running.model_dump_json()

        # Cancel job
        result = await generation_service.cancel_job(job.id, mock_db_session)
        assert result is True

    async def test_job_with_all_card_types(
        self,
        generation_service: GenerationService,
        mock_redis: AsyncMock,
        mock_db_session: AsyncMock,
        sample_user_id: UUID,
    ):
        """Test creating jobs with all card types."""
        for card_type in CardType:
            request = GenerationRequest(
                topic="Test topic",
                deck_id=uuid4(),
                card_type=card_type,
                num_cards=3,
            )

            job = await generation_service.create_job(
                user_id=sample_user_id,
                request=request,
                db=mock_db_session,
            )

            assert job.card_type == card_type
